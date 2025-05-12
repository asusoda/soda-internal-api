import discord
from discord.ext import commands
from discord import SlashCommandGroup, Option, OptionChoice, ApplicationContext
import asyncio
from datetime import datetime, timezone, timedelta
from typing import List, Dict, Any, Optional
from modules.summarizer.service import SummarizerService
from shared import logger

class SummarizerCog(commands.Cog, name="Summarizer"):
    """Discord cog for the channel summarizer functionality"""

    def __init__(self, bot):
        self.bot = bot
        self.summarizer_service = SummarizerService()
        print("SummarizerCog initialized - registering /summarize command")

    # Create a slash command for summarization
    @discord.slash_command(
        name="summarize",
        description="Summarize recent channel messages",
        guild_ids=None  # This makes it global
    )
    async def summarize_command(
        self,
        ctx: discord.ApplicationContext,
        duration: discord.Option(
            str,
            "Time period to summarize (default: 24h)",
            required=False,
            choices=[
                "1h",
                "24h",
                "1d",
                "3d",
                "7d",
                "1w"
            ],
            default="24h"
        ),
        public: discord.Option(
            bool,
            "Make the summary visible to everyone (default: False)",
            required=False,
            default=False
        )
    ):
        """Generate a summary of recent channel messages"""
        # Initial response to user - ephemeral based on public parameter
        await ctx.defer(ephemeral=not public)
        
        try:
            # Show initial thinking message
            thinking_message = await ctx.followup.send(
                "🔄 Thinking... I'm reviewing the messages and generating a summary.",
                ephemeral=not public
            )

            # Parse duration and calculate time range
            time_delta = self.summarizer_service.parse_duration(duration)
            look_back_time = datetime.now(timezone.utc) - time_delta

            # Show message about fetching messages
            await thinking_message.edit(content=f"🔍 Searching for messages since {look_back_time.strftime('%Y-%m-%d %H:%M:%S')} UTC...")

            # Fetch messages from the channel
            messages = await self._fetch_messages(ctx.channel, look_back_time)

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
            try:
                summary_result = self.summarizer_service.generate_summary(
                    messages=messages,
                    duration_str=duration,
                    user_id=str(ctx.author.id),
                    channel_id=str(ctx.channel.id),
                    guild_id=str(ctx.guild.id)
                )

                # Cancel the loading task when done
                if loading_task.cancel():
                    logger.info("Loading task was successfully cancelled")

                try:
                    # Wait for the task to cancel with timeout
                    await asyncio.wait_for(loading_task, timeout=1.0)
                except (asyncio.TimeoutError, asyncio.CancelledError, Exception):
                    pass
            except Exception as gen_error:
                # Handle summary generation error
                if loading_task.cancel():
                    logger.info("Loading task was cancelled due to generation error")
                try:
                    await asyncio.wait_for(loading_task, timeout=1.0)
                except Exception:
                    pass
                logger.error(f"Error generating summary: {gen_error}")
                raise  # Re-raise to be caught by the outer try/except
            
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

            # Create embed for response
            embed = discord.Embed(
                title=f"Channel Summary ({duration})",
                description=summary_result["summary"],
                color=discord.Color.blue()
            )

            # Stats now in footer instead of field
            embed.set_footer(text=f"📊 {message_count} msgs • 👥 {participant_count} participants • ⏱️ {time_span} • Requested by {ctx.author.display_name}")

            # Edit the thinking message with the final response
            try:
                await thinking_message.edit(content=None, embed=embed)
                logger.info("Slash command: Successfully updated message with summary embed")
                
                # If the summary was split into multiple parts, send continuation messages
                if summary_result.get("is_split", False) and "continuation_parts" in summary_result:
                    logger.info(f"Sending {len(summary_result['continuation_parts'])} continuation parts")
                    
                    for i, part in enumerate(summary_result["continuation_parts"]):
                        # Create continuation embed
                        cont_embed = discord.Embed(
                            title=f"Channel Summary ({duration}) - Part {i+2}",
                            description=part,
                            color=discord.Color.blue()
                        )
                        
                        # Send as a separate message
                        await ctx.followup.send(embed=cont_embed, ephemeral=not public)
                        logger.info(f"Sent continuation part {i+2}")

            except Exception as e:
                logger.error(f"Slash command: Error updating message with summary: {e}")
                # Fallback - try sending a new message
                try:
                    await ctx.followup.send(content=None, embed=embed, ephemeral=not public)
                    logger.info("Slash command: Sent summary as a new message")
                except Exception as send_error:
                    logger.error(f"Slash command: Error sending fallback message: {send_error}")
            
        except Exception as e:
            # Make sure to cancel the loading task if it exists
            if 'loading_task' in locals():
                try:
                    if loading_task.cancel():
                        logger.info("Slash command error handler: Loading task was successfully cancelled")
                    await asyncio.wait_for(loading_task, timeout=1.0)
                except (asyncio.TimeoutError, asyncio.CancelledError, Exception) as task_error:
                    logger.error(f"Slash command error handler: Issue cancelling loading task: {task_error}")

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
                    await ctx.followup.send(embed=error_embed, ephemeral=not public)
            except Exception as send_error:
                logger.error(f"Slash command: Failed to send error message: {send_error}")
                # Last resort plain text fallback
                await ctx.followup.send(
                    "⚠️ Sorry, I encountered an error trying to generate the summary. Please try again later.",
                    ephemeral=not public
                )
    
    @discord.message_command(name="Summarize Channel")
    async def summarize_context_menu(self, ctx: discord.ApplicationContext, message: discord.Message):
        """Context menu command for summarizing a channel"""
        # Create a modal for duration selection
        modal = SummarizerDurationModal(title="Select Summary Duration")
        
        # Send the modal
        await ctx.send_modal(modal)
        
        # Wait for modal submission
        try:
            modal_interaction = await self.bot.wait_for(
                "modal_submit",
                check=lambda i: i.custom_id == "duration_modal" and i.user.id == ctx.author.id,
                timeout=60.0
            )
            
            # Get selected duration from modal
            selected_duration = modal.duration_select.values[0]
            
            # Defer response
            await modal_interaction.response.defer(ephemeral=True)
            
            # Show initial thinking message
            thinking_message = await modal_interaction.followup.send(
                "🔄 Thinking... I'm reviewing the messages and generating a summary.",
                ephemeral=True
            )

            # Parse duration and calculate time range
            time_delta = self.summarizer_service.parse_duration(selected_duration)
            look_back_time = datetime.now(timezone.utc) - time_delta

            # Show message about fetching messages
            await thinking_message.edit(content=f"🔍 Searching for messages since {look_back_time.strftime('%Y-%m-%d %H:%M:%S')} UTC...")

            # Fetch messages from the channel
            messages = await self._fetch_messages(ctx.channel, look_back_time)

            # Use a simple spinner animation for loading
            spinner_frames = ["⠋", "⠙", "⠹", "⠸", "⠼", "⠴", "⠦", "⠧", "⠇", "⠏"]
            loading_base = "Generating summary... "

            # Set an initial static message
            try:
                await thinking_message.edit(content=f"{loading_base} Please wait, this may take a minute.")
                logger.info("Context menu: Set static loading message")
            except Exception as e:
                logger.error(f"Context menu: Failed to set static loading message: {e}")

            # Define a stub task that does nothing (we're avoiding animation due to Discord rate limits)
            async def dummy_task():
                try:
                    await asyncio.sleep(60)  # Just wait until cancelled
                except asyncio.CancelledError:
                    logger.info("Context menu: Dummy task cancelled")
                    return

            # Create a task that doesn't actually edit messages
            loop = asyncio.get_event_loop()
            loading_task = loop.create_task(dummy_task())

            # Generate summary
            try:
                summary_result = self.summarizer_service.generate_summary(
                    messages=messages,
                    duration_str=selected_duration,
                    user_id=str(ctx.author.id),
                    channel_id=str(ctx.channel.id),
                    guild_id=str(ctx.guild.id)
                )

                # Cancel the loading task when done
                if loading_task.cancel():
                    logger.info("Context menu: Loading task was successfully cancelled")

                try:
                    # Wait for the task to cancel with timeout
                    await asyncio.wait_for(loading_task, timeout=1.0)
                except (asyncio.TimeoutError, asyncio.CancelledError, Exception):
                    pass
            except Exception as gen_error:
                # Handle summary generation error
                if loading_task.cancel():
                    logger.info("Context menu: Loading task was cancelled due to generation error")
                try:
                    await asyncio.wait_for(loading_task, timeout=1.0)
                except Exception:
                    pass
                logger.error(f"Context menu: Error generating summary: {gen_error}")
                raise  # Re-raise to be caught by the outer try/except
            
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

            # Create embed for response
            embed = discord.Embed(
                title=f"Channel Summary ({selected_duration})",
                description=summary_result["summary"],
                color=discord.Color.blue()
            )

            # Stats now in footer instead of field
            embed.set_footer(text=f"📊 {message_count} msgs • 👥 {participant_count} participants • ⏱️ {time_span} • Requested by {ctx.author.display_name}")

            # Edit the thinking message with the final response
            try:
                await thinking_message.edit(content=None, embed=embed)
                logger.info("Context menu: Successfully updated message with summary embed")
                
                # If the summary was split into multiple parts, send continuation messages
                if summary_result.get("is_split", False) and "continuation_parts" in summary_result:
                    logger.info(f"Context menu: Sending {len(summary_result['continuation_parts'])} continuation parts")
                    
                    for i, part in enumerate(summary_result["continuation_parts"]):
                        # Create continuation embed
                        cont_embed = discord.Embed(
                            title=f"Channel Summary ({selected_duration}) - Part {i+2}",
                            description=part,
                            color=discord.Color.blue()
                        )
                        
                        # Send as a separate message
                        await modal_interaction.followup.send(embed=cont_embed, ephemeral=True)
                        logger.info(f"Context menu: Sent continuation part {i+2}")
                    
            except Exception as e:
                logger.error(f"Context menu: Error updating message with summary: {e}")
            
        except asyncio.TimeoutError:
            await ctx.followup.send(
                "⌛ The duration selection timed out. Please try again.",
                ephemeral=True
            )
        except Exception as e:
            # Make sure to cancel the loading task if it exists
            if 'loading_task' in locals():
                try:
                    if loading_task.cancel():
                        logger.info("Context menu error handler: Loading task was successfully cancelled")
                    await asyncio.wait_for(loading_task, timeout=1.0)
                except (asyncio.TimeoutError, asyncio.CancelledError, Exception) as task_error:
                    logger.error(f"Context menu error handler: Issue cancelling loading task: {task_error}")

            logger.error(f"Error in context menu command: {e}")

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
                logger.error(f"Context menu: Failed to send error message: {send_error}")
                # Last resort plain text fallback
                await ctx.followup.send(
                    "⚠️ Sorry, I encountered an error trying to generate the summary. Please try again later.",
                    ephemeral=True
                )
    
    async def _fetch_messages(self, channel: discord.TextChannel, after_time: datetime) -> List[Dict[str, Any]]:
        """Fetch messages from a channel after a specific time
        
        Args:
            channel: Discord channel to fetch messages from
            after_time: Only fetch messages after this time
            
        Returns:
            List of message dictionaries with author, content, and timestamp
        """
        messages = []
        
        try:
            async for message in channel.history(after=after_time, limit=None):
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
                
            # Sort messages by timestamp (oldest first)
            messages.sort(key=lambda msg: msg["timestamp"])
            
            return messages
            
        except Exception as e:
            logger.error(f"Error fetching messages: {e}")
            return []


class SummarizerDurationModal(discord.ui.Modal):
    """Modal for selecting summary duration from context menu"""
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.custom_id = "duration_modal"
        
        # Add a select menu for duration options
        self.duration_select = discord.ui.Select(
            custom_id="duration_select",
            placeholder="Select duration to summarize",
            options=[
                discord.SelectOption(label="Last Hour", value="1h", description="Summarize the last hour"),
                discord.SelectOption(label="Last 24 Hours", value="24h", description="Summarize the last 24 hours", default=True),
                discord.SelectOption(label="Last 3 Days", value="3d", description="Summarize the last 3 days"),
                discord.SelectOption(label="Last Week", value="7d", description="Summarize the last week")
            ]
        )
        
        # Add the select menu to the modal
        self.add_item(self.duration_select)
    
    async def callback(self, interaction: discord.Interaction):
        """Callback for modal submission"""
        # The main logic is handled in the cog


def setup(bot):
    """Add the cog to the bot"""
    bot.add_cog(SummarizerCog(bot))