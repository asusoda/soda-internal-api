import os
import time
from google import genai
from google.genai import types
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional
from modules.utils.db import DBConnect
from modules.summarizer.models import SummarizerConfig, SummaryLog
import logging
from modules.utils.config import Config as AppConfig

# Get logger
logger = logging.getLogger(__name__)
# Get app config
config = AppConfig()

class SummarizerService:
    """
    Service class for the Summarizer module that handles integration with
    Gemini API for generating summaries of Discord channel messages.
    """
    
    def __init__(self):
        """Initialize the SummarizerService"""
        self.db_connect = DBConnect("sqlite:///./data/user.db")

        # Hardcode configuration settings instead of loading from DB
        self.model_name = "models/gemini-2.5-flash-preview-04-17"
        self.api_key = os.environ.get("GEMINI_API_KEY") or config.GEMINI_API_KEY
        self.temperature = 0.7
        self.max_tokens = 8192
        self.default_duration = "24h"
        self.enabled = True

        logger.info(f"Using hardcoded model: {self.model_name}")

        self._setup_gemini()
    
    # _load_config method removed - using hardcoded values instead
    
    def _setup_gemini(self):
        """Set up the Gemini API client"""
        if not self.api_key:
            logger.warning("Gemini API key not configured")
            self.gemini_client = None
            return

        try:
            # Initialize the client with the API key
            self.gemini_client = genai.Client(api_key=self.api_key)
            logger.info("Gemini client initialized")

            # We're using a hardcoded model name, so no need to check if it exists
            # Just log the model we're using
            logger.info(f"Using model: {self.model_name}")

        except Exception as e:
            logger.error(f"Failed to initialize Gemini client: {e}")
            self.gemini_client = None
    
    def get_config(self) -> Dict[str, Any]:
        """Get the current summarizer configuration"""
        # Return hardcoded config as a dictionary
        return {
            "model_name": self.model_name,
            "default_duration": self.default_duration,
            "max_tokens": self.max_tokens,
            "temperature": self.temperature,
            "enabled": self.enabled,
            "api_key": "*****" if self.api_key else None  # Hide the actual API key
        }

    def update_config(self, config_data: Dict[str, Any]) -> Dict[str, Any]:
        """Update the summarizer configuration (no-op with hardcoded values)"""
        # Log that we're ignoring this request
        logger.info("Config update requested but using hardcoded values - ignoring")

        # Just return the current config
        return self.get_config()
    
    def test_gemini_connection(self, test_text: str) -> str:
        """Test the connection to Gemini API"""
        if not self.gemini_client:
            raise Exception("Gemini client not initialized")

        try:
            # Use the new Google Genai API with hardcoded model
            response = self.gemini_client.models.generate_content(
                model=self.model_name,
                contents=f"Respond briefly to this message: {test_text}"
            )

            # Log the response for debugging
            logger.info(f"Test response type: {type(response)}")
            logger.info(f"Response structure: {response.model_dump_json(exclude_none=True)[:100]}...")

            # The new SDK has a simpler way to access the response text
            return response.text
        except Exception as e:
            logger.error(f"Error testing Gemini connection: {e}")
            return f"Error generating response: {str(e)}"
    
    def parse_duration(self, duration_str: str) -> timedelta:
        """Parse a duration string into a timedelta object
        
        Formats supported:
        - 1h, 24h: Hours
        - 1d, 3d, 7d: Days
        - 1w: Week
        """
        # Default to 24 hours if no duration provided
        if not duration_str:
            return timedelta(hours=24)
            
        try:
            # Parse the duration string
            unit = duration_str[-1].lower()
            value = int(duration_str[:-1])
            
            if unit == 'h':
                return timedelta(hours=value)
            elif unit == 'd':
                return timedelta(days=value)
            elif unit == 'w':
                return timedelta(weeks=value)
            else:
                # Invalid format, return default
                logger.warning(f"Invalid duration format: {duration_str}")
                return timedelta(hours=24)
        except (ValueError, IndexError):
            logger.warning(f"Could not parse duration: {duration_str}")
            return timedelta(hours=24)
    
    def generate_summary(self,
                         messages: List[Dict[str, Any]],
                         duration_str: str,
                         user_id: str,
                         channel_id: str,
                         guild_id: str) -> Dict[str, Any]:
        """Generate a summary of Discord messages using Gemini API

        Args:
            messages: List of Discord message objects with author, content, timestamp
            duration_str: Duration string (e.g., "24h", "1d")
            user_id: Discord user ID who requested the summary
            channel_id: Discord channel ID where the summary was requested
            guild_id: Discord guild/server ID

        Returns:
            Dictionary with summary text and metrics
        """
        # The code is checking if the `gemini_client` attribute of the current object is `None` or
        # empty. If it is `None` or empty, the condition will evaluate to `True`.
        if not self.gemini_client:
            raise Exception("Gemini client not initialized")

        if not messages:
            return {
                "summary": f"""# No Messages Found 🔎

I didn't find any messages in this channel for the specified period (`{duration_str}`).

## Options

- Try a longer time period
- Check if there are messages in this channel
- Try another channel""",
                "message_count": 0,
                "duration": duration_str,
                "error": False
            }

        # Log some info about the request
        logger.info(f"Summary request for channel {channel_id} - Found {len(messages)} messages over {duration_str}")

        db = next(self.db_connect.get_db())

        try:
            # Create log entry
            log_entry = SummaryLog(
                user_id=user_id,
                channel_id=channel_id,
                guild_id=guild_id,
                duration=duration_str,
                message_count=len(messages)
            )

            db.add(log_entry)
            db.commit()

            start_time = time.time()

            try:
                # Format messages for the prompt
                formatted_messages = ""
                citation_index = 1
                citation_map = {}
                
                for msg in messages:
                    author = msg.get("author", {}).get("name", "Unknown")
                    content = msg.get("content", "")
                    timestamp = msg.get("timestamp", "")
                    msg_id = msg.get("id", "")
                    jump_url = msg.get("jump_url", "")
                    
                    # Create a citation ID for this message
                    citation_id = f"[c{citation_index}]"
                    citation_map[citation_id] = jump_url
                    
                    # Add the message with citation ID
                    formatted_messages += f"{timestamp} | {author} {citation_id}: {content}\n\n"
                    citation_index += 1

                # Log the number of messages being summarized
                logger.info(f"Formatting {len(messages)} messages for summarization with citations")

                # Create prompt for Gemini
                prompt = f"""
                You are AVERY, a Discord bot that creates BRIEF summaries of chat activity. I am giving you Discord messages from the last {duration_str} to summarize.

                CRITICAL INSTRUCTIONS:
                1. Create a VERY CONCISE summary (max 300 words)
                2. Focus on the key points rather than including every detail
                3. NEVER respond with phrases like "no significant activity" - ALL messages are important
                4. Be extremely brief but informative
                5. Format in bulleted lists using dashes (-) for bullets
                6. Follow EXACTLY the header structure from the example below
                7. IMPORTANT: Include citations to reference specific messages using the citation format [cX] that appears after each message author's name

                Focus on:
                1. Participants involved (who was talking)
                2. Key topics discussed (what they talked about)
                3. Important arguments or decisions (what conclusions were reached)
                4. Action items or follow-ups needed (what needs to be done)
                5. Key messages that should be highlighted (specific important messages)

                Format the output EXACTLY like this example, using proper Markdown header levels:

                # Action Items ✨
                - **[Person responsible]:** [Action item description] [c1]
                - **[Person responsible]:** [Another action item if applicable] [c2]
                # Conversation Summary ✨
                ## Conversation Purpose
                [Brief description of meeting purpose]
                ## Key Takeaways
                - [First key takeaway from the conversation] [c3]
                - [Second key takeaway from the conversation] [c4]
                - [Third key takeaway if applicable] [c5]
                ## Topics
                ### [Topic Name]
                - [Detail about the first topic] [c6]
                - [Another point about the first topic] [c7]
                ### [Another Topic Name]
                - [Detail about the second topic] [c8]
                - [Another point about the second topic] [c9]

                IMPORTANT FORMATTING RULES:
                1. Use "# " for first-level headers ("Action Items ✨" and "Conversation Summary ✨")
                2. Use "## " for second-level headers ("Conversation Purpose", "Key Takeaways", and "Topics")
                3. Use "### " for third-level headers (each topic name under "Topics")
                4. Make sure there is a space after each # symbol
                5. Use dashes (-) for bullet points, NOT Unicode bullets or asterisks
                6. Include emoji (✨) ONLY for the two main section headers as shown
                7. ONLY use bold formatting (**text**) for assignee names in action items
                8. Maintain consistent indentation for bullet points
                9. For action items, format as a single bullet with the person's name in bold followed by a colon and the action item description
                10. ALWAYS include citation references in the format [cX] after important information to refer to the original messages
                11. Use citations [cX] to reference specific messages that support your summary points

                MESSAGES TO SUMMARIZE:
                {formatted_messages}
                """

                # Generate summary using the new Genai API
                try:
                    # Configure the generation parameters
                    generation_config = types.GenerateContentConfig(
                        temperature=self.temperature,
                        max_output_tokens=self.max_tokens,  # Using our hardcoded max tokens
                        top_p=0.8,
                        top_k=40
                    )

                    # Send request to Gemini API
                    response = self.gemini_client.models.generate_content(
                        model=self.model_name,  # Using our hardcoded model name
                        contents=prompt,
                        config=generation_config
                    )

                    # Log response details
                    logger.info(f"Gemini response type: {type(response)}")
                    logger.info(f"Response structure: {response.model_dump_json(exclude_none=True)[:100]}...")

                    # The new SDK makes it easy to get the text
                    summary = response.text.strip()
                    logger.info(f"Generated summary with {len(summary)} characters")

                    # Check for empty or very short summaries (less than 100 chars would indicate a problem)
                    if not summary or len(summary) < 100:
                        logger.warning(f"Gemini returned empty or very short summary: '{summary}' - this might indicate an issue with the API")
                        summary = """# Summary Generation Issue ⚠️

I encountered a problem generating a summary for this conversation. This is likely due to an issue with the AI service.

## Options

- Try again later when the service may be less busy
- Try requesting a shorter time period (fewer messages)"""
                    else:
                        # Parse and format citations
                        summary = self._parse_citations(summary, citation_map)
                        
                        # Split the summary if it's too long for Discord
                        if len(summary) > 4000:  # Using 4000 to leave some buffer
                            logger.info(f"Summary exceeds Discord's limit ({len(summary)} chars). Splitting into parts.")
                            summary_parts = self._split_summary_for_discord(summary)
                            # Return as multiple parts
                            return {
                                "summary": summary_parts[0],
                                "continuation_parts": summary_parts[1:],
                                "message_count": len(messages),
                                "duration": duration_str,
                                "completion_time": time.time() - start_time,
                                "error": False,
                                "is_split": True
                            }

                except Exception as api_error:
                    logger.error(f"Error in Gemini API call: {api_error}")
                    summary = """# API Error ⚠️

I encountered an error while trying to generate a summary. The AI service returned an error.

## Technical Details

Error type: API Connection Issue

## Next Steps

- Try again later
- Contact support if the issue persists"""

                completion_time = time.time() - start_time

                # Update log entry with success
                log_entry.completion_time = completion_time
                db.commit()

                return {
                    "summary": summary,
                    "message_count": len(messages),
                    "duration": duration_str,
                    "completion_time": completion_time,
                    "error": False,
                    "is_split": False
                }

            except Exception as e:
                # Log error
                logger.error(f"Error generating summary: {e}")

                # Update log entry with error
                log_entry.error = True
                log_entry.error_message = str(e)
                db.commit()

                return {
                    "summary": """# Error Generating Summary ⚠️

I encountered an unexpected error while processing your request.

## Technical Details

An error occurred during summary generation.

## Next Steps

- Try again with a shorter time period
- Contact support if the issue persists""",
                    "message_count": len(messages),
                    "duration": duration_str,
                    "error": True,
                    "error_message": str(e)
                }
        finally:
            db.close()


    # _parse_citations method to parse citations in the summary text
    def _parse_citations(self, text: str, citation_map: Dict[str, str]) -> str:
        """Parse and format citations in the summary text."""
        import re
        
        # First, find range citations like [c16-c19] and expand them
        range_pattern = r'\[c(\d+)-c(\d+)\]'
        
        def expand_range_citation(match):
            start = int(match.group(1))
            end = int(match.group(2)) + 1
            return ''.join(f'[c{i}]' for i in range(start, end))
        
        text = re.sub(range_pattern, expand_range_citation, text)
        
        # Find all grouped citations like [c1, c2, c3]
        grouped_citation_pattern = r'\[(c\d+(?:,\s*c\d+)*)\]'
        
        def replace_grouped_citations(match):
            citations_content = match.group(1)
            individual_citations = [c.strip() for c in citations_content.split(',')]
            return ''.join(f'[{c}]' for c in individual_citations)
        
        text = re.sub(grouped_citation_pattern, replace_grouped_citations, text)
        
        # Find citations without brackets like c1c2c3
        unbracket_pattern = r'(?<!\[)c(\d+)(?!\])'
        
        def add_brackets(match):
            return f'[c{match.group(1)}]'
        
        text = re.sub(unbracket_pattern, add_brackets, text)
        
        # Replace each citation with a hyperlink
        for citation_id, jump_url in citation_map.items():
            # Ensure we're looking for [cN]
            bracket_citation = citation_id if citation_id.startswith('[') else f'[{citation_id.strip("[]")}]'
            # Create hyperlink with brackets preserved
            hyperlink = f"[{bracket_citation}]({jump_url})"
            # Replace in text, being careful with the brackets
            text = text.replace(bracket_citation, hyperlink)
        
        return text

    def _split_summary_for_discord(self, summary: str) -> List[str]:
        """Split a long summary into multiple parts that fit within Discord's limits.
        
        Discord has a 4096 character limit for embed descriptions.
        This function tries to split at logical section boundaries (Markdown headers)
        and ensures each part is under the limit.
        
        Args:
            summary: The full summary text
            
        Returns:
            List of summary parts, each under 4000 characters
        """
        import re
        
        # Maximum size for each part (leaving some buffer)
        MAX_PART_SIZE = 4000
        
        # If the summary is already small enough, return it as a single part
        if len(summary) <= MAX_PART_SIZE:
            return [summary]
            
        # Try to split at main section headers (# or ##)
        parts = []
        header_pattern = re.compile(r'^#{1,2}\s', re.MULTILINE)
        
        # Find all section headers
        header_matches = list(header_pattern.finditer(summary))
        
        if len(header_matches) <= 1:
            # Not enough headers to split meaningfully, just split by size
            return self._split_by_size(summary, MAX_PART_SIZE)
            
        # Start with first part from beginning to first split point
        current_pos = 0
        current_part = ""
        
        for i in range(1, len(header_matches)):
            # Get the position of this header
            header_pos = header_matches[i].start()
            
            # Check if adding this section would exceed the limit
            section = summary[current_pos:header_pos]
            
            if len(current_part) + len(section) <= MAX_PART_SIZE:
                # Add this section to current part
                current_part += section
            else:
                # Current part is full, add it to parts and start a new one
                parts.append(current_part)
                current_part = section
            
            current_pos = header_pos
            
        # Add the last part from the last split point to the end
        last_section = summary[current_pos:]
        if len(current_part) + len(last_section) <= MAX_PART_SIZE:
            current_part += last_section
            parts.append(current_part)
        else:
            parts.append(current_part)
            parts.append(last_section)
            
        # Check if any part is still too long and split it further if needed
        final_parts = []
        for part in parts:
            if len(part) <= MAX_PART_SIZE:
                final_parts.append(part)
            else:
                # Split this part by size
                final_parts.extend(self._split_by_size(part, MAX_PART_SIZE))
                
        # Add part indicators to the parts
        for i in range(len(final_parts)):
            if i > 0:
                final_parts[i] = f"**(Part {i+1} continued)**\n\n{final_parts[i]}"
                
        return final_parts
        
    def _split_by_size(self, text: str, max_size: int) -> List[str]:
        """Split text by size, trying to split at paragraph boundaries
        
        Args:
            text: Text to split
            max_size: Maximum size for each part
            
        Returns:
            List of text parts
        """
        parts = []
        
        while text:
            if len(text) <= max_size:
                parts.append(text)
                break
                
            # Try to find a paragraph break within the limit
            split_pos = text[:max_size].rfind("\n\n")
            
            if split_pos == -1 or split_pos < max_size // 2:
                # No good paragraph break, try a line break
                split_pos = text[:max_size].rfind("\n")
                
            if split_pos == -1 or split_pos < max_size // 2:
                # No good line break either, just split at the limit
                split_pos = max_size
                
            parts.append(text[:split_pos])
            text = text[split_pos:].strip()
            
        return parts
