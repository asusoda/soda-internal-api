"""
Direct command registration for Discord 
This provides an alternative method to register the /summarize command
"""

import discord
from discord.ext import commands
from modules.summarizer.service import SummarizerService
from datetime import datetime, timezone, timedelta
import logging
import asyncio
import random

logger = logging.getLogger(__name__)

# Create a direct slash command without using a cog
@discord.slash_command(
    name="summarize",
    description="Summarize recent channel messages"
)
async def summarize_command(
    ctx,
    timeframe: discord.Option(
        str,
        "Time period to summarize (e.g., '3 days', 'last week', 'January 1 to January 15')",
        required=False,
        default="24h"
    )
):
    """Generate a summary of recent channel messages"""
    # Initial response to user - always ephemeral initially
    await ctx.defer(ephemeral=True)
    
    service = SummarizerService()
    
    try:
        # Show thinking message
        thinking_message = await ctx.followup.send(
            "🔄 Thinking... I'm reviewing the messages and generating a summary.",
            ephemeral=True
        )
        
        # Parse the timeframe using natural language processing
        try:
            start_time, end_time, display_range = service.parse_date_range(timeframe)
            
            # If end_time is provided, we're in timeline mode (specific date range)
            if end_time:
                look_back_time = start_time
                end_datetime = end_time
            else:
                # Duration mode - just use start_time
                look_back_time = start_time
                end_datetime = None
                
            logger.info(f"Parsed timeframe '{timeframe}' as: {start_time} to {end_time if end_time else 'now'} (display: {display_range})")
            
        except Exception as e:
            logger.error(f"Error parsing timeframe '{timeframe}': {e}")
            await thinking_message.edit(content=f"⚠️ Error: I couldn't understand the timeframe '{timeframe}'. Try something like '24h', 'last week', or 'January 1 to January 15'.")
            return
        
        # Fetch messages from the channel - with debug info
        messages = []
        try:
            # First message to report the timeframe
            await thinking_message.edit(content=f"🔍 Searching for messages from {look_back_time.strftime('%Y-%m-%d %H:%M:%S')} UTC...")

            message_count = 0
            
            # Use different fetching methods based on whether we have an end date
            if end_datetime:
                async for message in ctx.channel.history(after=look_back_time, before=end_datetime, limit=None):
                    message_count += 1
                    # Skip bot messages
                    if message.author.bot:
                        continue

                    # Skip system messages
                    if message.type != discord.MessageType.default:
                        continue

                    # Format the message
                    message_data = {
                        "id": str(message.id),
                        "content": message.content,
                        "author": {
                            "id": str(message.author.id),
                            "name": message.author.display_name
                        },
                        "timestamp": message.created_at.strftime("%Y-%m-%d %H:%M:%S"),
                        "jump_url": message.jump_url
                    }

                    messages.append(message_data)

                    # Update the message every 25 messages for user feedback
                    if len(messages) % 25 == 0:
                        await thinking_message.edit(content=f"🔍 Found {len(messages)} relevant messages out of {message_count} total...")
            else:
                async for message in ctx.channel.history(after=look_back_time, limit=None):
                    message_count += 1
                    # Skip bot messages
                    if message.author.bot:
                        continue

                    # Skip system messages
                    if message.type != discord.MessageType.default:
                        continue

                    # Format the message
                    message_data = {
                        "id": str(message.id),
                        "content": message.content,
                        "author": {
                            "id": str(message.author.id),
                            "name": message.author.display_name
                        },
                        "timestamp": message.created_at.strftime("%Y-%m-%d %H:%M:%S"),
                        "jump_url": message.jump_url
                    }

                    messages.append(message_data)

                    # Update the message every 25 messages for user feedback
                    if len(messages) % 25 == 0:
                        await thinking_message.edit(content=f"🔍 Found {len(messages)} relevant messages out of {message_count} total...")

            # Log the results
            print(f"Discord history search for timeframe '{display_range}': Found {len(messages)} relevant messages out of {message_count} total")
            logger.info(f"Found {len(messages)} relevant messages out of {message_count} total")

            # Sort messages by timestamp (oldest first)
            messages.sort(key=lambda msg: msg["timestamp"])

        except discord.Forbidden:
            logger.error("Bot doesn't have permission to fetch message history")
            await thinking_message.edit(content="⚠️ I don't have permission to read the message history in this channel.")
            return
        except Exception as e:
            logger.error(f"Error fetching messages: {e}")
            print(f"Error fetching message history: {e}")
        
        # Check if we have enough messages to summarize
        if len(messages) == 0:
            embed = discord.Embed(
                title=f"Channel Summary ({display_range})",
                description=f"🔎 No messages found in this channel for the specified period ({display_range}).",
                color=discord.Color.blue()
            )
            await thinking_message.edit(content=None, embed=embed)
            return

        # Use a simple spinner animation for loading
        spinner_frames = ["⠋", "⠙", "⠹", "⠸", "⠼", "⠴", "⠦", "⠧", "⠇", "⠏"]
        loading_base = "Generating summary... "

        # Set an initial static message
        try:
            await thinking_message.edit(content=f"{loading_base} Please wait, this may take a minute.")
            logger.info("Set static loading message")
        except Exception as e:
            logger.error(f"Failed to set static loading message: {e}")

        # Define a stub task that does nothing (we're avoiding animation due to Discord rate limits)
        async def dummy_task():
            try:
                await asyncio.sleep(60)  # Just wait until cancelled
            except asyncio.CancelledError:
                logger.info("Dummy task cancelled")
                return

        # Create a task that doesn't actually edit messages
        loop = asyncio.get_event_loop()
        loading_task = loop.create_task(dummy_task())

        # Generate summary
        summary_result = service.generate_summary(
            messages=messages,
            duration_str=display_range,
            user_id=str(ctx.author.id),
            channel_id=str(ctx.channel.id),
            guild_id=str(ctx.guild.id)
        )
        
        # Get stats
        message_count = summary_result['message_count']

        # Get unique participants
        participants = set()
        for msg in messages:
            participants.add(msg["author"]["name"])
        participant_count = len(participants)

        # Calculate time span
        time_span = "0 minutes"
        if messages and len(messages) > 1:
            first_msg_time = datetime.strptime(messages[0]["timestamp"], "%Y-%m-%d %H:%M:%S")
            last_msg_time = datetime.strptime(messages[-1]["timestamp"], "%Y-%m-%d %H:%M:%S")
            delta = last_msg_time - first_msg_time
            minutes = delta.total_seconds() / 60
            time_span = f"{int(minutes)} minutes"

        # Get the summary from the result
        summary = summary_result["summary"]

        # Print detailed debug info
        print(f"============ SUMMARY START ============")
        print(f"Summary length: {len(summary)} characters")
        print(f"Summary content: {summary}")
        print(f"============ SUMMARY END ==============")

        # Log that we're using the raw LLM output
        logger.info(f"Using LLM-generated summary without manual formatting")

        # Check if summary is too long for embed description (which has a 4096 character limit)
        if len(summary) > 4000:
            summary = summary[:3997] + "..."

        # Create embed for response
        embed = discord.Embed(
            title=f"Channel Summary ({display_range})",
            description=summary,
            color=discord.Color.blue()
        )

        # Move stats to the footer with emojis and bullet separators
        embed.set_footer(text=f"📊 {message_count} msgs • 👥 {participant_count} participants • ⏱️ {time_span} • Requested by {ctx.author.display_name}")
        
        # Create a view with the make public button
        view = discord.ui.View()
        make_public_button = discord.ui.Button(
            style=discord.ButtonStyle.secondary,
            label="Make Public",
            emoji="🌐",
            custom_id="make_summary_public"
        )
        
        # Define the callback for the button
        async def make_public_callback(interaction):
            if interaction.user.id != ctx.author.id:
                await interaction.response.send_message("Only the user who requested the summary can make it public.", ephemeral=True)
                return
            
            # Send the same embed as a public message directly
            await ctx.channel.send(embed=embed)
            
            # Delete the ephemeral message
            try:
                # Acknowledge the interaction without sending a visible message
                await interaction.response.defer(ephemeral=True)
                await thinking_message.delete()
            except Exception as e:
                logger.error(f"Failed to delete ephemeral message: {e}")
        
        make_public_button.callback = make_public_callback
        view.add_item(make_public_button)
        
        # Cancel the loading animation task and wait for it to complete
        if loading_task.cancel():
            logger.info("Loading task was successfully cancelled")
        else:
            logger.warning("Loading task was already cancelled or completed")

        try:
            # Wait for the task to properly cancel (with timeout)
            await asyncio.wait_for(loading_task, timeout=1.0)
            logger.info("Loading task cancellation complete")
        except asyncio.TimeoutError:
            logger.warning("Timeout waiting for loading task to cancel")
        except asyncio.CancelledError:
            logger.info("Loading task was properly cancelled")
        except Exception as e:
            logger.error(f"Error during loading task cancellation: {e}")

        # Edit the thinking message with the final response
        try:
            await thinking_message.edit(content=None, embed=embed, view=view)
            logger.info("Successfully updated message with summary embed")
        except Exception as e:
            logger.error(f"Error updating message with summary: {e}")
            # Fallback - try sending a new message
            try:
                await ctx.followup.send(content=None, embed=embed, view=view, ephemeral=True)
                logger.info("Sent summary as a new message")
            except Exception as send_error:
                logger.error(f"Error sending fallback message: {send_error}")
        
    except Exception as e:
        # Make sure to cancel the loading task if it exists
        if 'loading_task' in locals():
            try:
                if loading_task.cancel():
                    logger.info("Error handler: Loading task was successfully cancelled")
                await asyncio.wait_for(loading_task, timeout=1.0)
            except (asyncio.TimeoutError, asyncio.CancelledError, Exception) as task_error:
                logger.error(f"Error handler: Issue cancelling loading task: {task_error}")

        logger.error(f"Error in summarize command: {e}")

        # Create an error embed with Markdown formatting
        error_embed = discord.Embed(
            title="Summary Generation Error",
            description="""# Error Generating Summary ⚠️

I encountered an unexpected error while processing your request.

## Technical Details

An error occurred during the summarization process.

## Next Steps

- Try again with a shorter time period
- Contact support if the issue persists""",
            color=discord.Color.red()
        )

        try:
            # First try to edit the thinking message if it exists
            if 'thinking_message' in locals():
                await thinking_message.edit(content=None, embed=error_embed)
            else:
                # Fall back to sending a new message
                await ctx.followup.send(embed=error_embed, ephemeral=True)
        except Exception as send_error:
            logger.error(f"Failed to send error message: {send_error}")
            # Last resort plain text fallback
            await ctx.followup.send(
                "⚠️ Sorry, I encountered an error trying to generate the summary. Please try again later.",
                ephemeral=True
            )

def register_direct_commands(bot):
    """
    Register direct commands with the bot
    
    Args:
        bot: The Discord bot instance
    """
    # Add the direct commands to the bot
    bot.add_application_command(summarize_command)
    print(f"Registered direct command: summarize")
    
    # Return success
    return True
