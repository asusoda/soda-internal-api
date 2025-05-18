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
        mode: discord.Option(
            str,
            "Choose summarization mode (default: duration)",
            required=False,
            choices=[
                "duration", 
                "timeline"
            ],
            default="duration"
        ),
        duration: discord.Option(
            str,
            "Time period to summarize (when using duration mode)",
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
        start_date: discord.Option(
            str,
            "Start date (YYYY-MM-DD) for timeline mode",
            required=False,
            default=None
        ),
        end_date: discord.Option(
            str,
            "End date (YYYY-MM-DD) for timeline mode",
            required=False,
            default=None
        )
    ):
        """Generate a summary of channel messages"""
        # Initial response to user - always ephemeral initially
        await ctx.defer(ephemeral=True)
        
        try:
            # Show initial thinking message
            thinking_message = await ctx.followup.send(
                "🔄 Thinking... I'm reviewing the messages and generating a summary.",
                ephemeral=True
            )

            # Calculate time range based on selected mode
            if mode == "duration":
                time_delta = self.summarizer_service.parse_duration(duration)
                look_back_time = datetime.now(timezone.utc) - time_delta
                display_range = duration
            else:  # timeline mode
                # Validate date inputs
                if not start_date or not end_date:
                    await thinking_message.edit(content="⚠️ Error: Both start_date and end_date are required for timeline mode.")
                    return
                
                try:
                    # Parse dates (assume input is in user's local timezone, convert to UTC)
                    start_datetime = datetime.strptime(f"{start_date} 00:00:00", "%Y-%m-%d %H:%M:%S").replace(tzinfo=timezone.utc)
                    end_datetime = datetime.strptime(f"{end_date} 23:59:59", "%Y-%m-%d %H:%M:%S").replace(tzinfo=timezone.utc)
                    
                    # Ensure end date is after start date
                    if end_datetime <= start_datetime:
                        await thinking_message.edit(content="⚠️ Error: End date must be after start date.")
                        return
                    
                    # Set variables for fetching messages
                    look_back_time = start_datetime
                    display_range = f"{start_date} to {end_date}"
                except ValueError:
                    await thinking_message.edit(content="⚠️ Error: Invalid date format. Please use YYYY-MM-DD.")
                    return

            # Show message about fetching messages
            await thinking_message.edit(content=f"🔍 Searching for messages from {look_back_time.strftime('%Y-%m-%d %H:%M:%S')} UTC...")

            # Fetch messages from the channel - pass end_time if in timeline mode
            if mode == "timeline":
                messages = await self._fetch_messages_in_range(ctx.channel, look_back_time, end_datetime)
            else:
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
                    duration_str=display_range,
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
                title=f"Channel Summary ({display_range})",
                description=summary_result["summary"],
                color=discord.Color.blue()
            )

            # Stats now in footer instead of field
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

            # Edit the thinking message with the final response
            try:
                await thinking_message.edit(content=None, embed=embed, view=view)
                logger.info("Slash command: Successfully updated message with summary embed")
                
                # If the summary was split into multiple parts, send continuation messages
                if summary_result.get("is_split", False) and "continuation_parts" in summary_result:
                    logger.info(f"Sending {len(summary_result['continuation_parts'])} continuation parts")
                    
                    for i, part in enumerate(summary_result["continuation_parts"]):
                        # Create continuation embed
                        cont_embed = discord.Embed(
                            title=f"Channel Summary ({display_range}) - Part {i+2}",
                            description=part,
                            color=discord.Color.blue()
                        )
                        
                        # Send as a separate message
                        await ctx.followup.send(embed=cont_embed, ephemeral=True)
                        logger.info(f"Sent continuation part {i+2}")

            except Exception as e:
                logger.error(f"Slash command: Error updating message with summary: {e}")
                # Fallback - try sending a new message
                try:
                    await ctx.followup.send(content=None, embed=embed, view=view, ephemeral=True)
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
                    await ctx.followup.send(embed=error_embed, ephemeral=True)
            except Exception as send_error:
                logger.error(f"Slash command: Failed to send error message: {send_error}")
                # Last resort plain text fallback
                await ctx.followup.send(
                    "⚠️ Sorry, I encountered an error trying to generate the summary. Please try again later.",
                    ephemeral=True
                )
    
    @discord.message_command(name="Summarize Channel")
    async def summarize_context_menu(self, ctx: discord.ApplicationContext, message: discord.Message):
        """Context menu command for summarizing a channel"""
        # Create a modal for duration selection
        modal = SummarizerDurationModal(title="Select Summary Options")
        
        # Send the modal
        await ctx.send_modal(modal)
        
        # Wait for modal submission
        try:
            modal_interaction = await self.bot.wait_for(
                "modal_submit",
                check=lambda i: i.custom_id == "duration_modal" and i.user.id == ctx.author.id,
                timeout=60.0
            )
            
            # Get selected options from modal
            selected_mode = modal.mode_select.values[0]
            selected_duration = modal.duration_select.values[0]
            start_date = modal.start_date.value
            end_date = modal.end_date.value
            
            # Defer response
            await modal_interaction.response.defer(ephemeral=True)
            
            # Show initial thinking message
            thinking_message = await modal_interaction.followup.send(
                "🔄 Thinking... I'm reviewing the messages and generating a summary.",
                ephemeral=True
            )

            # Calculate time range based on selected mode
            if selected_mode == "duration":
                time_delta = self.summarizer_service.parse_duration(selected_duration)
                look_back_time = datetime.now(timezone.utc) - time_delta
                display_range = selected_duration
                
                # Show message about fetching messages
                await thinking_message.edit(content=f"🔍 Searching for messages from {look_back_time.strftime('%Y-%m-%d %H:%M:%S')} UTC...")
                
                # Fetch messages
                messages = await self._fetch_messages(ctx.channel, look_back_time)
            else:  # timeline mode
                # Validate date inputs
                if not start_date or not end_date:
                    await thinking_message.edit(content="⚠️ Error: Both start date and end date are required for timeline mode.")
                    return
                
                try:
                    # Parse dates (assume input is in user's local timezone, convert to UTC)
                    start_datetime = datetime.strptime(f"{start_date} 00:00:00", "%Y-%m-%d %H:%M:%S").replace(tzinfo=timezone.utc)
                    end_datetime = datetime.strptime(f"{end_date} 23:59:59", "%Y-%m-%d %H:%M:%S").replace(tzinfo=timezone.utc)
                    
                    # Ensure end date is after start date
                    if end_datetime <= start_datetime:
                        await thinking_message.edit(content="⚠️ Error: End date must be after start date.")
                        return
                    
                    # Set variables for fetching messages
                    look_back_time = start_datetime
                    display_range = f"{start_date} to {end_date}"
                    
                    # Show message about fetching messages
                    await thinking_message.edit(content=f"🔍 Searching for messages from {start_date} to {end_date}...")
                    
                    # Fetch messages in date range
                    messages = await self._fetch_messages_in_range(ctx.channel, start_datetime, end_datetime)
                except ValueError:
                    await thinking_message.edit(content="⚠️ Error: Invalid date format. Please use YYYY-MM-DD.")
                    return

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
                    duration_str=display_range,
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
                title=f"Channel Summary ({display_range})",
                description=summary_result["summary"],
                color=discord.Color.blue()
            )

            # Stats now in footer instead of field
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
                            title=f"Channel Summary ({display_range}) - Part {i+2}",
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

    async def _fetch_messages_in_range(self, channel: discord.TextChannel, start_time: datetime, end_time: datetime) -> List[Dict[str, Any]]:
        """Fetch messages from a channel between two specific times
        
        Args:
            channel: Discord channel to fetch messages from
            start_time: Only fetch messages after this time
            end_time: Only fetch messages before this time
            
        Returns:
            List of message dictionaries with author, content, and timestamp
        """
        messages = []
        
        try:
            async for message in channel.history(after=start_time, before=end_time, limit=None):
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

    # Create a slash command for asking questions about chat
    @discord.slash_command(
        name="ask",
        description="Ask a specific question about channel messages",
        guild_ids=None  # This makes it global
    )
    async def ask_command(
        self,
        ctx: discord.ApplicationContext,
        question: discord.Option(
            str,
            "Your question about the conversation",
            required=True
        ),
        mode: discord.Option(
            str,
            "Choose search mode (default: duration)",
            required=False,
            choices=[
                "duration", 
                "timeline"
            ],
            default="duration"
        ),
        duration: discord.Option(
            str,
            "Time period to analyze (when using duration mode)",
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
        start_date: discord.Option(
            str,
            "Start date (YYYY-MM-DD) for timeline mode",
            required=False,
            default=None
        ),
        end_date: discord.Option(
            str,
            "End date (YYYY-MM-DD) for timeline mode",
            required=False,
            default=None
        )
    ):
        """Ask a specific question about channel messages"""
        # Initial response to user - always ephemeral initially
        await ctx.defer(ephemeral=True)
        
        try:
            # Show initial thinking message
            thinking_message = await ctx.followup.send(
                "🔄 Thinking... I'm reviewing the messages to answer your question.",
                ephemeral=True
            )

            # Calculate time range based on selected mode
            if mode == "duration":
                time_delta = self.summarizer_service.parse_duration(duration)
                look_back_time = datetime.now(timezone.utc) - time_delta
                display_range = duration
            else:  # timeline mode
                # Validate date inputs
                if not start_date or not end_date:
                    await thinking_message.edit(content="⚠️ Error: Both start_date and end_date are required for timeline mode.")
                    return
                
                try:
                    # Parse dates (assume input is in user's local timezone, convert to UTC)
                    start_datetime = datetime.strptime(f"{start_date} 00:00:00", "%Y-%m-%d %H:%M:%S").replace(tzinfo=timezone.utc)
                    end_datetime = datetime.strptime(f"{end_date} 23:59:59", "%Y-%m-%d %H:%M:%S").replace(tzinfo=timezone.utc)
                    
                    # Ensure end date is after start date
                    if end_datetime <= start_datetime:
                        await thinking_message.edit(content="⚠️ Error: End date must be after start date.")
                        return
                    
                    # Set variables for fetching messages
                    look_back_time = start_datetime
                    display_range = f"{start_date} to {end_date}"
                except ValueError:
                    await thinking_message.edit(content="⚠️ Error: Invalid date format. Please use YYYY-MM-DD.")
                    return

            # Show message about fetching messages
            await thinking_message.edit(content=f"🔍 Searching for messages from {look_back_time.strftime('%Y-%m-%d %H:%M:%S')} UTC...")

            # Fetch messages from the channel - pass end_time if in timeline mode
            if mode == "timeline":
                messages = await self._fetch_messages_in_range(ctx.channel, look_back_time, end_datetime)
            else:
                messages = await self._fetch_messages(ctx.channel, look_back_time)

            # Use a simple spinner animation for loading
            spinner_frames = ["⠋", "⠙", "⠹", "⠸", "⠼", "⠴", "⠦", "⠧", "⠇", "⠏"]
            loading_base = "Analyzing messages... "

            # Set an initial static message
            try:
                await thinking_message.edit(content=f"{loading_base} Please wait, this may take a minute.")
                logger.info("Ask command: Set static loading message")
            except Exception as e:
                logger.error(f"Ask command: Failed to set static loading message: {e}")

            # Define a stub task that does nothing (we're avoiding animation due to Discord rate limits)
            async def dummy_task():
                try:
                    await asyncio.sleep(60)  # Just wait until cancelled
                except asyncio.CancelledError:
                    logger.info("Ask command: Dummy task cancelled")
                    return

            # Create a task that doesn't actually edit messages
            loop = asyncio.get_event_loop()
            loading_task = loop.create_task(dummy_task())

            # Generate answer
            try:
                answer_result = self.summarizer_service.answer_question(
                    messages=messages,
                    question=question,
                    duration_str=display_range,
                    user_id=str(ctx.author.id),
                    channel_id=str(ctx.channel.id),
                    guild_id=str(ctx.guild.id)
                )

                # Cancel the loading task when done
                if loading_task.cancel():
                    logger.info("Ask command: Loading task was successfully cancelled")

                try:
                    # Wait for the task to cancel with timeout
                    await asyncio.wait_for(loading_task, timeout=1.0)
                except (asyncio.TimeoutError, asyncio.CancelledError, Exception):
                    pass
            except Exception as gen_error:
                # Handle answer generation error
                if loading_task.cancel():
                    logger.info("Ask command: Loading task was cancelled due to generation error")
                try:
                    await asyncio.wait_for(loading_task, timeout=1.0)
                except Exception:
                    pass
                logger.error(f"Ask command: Error generating answer: {gen_error}")
                raise  # Re-raise to be caught by the outer try/except
            
            # Get stats
            message_count = answer_result['message_count']

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
                title=f"Question: {question}",
                description=answer_result["answer"],
                color=discord.Color.green()
            )

            # Stats now in footer instead of field
            embed.set_footer(text=f"📊 {message_count} msgs • 👥 {participant_count} participants • ⏱️ {time_span} • Requested by {ctx.author.display_name}")
            
            # Create a view with the make public button
            view = discord.ui.View()
            make_public_button = discord.ui.Button(
                style=discord.ButtonStyle.secondary,
                label="Make Public",
                emoji="🌐",
                custom_id="make_answer_public"
            )
            
            # Define the callback for the button
            async def make_public_callback(interaction):
                if interaction.user.id != ctx.author.id:
                    await interaction.response.send_message("Only the user who asked the question can make it public.", ephemeral=True)
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

            # Edit the thinking message with the final response
            try:
                await thinking_message.edit(content=None, embed=embed, view=view)
                logger.info("Ask command: Successfully updated message with answer embed")
                
                # If the answer was split into multiple parts, send continuation messages
                if answer_result.get("is_split", False) and "continuation_parts" in answer_result:
                    logger.info(f"Sending {len(answer_result['continuation_parts'])} continuation parts")
                    
                    for i, part in enumerate(answer_result["continuation_parts"]):
                        # Create continuation embed
                        cont_embed = discord.Embed(
                            title=f"Answer (continued part {i+2})",
                            description=part,
                            color=discord.Color.green()
                        )
                        
                        # Send as a separate message
                        await ctx.followup.send(embed=cont_embed, ephemeral=True)
                        logger.info(f"Ask command: Sent continuation part {i+2}")
            except Exception as e:
                logger.error(f"Ask command: Error updating message with answer: {e}")
                # Fallback - try sending a new message
                try:
                    await ctx.followup.send(content=None, embed=embed, view=view, ephemeral=True)
                    logger.info("Ask command: Sent answer as a new message")
                except Exception as send_error:
                    logger.error(f"Ask command: Error sending fallback message: {send_error}")
            
        except Exception as e:
            # Make sure to cancel the loading task if it exists
            if 'loading_task' in locals():
                try:
                    if loading_task.cancel():
                        logger.info("Ask command error handler: Loading task was successfully cancelled")
                    await asyncio.wait_for(loading_task, timeout=1.0)
                except (asyncio.TimeoutError, asyncio.CancelledError, Exception) as task_error:
                    logger.error(f"Ask command error handler: Issue cancelling loading task: {task_error}")

            logger.error(f"Error in ask command: {e}")

            # Create an error embed with Markdown formatting
            error_embed = discord.Embed(
                title="Answer Generation Error",
                description="""# Error Answering Question ⚠️

I encountered an unexpected error while processing your request.

## Technical Details

An error occurred during the question answering process.

## Next Steps

- Try again with a shorter time period
- Try simplifying your question
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
                logger.error(f"Ask command: Failed to send error message: {send_error}")
                # Last resort plain text fallback
                await ctx.followup.send(
                    "⚠️ Sorry, I encountered an error trying to answer your question. Please try again later.",
                    ephemeral=True
                )

    @discord.slash_command(
        name="help",
        description="Show help and instructions for the summarizer bot",
        guild_ids=None
    )
    async def help_command(self, ctx: discord.ApplicationContext):
        """Show help and instructions for the summarizer bot"""
        help_text = (
            """
**/summarize**
Summarize recent channel messages. You can use this command to get a concise summary of recent activity in the current channel.

**Options:**
- `mode`: Choose between `duration` (default) or `timeline`.
- `duration`: For duration mode, pick a time period (e.g., 1h, 24h, 1d, 3d, 7d, 1w).
- `start_date`/`end_date`: For timeline mode, specify the date range (YYYY-MM-DD).

**/ask**
Ask a specific question about the channel's messages. The bot will analyze the chat history and answer your question, citing relevant messages.

**Options:**
- `question`: The question you want to ask about the chat.
- `mode`, `duration`, `start_date`, `end_date`: Same as `/summarize`.

**Requirements:**
- The bot must have permission to read message history in the channel.
- For timeline mode, both `start_date` and `end_date` are required and must be in YYYY-MM-DD format.
- For duration mode, only the `duration` option is needed.

**Tips:**
- Use `/summarize` to quickly catch up on what you missed in a channel.
- Use `/ask` to get answers to specific questions, such as "Who made the final decision?" or "What was the main topic on Monday?"
- Both commands support citations: click on citation links in the summary or answer to jump to the original message.
- If your summary or answer is too long, it will be split into multiple messages automatically.
- All results are private by default. Use the "Make Public" button to share with the channel.

For more details, see the project README or contact the bot maintainer.
"""
        )
        embed = discord.Embed(
            title="SoDA Summarizer Bot Help",
            description=help_text,
            color=discord.Color.purple()
        )
        # Create a view with the make public button
        view = discord.ui.View()
        make_public_button = discord.ui.Button(
            style=discord.ButtonStyle.secondary,
            label="Make Public",
            emoji="🌐",
            custom_id="make_help_public"
        )
        
        # Define the callback for the button
        async def make_public_callback(interaction):
            if interaction.user.id != ctx.author.id:
                await interaction.response.send_message("Only the user who requested help can make it public.", ephemeral=True)
                return
            
            # Send the same embed as a public message directly
            await ctx.channel.send(embed=embed)
            
            # Delete the ephemeral message - for help, we need to use interaction.message
            try:
                # Acknowledge the interaction without sending a visible message
                await interaction.response.defer(ephemeral=True)
                await interaction.message.delete()
            except Exception as e:
                logger.error(f"Failed to delete ephemeral help message: {e}")
        
        make_public_button.callback = make_public_callback
        view.add_item(make_public_button)
        
        await ctx.respond(embed=embed, view=view, ephemeral=True)


class SummarizerDurationModal(discord.ui.Modal):
    """Modal for selecting summary duration from context menu"""
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.custom_id = "duration_modal"
        
        # Add mode selector
        self.mode_select = discord.ui.Select(
            custom_id="mode_select",
            placeholder="Select summary mode",
            options=[
                discord.SelectOption(label="Duration-based", value="duration", description="Summarize based on time period", default=True),
                discord.SelectOption(label="Timeline", value="timeline", description="Summarize between specific dates")
            ]
        )
        
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
        
        # Add start date input for timeline mode
        self.start_date = discord.ui.TextInput(
            label="Start Date (YYYY-MM-DD)",
            custom_id="start_date",
            placeholder="e.g., 2025-05-01",
            required=False,
            style=discord.TextInputStyle.short
        )
        
        # Add end date input for timeline mode
        self.end_date = discord.ui.TextInput(
            label="End Date (YYYY-MM-DD)",
            custom_id="end_date",
            placeholder="e.g., 2025-05-10",
            required=False,
            style=discord.TextInputStyle.short
        )
        
        # Add instructions text
        self.instructions = discord.ui.TextInput(
            label="Instructions",
            custom_id="instructions",
            value="Choose either duration-based or timeline mode. For timeline, enter both dates.",
            required=False,
            style=discord.TextInputStyle.paragraph
        )
        self.instructions.disabled = True
        
        # Add all items to the modal
        self.add_item(self.mode_select)
        self.add_item(self.duration_select)
        self.add_item(self.start_date)
        self.add_item(self.end_date)
        self.add_item(self.instructions)
    
    async def callback(self, interaction: discord.Interaction):
        """Callback for modal submission"""
        # The main logic is handled in the cog


def setup(bot):
    """Add the cog to the bot"""
    bot.add_cog(SummarizerCog(bot))