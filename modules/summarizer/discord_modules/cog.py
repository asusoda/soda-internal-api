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
        timeframe: discord.Option(
            str,
            "Time period to summarize (e.g., '3 days', 'last week', 'January 1 to January 15')",
            required=False,
            default="24h"
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

            # First try to extract timeframe from the parameter using the same
            # extraction logic as the /ask command
            extracted_timeframe = self.summarizer_service.extract_timeframe_from_text(timeframe)
            
            # If we successfully extracted a standard timeframe, use that
            if extracted_timeframe:
                logger.info(f"Extracted timeframe from parameter: '{extracted_timeframe}'")
                timeframe_to_parse = extracted_timeframe
            else:
                # Otherwise use the original timeframe parameter
                timeframe_to_parse = timeframe
                
            # Check if the timeframe might contain multiple time references
            if timeframe and (" and " in timeframe.lower() or "," in timeframe):
                logger.warning(f"Timeframe might contain multiple time references: '{timeframe}'")
                logger.warning("Only the first detected reference will be used")
            
            # Parse the timeframe using natural language processing
            try:
                start_time, end_time, display_range = self.summarizer_service.parse_date_range(timeframe_to_parse)
                
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

            # Show message about fetching messages
            await thinking_message.edit(content=f"🔍 Searching for messages from {look_back_time.strftime('%Y-%m-%d %H:%M:%S')} UTC...")

            # Fetch messages from the channel - pass end_time if in timeline mode (specific date range)
            if end_datetime:
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
            # Include timespan information in the footer
            timespan_info = f"{start_time.strftime('%Y-%m-%d')} to {datetime.now().strftime('%Y-%m-%d')}" if not end_time else f"{start_time.strftime('%Y-%m-%d')} to {end_time.strftime('%Y-%m-%d')}"
            embed.set_footer(text=f"📊 {message_count} msgs • 👥 {participant_count} participants • ⏱️ {time_span} • 📅 {timespan_info} • Requested by {ctx.author.display_name}")
            
            # Create a view with the make public button
            view = discord.ui.View()
            make_public_button = discord.ui.Button(
                style=discord.ButtonStyle.secondary,
                label="Make Public",
                emoji="🌐",
                custom_id="make_summary_public"
            )
            
            # Keep track of all ephemeral message IDs for deletion
            ephemeral_message_ids = []
            ephemeral_embeds = []
            
            # Define the callback for the button
            async def make_public_callback(interaction):
                if interaction.user.id != ctx.author.id:
                    await interaction.response.send_message("Only the user who requested the summary can make it public.", ephemeral=True)
                    return
                
                # Acknowledge the interaction without sending a visible message
                await interaction.response.defer(ephemeral=True)
                
                # Send the main embed as a public message
                await ctx.channel.send(embed=embed)
                
                # Send all continuation parts as public messages, if any exist
                if summary_result.get("is_split", False) and "continuation_parts" in summary_result:
                    for i, part in enumerate(summary_result["continuation_parts"]):
                        # Create continuation embed
                        cont_embed = discord.Embed(
                            title=f"Channel Summary ({display_range}) - Part {i+2}",
                            description=part,
                            color=discord.Color.blue()
                        )
                        # Add the same footer
                        cont_embed.set_footer(text=embed.footer.text)
                        # Send publicly
                        await ctx.channel.send(embed=cont_embed)
                
                # Try to delete all ephemeral messages (main and continuations)
                try:
                    await thinking_message.delete()
                except Exception as e:
                    logger.error(f"Failed to delete main ephemeral message: {e}")
            
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
                        
                        # Add the same footer to all continuation parts
                        cont_embed.set_footer(text=embed.footer.text)
                        
                        # Send as a separate message with the same view containing the button
                        await ctx.followup.send(embed=cont_embed, ephemeral=True, view=view)
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
        description="Ask a specific question about channel messages (include timeframe in your question)",
        guild_ids=None  # This makes it global
    )
    async def ask_command(
        self,
        ctx: discord.ApplicationContext,
        question: discord.Option(
            str,
            "Your question about the conversation (include timeframe like 'last week' in your question)",
            required=True
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

            # Extract timeframe information from the question text using our method
            extracted_timeframe = self.summarizer_service.extract_timeframe_from_text(question)
            
            # If we extracted a timeframe from the question, use it
            if extracted_timeframe:
                timeframe = extracted_timeframe
                logger.info(f"Extracted timeframe from question: '{extracted_timeframe}'")
            else:
                # Default to 24h if no timeframe was extracted
                timeframe = "24h"
                logger.info(f"No timeframe found in question, using default: 24h")
                
            # If the question contains multiple time references, log a warning
            if " and " in question.lower() or "," in question:
                logger.warning(f"Question might contain multiple time references: '{question}'")
                logger.warning(f"Only using the first detected reference: '{timeframe}'")
                # In the future, we could enhance this to handle multiple time references
            
            # Parse the timeframe using natural language processing
            try:
                start_time, end_time, display_range = self.summarizer_service.parse_date_range(timeframe)
                
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

            # Show message about fetching messages
            await thinking_message.edit(content=f"🔍 Searching for messages from {look_back_time.strftime('%Y-%m-%d %H:%M:%S')} UTC...")

            # Fetch messages from the channel - pass end_time if in timeline mode (specific date range)
            if end_datetime:
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
            # Include timespan information in the footer
            timespan_info = f"{start_time.strftime('%Y-%m-%d')} to {datetime.now().strftime('%Y-%m-%d')}" if not end_time else f"{start_time.strftime('%Y-%m-%d')} to {end_time.strftime('%Y-%m-%d')}"
            embed.set_footer(text=f"📊 {message_count} msgs • 👥 {participant_count} participants • ⏱️ {time_span} • 📅 {timespan_info} • Requested by {ctx.author.display_name}")
            
            # Create a view with the make public button
            view = discord.ui.View()
            make_public_button = discord.ui.Button(
                style=discord.ButtonStyle.secondary,
                label="Make Public",
                emoji="🌐",
                custom_id="make_answer_public"
            )
            
            # Keep track of all ephemeral message IDs for deletion
            ephemeral_message_ids = []
            ephemeral_embeds = []
            
            # Define the callback for the button
            async def make_public_callback(interaction):
                if interaction.user.id != ctx.author.id:
                    await interaction.response.send_message("Only the user who asked the question can make it public.", ephemeral=True)
                    return
                
                # Acknowledge the interaction without sending a visible message
                await interaction.response.defer(ephemeral=True)
                
                # Send the main embed as a public message directly
                await ctx.channel.send(embed=embed)
                
                # Send all continuation parts as public messages, if any exist
                if answer_result.get("is_split", False) and "continuation_parts" in answer_result:
                    for i, part in enumerate(answer_result["continuation_parts"]):
                        # Create continuation embed
                        cont_embed = discord.Embed(
                            title=f"Answer (continued part {i+2})",
                            description=part,
                            color=discord.Color.green()
                        )
                        # Add the same footer
                        cont_embed.set_footer(text=embed.footer.text)
                        # Send publicly
                        await ctx.channel.send(embed=cont_embed)
                
                # Delete the ephemeral message
                try:
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
                        
                        # Add the same footer to all continuation parts
                        cont_embed.set_footer(text=embed.footer.text)
                        
                        # Send as a separate message with the same view containing the button
                        await ctx.followup.send(embed=cont_embed, ephemeral=True, view=view)
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

**Usage:**
- `/summarize` - Summarizes the last 24 hours
- `/summarize 3 days` - Summarizes the last 3 days
- `/summarize last week` - Summarizes the past week
- `/summarize January 1 to January 15` - Summarizes a specific date range

**/ask**
Ask a specific question about the channel's messages. The bot will analyze the chat history and answer your question, citing relevant messages.

**Usage:**
- `/ask "Who made the decision about the website redesign?"` - Uses default 24h timeframe
- `/ask "What happened last month?"` - Analyzes messages from the last month
- `/ask "What did John say yesterday?"` - Analyzes messages from yesterday

**Natural Language Time Understanding:**
Both commands support natural language time expressions like:
- Time periods: "last week", "past 3 days", "last month", "previous year"
- Specific months: "last January", "this April"
- Date ranges: "January to February", "from December to January"
- Traditional formats: "24h", "3d", "1w" also still work

**Requirements:**
- The bot must have permission to read message history in the channel.

**Tips:**
- Use `/summarize` to quickly catch up on what you missed in a channel.
- Use `/ask` to get answers to specific questions, such as "Who made the final decision?" or "What was the main topic on Monday?"
- Include time references directly in your questions for `/ask` commands
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
            
            # Acknowledge the interaction without sending a visible message
            await interaction.response.defer(ephemeral=True)
            
            # Send the same embed as a public message directly
            await ctx.channel.send(embed=embed)
            
            # Delete the ephemeral message - for help, we need to use interaction.message
            try:
                await interaction.message.delete()
            except Exception as e:
                logger.error(f"Failed to delete ephemeral help message: {e}")
        
        make_public_button.callback = make_public_callback
        view.add_item(make_public_button)
        
        await ctx.respond(embed=embed, view=view, ephemeral=True)


def setup(bot):
    """Add the cog to the bot"""
    bot.add_cog(SummarizerCog(bot))