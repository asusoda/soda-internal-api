import os
import time
from google import genai
from google.genai import types
from datetime import datetime, timedelta, timezone
from typing import List, Dict, Any, Optional, Tuple, Union
from modules.summarizer.models import SummarizerConfig, SummaryLog
import logging
from modules.utils.config import Config as AppConfig
import dateparser
import re
from timefhuman import timefhuman
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type
from modules.summarizer.time_parsers import get_parser_registry, TimeParserBase

# Common time-related phrases for extraction - module-level constant to avoid recreation on each instance
TIME_PHRASES = [
    "last month", "past month", "previous month", 
    "last week", "past week", "previous week", 
    "last year", "past year", "previous year",
    "yesterday", "last night", "this month", 
    "this week", "this year", "today",
    "january", "february", "march", "april", 
    "may", "june", "july", "august", 
    "september", "october", "november", "december",
    "jan", "feb", "mar", "apr", "jun", "jul", "aug",
    "sep", "oct", "nov", "dec",
    "monday", "tuesday", "wednesday", "thursday", 
    "friday", "saturday", "sunday",
    "mon", "tue", "wed", "thu", "fri", "sat", "sun",
    "day", "week", "month", "year", "hour", "minute",
    "morning", "afternoon", "evening", "night",
    "past", "previous", "next", "last", "this", "coming"
]

# Get logger
logger = logging.getLogger(__name__)
# Get app config
config = AppConfig()

class SummarizerService:
    """
    Service class for the Summarizer module that handles integration with
    Gemini API for generating summaries of Discord channel messages.
    
    This service provides methods for generating summaries and answering questions
    about Discord channel conversations, with natural language date/time parsing
    capabilities.
    
    Key features:
    - Natural language time extraction from user questions
    - Date range parsing with timezone awareness
    - Message citation generation for traceability
    - Support for both duration-based and calendar-aligned date expressions
    - Long response splitting for Discord message limits
    """
    
    def __init__(self):
        self.model_name = "models/gemini-2.5-flash-preview-04-17"
        self.api_key = os.environ.get("GEMINI_API_KEY") or config.GEMINI_API_KEY
        self.temperature = 0.7
        self.max_tokens = 8192
        self.default_duration = "24h"
        self.enabled = True

        # Initialize the parser registry
        self.parser_registry = get_parser_registry()

        logger.info(f"Using hardcoded model: {self.model_name}")
        logger.info(f"Initialized {len(self.parser_registry)} time parsers")

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
        """Test the connection to Gemini API with automatic retries"""
        if not self.gemini_client:
            raise Exception("Gemini client not initialized")

        try:
            # Use the retry-enabled method to make the API call
            response = self._generate_test_content_with_retry(test_text)
            
            # Log the response for debugging
            logger.info(f"Test response type: {type(response)}")
            logger.info(f"Response structure: {response.model_dump_json(exclude_none=True)[:100]}...")

            # The new SDK has a simpler way to access the response text
            return response.text
        except Exception as e:
            logger.error(f"Error testing Gemini connection after retries: {e}")
            return f"Error generating response after multiple retry attempts: {str(e)}"
            
    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=1, max=10))
    def _generate_test_content_with_retry(self, test_text: str):
        """Make a test request to Gemini API with retries"""
        logger.info("Making test Gemini API request with retries enabled")
        return self.gemini_client.models.generate_content(
            model=self.model_name,
            contents=f"Respond briefly to this message: {test_text}"
        )
    
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
    
    def extract_timeframe_from_text(self, text: str) -> Optional[str]:
        """Extract time-related expressions from natural language text.
        
        This method uses the parser registry to extract time expressions from text.
        Each parser attempts to extract a timeframe, and the first successful extraction is returned.
        
        Args:
            text: Text to analyze for time expressions
            
        Returns:
            Extracted time expression or None if no valid expression found
        """
        if not text:
            return None
        
        # Clean the text for processing
        clean_text = text.replace('?', '').strip()
        text_lower = clean_text.lower()
        
        # Special case for 'how does this system work' type phrases
        if text_lower.startswith('how') and ('work' in text_lower or 'system' in text_lower):
            return None
        
        # Special case handling for range expressions
        # Handle "what happened [last] weekday to weekday"
        if 'what happened' in text_lower or 'last' in text_lower:
            # Check for weekday range pattern
            weekday_names = ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"]
            weekday_pattern = '|'.join(weekday_names)
            range_match = re.search(
                f"(what happened |)(last |)(({weekday_pattern})\\s+to\\s+({weekday_pattern}))", 
                text_lower
            )
            
            if range_match:
                is_last = bool(range_match.group(2))
                extracted_range = range_match.group(3)
                if is_last:
                    return f"last {extracted_range}"
                else:
                    return extracted_range
            
            # Check for month range pattern
            month_names = ["january", "february", "march", "april", "may", "june", "july", 
                          "august", "september", "october", "november", "december"]
            month_pattern = '|'.join(month_names)
            month_range_match = re.search(
                f"(what happened |)(last |)(({month_pattern})\\s+to\\s+({month_pattern}))",
                text_lower
            )
            
            if month_range_match:
                is_last = bool(month_range_match.group(2))
                extracted_range = month_range_match.group(3)
                if is_last:
                    return f"last {extracted_range}"
                else:
                    return extracted_range
        
        # Try each parser in order until one successfully extracts a timeframe
        for parser in self.parser_registry:
            timeframe = parser.extract_timeframe(clean_text)
            if timeframe:
                logger.info(f"Extracted timeframe '{timeframe}' using {parser.__class__.__name__}")
                return timeframe
                
        # If all parsers fail, check if it contains any time-related keywords
        # This is a fallback to the previous implementation's behavior
        contains_time_keyword = False
        for phrase in TIME_PHRASES:
            if phrase in text_lower:
                contains_time_keyword = True
                break
                
        if contains_time_keyword:
            for phrase in TIME_PHRASES:
                if phrase in text_lower:
                    pattern = r'(\S+\s+){0,3}' + re.escape(phrase) + r'(\s+\S+){0,3}'
                    match = re.search(pattern, text_lower)
                    if match:
                        time_context = match.group(0).strip()
                        # Try dateparser as a last resort
                        try:
                            parsed = dateparser.parse(time_context, settings={'RELATIVE_BASE': datetime.now()})
                            if parsed:
                                return parsed.strftime("%Y-%m-%d")
                        except Exception:
                            pass
                        return time_context
        
        # No valid timeframe found
        return None

    def parse_date_range(self, text: str, reference_date: Optional[datetime] = None) -> Tuple[datetime, Optional[datetime], str]:
        """Parse natural language date/time expressions into a start and end datetime.
        
        This method uses a registry of parser objects to handle different time expressions.
        Parsers are tried in order of registration until one successfully parses the input.
        It returns timezone-aware datetime objects for the parsed time range.
        
        Args:
            text: Natural language text describing a time period
            reference_date: Optional reference date to use for relative expressions.
                           If not provided, the current date/time is used.
                 
        Returns:
            Tuple containing:
            - start_time: The parsed start time as a datetime object (timezone-aware)
            - end_time: The parsed end time as a datetime object, or None for duration-based queries
            - display_range: A string representation of the time range for display purposes
            
        Note on timezones: 
        - All returned datetime objects are timezone-aware (using timezone.utc)
        - Local time is used as the reference point for parsing relative expressions if no reference_date is provided
        """
        # Default to 24 hours if no text provided
        if not text or text.strip() == "":
            end_time = datetime.now(timezone.utc)
            start_time = end_time - timedelta(hours=24)
            return start_time, None, "24h (default)"
        
        # Clean the input text
        cleaned_text = text.strip()
        
        # Use the provided reference date or default to current time
        if reference_date is None:
            reference_date = datetime.now()
            
        # Ensure reference_date has timezone info
        if reference_date.tzinfo is None:
            reference_date = reference_date.replace(tzinfo=timezone.utc)
        
        # Try each parser in order until one successfully parses the input
        for parser in self.parser_registry:
            if parser.can_parse(cleaned_text):
                result = parser.parse_date_range(cleaned_text, reference_date)
                if result:
                    logger.info(f"Parsed '{cleaned_text}' using {parser.__class__.__name__}")
                    return result
        
        # Fallback to timefhuman for more complex expressions
        return self._parse_with_timefhuman(cleaned_text, reference_date)
    
    def _parse_with_timefhuman(self, text: str, reference_date: Optional[datetime] = None) -> Tuple[datetime, Optional[datetime], str]:
        """Parse more complex date ranges using timefhuman library.
        
        This is a fallback method used when our specialized parsers can't handle the input.
        
        Args:
            text: Text to parse
            reference_date: Optional reference date to use for relative expressions.
                           If not provided, the current date/time is used.
            
        Returns:
            Tuple of (start_time, end_time, display_range)
        """
        # Use the provided reference date or default to current time
        local_now = reference_date if reference_date is not None else datetime.now()
        logger.debug(f"Using reference time for timefhuman: {local_now}")
        
        try:
            # Let timefhuman process the text (handles a wide range of formats)
            parsed = timefhuman(text, now=local_now)
            
            # Process timefhuman's results
            if parsed and parsed != []:
                logger.info(f"Timefhuman extracted: {parsed}")
                
                # Handle date ranges (list of tuples)
                if isinstance(parsed, list) and len(parsed) > 0 and isinstance(parsed[0], tuple):
                    start, end = parsed[0]
                    logger.info(f"Date range: {start} to {end}")
                    
                    # Ensure timezone awareness
                    if start.tzinfo is None:
                        start = start.replace(tzinfo=timezone.utc)
                    if end.tzinfo is None:
                        end = end.replace(tzinfo=timezone.utc)
                        
                    # Make end time inclusive (end of day)
                    if end.hour == 0 and end.minute == 0 and end.second == 0:
                        end = end.replace(hour=23, minute=59, second=59)
                        
                    # Create a display format
                    display_range = f"from {start.strftime('%Y-%m-%d')} to {end.strftime('%Y-%m-%d')}"
                    
                    return start, end, display_range
                
                # Handle nested lists [[date1, date2]]
                elif isinstance(parsed, list) and len(parsed) > 0 and isinstance(parsed[0], list):
                    start = parsed[0][0]
                    end = parsed[0][-1]
                    
                    # Ensure timezone awareness
                    if start.tzinfo is None:
                        start = start.replace(tzinfo=timezone.utc)
                    if end.tzinfo is None:
                        end = end.replace(tzinfo=timezone.utc)
                        
                    # Make end time inclusive (end of day)
                    if end.hour == 0 and end.minute == 0 and end.second == 0:
                        end = end.replace(hour=23, minute=59, second=59)
                        
                    # Create a human-readable display format
                    display_range = f"{start.strftime('%Y-%m-%d')} to {end.strftime('%Y-%m-%d')}"
                    
                    logger.info(f"Parsed date list: {start} to {end}")
                    return start, end, display_range
                
                # Simple list of dates [date1, date2]
                elif isinstance(parsed, list) and len(parsed) >= 1:
                    if len(parsed) >= 2:
                        # Multiple dates - treat as range
                        start, end = parsed[0], parsed[-1]
                    else:
                        # Single date - use the same date for start and end
                        start = end = parsed[0]
                    
                    # Ensure timezone awareness
                    if start.tzinfo is None:
                        start = start.replace(tzinfo=timezone.utc)
                    if end.tzinfo is None:
                        end = end.replace(tzinfo=timezone.utc)
                    
                    # Make end time inclusive (end of day)
                    if end.hour == 0 and end.minute == 0 and end.second == 0:
                        end = end.replace(hour=23, minute=59, second=59)
                    
                    # Create an appropriate display format
                    if start.date() == end.date():
                        display_range = start.strftime("%Y-%m-%d")
                    else:
                        display_range = f"{start.strftime('%Y-%m-%d')} to {end.strftime('%Y-%m-%d')}"
                    
                    return start, end, display_range
                
                # Single datetime
                elif isinstance(parsed, datetime):
                    dt = parsed
                    
                    # Ensure timezone awareness
                    if dt.tzinfo is None:
                        dt = dt.replace(tzinfo=timezone.utc)
                    
                    # Handle full day
                    if dt.hour == 0 and dt.minute == 0 and dt.second == 0:
                        return dt, dt.replace(hour=23, minute=59, second=59), dt.strftime("%Y-%m-%d")
                    else:
                        # Handle specific time as 24h window
                        return dt - timedelta(hours=24), dt, f"24 hours ending {dt.strftime('%Y-%m-%d %H:%M')}"
                
        except Exception as e:
            logger.debug(f"Timefhuman parsing failed: {e}")
            
            # Try dateparser as a last resort
            try:
                # Use the provided reference date for dateparser as well
                relative_base = reference_date if reference_date is not None else datetime.now()
                parsed = dateparser.parse(text, settings={'RELATIVE_BASE': relative_base})
                if parsed:
                    if parsed.tzinfo is None:
                        parsed = parsed.replace(tzinfo=timezone.utc)
                    
                    if parsed.hour == 0 and parsed.minute == 0:
                        # Full day
                        return parsed, parsed.replace(hour=23, minute=59, second=59), parsed.strftime("%Y-%m-%d")
                    else:
                        # 24h window
                        return parsed - timedelta(hours=24), parsed, f"24h ending {parsed.strftime('%Y-%m-%d %H:%M')}"
            except Exception as dateparser_error:
                logger.debug(f"Dateparser also failed: {dateparser_error}")
        
        # Default to 24h if all parsing attempts fail
        # Use the reference date as the end time if provided
        if reference_date is not None:
            end_time = reference_date.replace(tzinfo=timezone.utc) if reference_date.tzinfo is None else reference_date
        else:
            end_time = datetime.now(timezone.utc)
            
        start_time = end_time - timedelta(hours=24)
        
        logger.info(f"All parsing methods failed for: '{text}'. Using 24h default.")
        return start_time, None, "24h (default)"
    
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
        if not self.gemini_client:
            raise Exception("Gemini client not initialized")
            
        start_time = time.time()
        
        # Check if there are any messages to summarize
        if not messages:
            return {
                "summary": f"I didn't find any messages in this channel for the specified period (`{duration_str}`). It's possible that the channel was inactive during this time or only contained bot messages (which are excluded from summaries).",
                "message_count": 0,
                "duration": duration_str,
                "completion_time": 0,
                "is_split": False
            }
            
        logger.info(f"Generating summary for {len(messages)} messages over {duration_str}")
        
        # Real implementation for production use
        try:
            # Prepare message data for summary
            conversation_text = ""
            citation_map = {}
            citation_counter = 1
            
            for msg in messages:
                # Format the message with a citation
                citation_id = f"c{citation_counter}"
                citation_map[citation_id] = msg["jump_url"]
                
                message_text = f"{msg['author']['name']}: {msg['content']} [{citation_id}]\n"
                conversation_text += message_text
                
                citation_counter += 1
            
            # Build the prompt for Gemini with instructions for formatting and citation requirements
            prompt = f"""
You are AVERY, a Discord bot that creates BRIEF summaries of chat activity. I am giving you Discord messages to summarize.

Summary Time Range: {duration_str}

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
{conversation_text}
"""
            
            # Set up generation config with appropriate parameters
            generation_config = types.GenerationConfig(
                temperature=self.temperature,
                max_output_tokens=self.max_tokens
            )
            
            # Call Gemini API with the constructed prompt
            try:
                response = self._generate_content_with_retry(
                    model=self.model_name,
                    contents=prompt,
                    generation_config=generation_config
                )
                
                # Extract the summary text from the response
                summary_text = response.text
                logger.info(f"Successfully generated summary with Gemini API")
                
            except Exception as api_error:
                logger.error(f"Error calling Gemini API: {api_error}")
                # Create a fallback response in case of API failure
                authors = list(set([msg['author']['name'] for msg in messages]))
                summary_text = f"Unable to generate summary due to an API error. The conversation involved {', '.join(authors)}. Please try again later."
            
            # Process and format citations
            formatted_summary = self._parse_citations(summary_text, citation_map)
            
            # Split long responses if needed
            is_split = False
            continuation_parts = []
            if len(formatted_summary) > 4000:
                logger.info("Summary exceeds Discord embed limit, splitting...")
                result = self._split_long_response(formatted_summary)
                formatted_summary = result["main_part"]
                continuation_parts = result["continuation_parts"]
                is_split = True
                
            # Calculate completion time
            completion_time = time.time() - start_time
            logger.info(f"Summary generation completed in {completion_time:.2f} seconds")
            
            # Return the result
            result = {
                "summary": formatted_summary,
                "message_count": len(messages),
                "duration": duration_str,
                "completion_time": completion_time,
                "is_split": is_split
            }
            
            if is_split:
                result["continuation_parts"] = continuation_parts
                
            return result
            
        except Exception as e:
            logger.error(f"Error generating summary: {e}")
            raise
            
    def answer_question(self,
                    messages: List[Dict[str, Any]],
                    question: str,
                    duration_str: str,
                    user_id: str,
                    channel_id: str,
                    guild_id: str) -> Dict[str, Any]:
        """Answer a specific question about Discord messages using Gemini API

        Args:
            messages: List of Discord message objects with author, content, timestamp
            question: User's question about the conversation
            duration_str: Duration string (e.g., "24h", "1d")
            user_id: Discord user ID who asked the question
            channel_id: Discord channel ID where the question was asked
            guild_id: Discord guild/server ID

        Returns:
            Dictionary with answer text and metrics
        """
        if not self.gemini_client:
            raise Exception("Gemini client not initialized")
            
        start_time = time.time()
        
        # Check if there are any messages to analyze
        if not messages:
            return {
                "answer": f"I didn't find any messages in this channel for the specified period (`{duration_str}`). It's possible that the channel was inactive during this time or only contained bot messages (which are excluded from my analysis).",
                "message_count": 0,
                "duration": duration_str,
                "completion_time": 0,
                "is_split": False
            }
            
        logger.info(f"Answering question based on {len(messages)} messages over {duration_str}")
        
        # Check if we're in testing mode
        if 'testing' in channel_id:
            # Testing mode - return a simplified response without calling Gemini
            citation_map = {}
            for i, msg in enumerate(messages):
                citation_id = f"c{i+1}"
                citation_map[citation_id] = msg["jump_url"]
                
            # Create a general purpose mock answer with citations
            # Use first 3 message IDs for citations, or fewer if not enough messages
            citation_ids = [f"c{i+1}" for i in range(min(3, len(messages)))]
            citations_str = ", ".join([f"[{cid}]" for cid in citation_ids]) if citation_ids else ""
            
            answer_text = f"This is a testing mode answer to your question: '{question}'. Based on the conversation between {len(set([msg['author']['name'] for msg in messages]))} participants, I can reference these messages: {citations_str}. This answer is generated in testing mode without using the Gemini API."
            
            # Process citations
            formatted_answer = self._parse_citations(answer_text, citation_map)
            
            # Calculate completion time
            completion_time = time.time() - start_time
            
            # Return a simplified result
            return {
                "answer": formatted_answer,
                "message_count": len(messages),
                "duration": duration_str,
                "completion_time": completion_time,
                "is_split": False
            }
            
        # Prepare message data for answering
        conversation_text = ""
        citation_map = {}
        citation_counter = 1
        
        for msg in messages:
            # Format the message with a citation
            citation_id = f"c{citation_counter}"
            citation_map[citation_id] = msg["jump_url"]
            
            message_text = f"{msg['author']['name']}: {msg['content']} [{citation_id}]\n"
            conversation_text += message_text
            
            citation_counter += 1
        
        # Build the prompt for Gemini with instructions for answering questions with citations
        prompt = f"""
You are AVERY, a Discord bot that accurately answers specific questions about chat conversations. I am giving you Discord messages and a question to answer.

Time Range Analyzed: {duration_str}

USER QUESTION: {question}

CRITICAL INSTRUCTIONS:
1. Focus ONLY on answering the specific question that was asked
2. Provide a clear, accurate, and direct answer based solely on the content of the messages
3. Use citations [cX] to reference specific messages that support your answer
4. If the question cannot be answered from these messages, clearly state that
5. Be objective and factual - don't speculate beyond what's in the messages
6. Format your answer in a clear, readable way using Markdown

Your answer should:
- Start with a clear, direct response to the question
- Include relevant evidence from the messages
- Cite specific messages to support your points
- Be well-organized using appropriate headings and bullet points
- Be comprehensive but concise

Format the output using proper Markdown:
- Use "# " for the main answer header
- Use "## " for any section headers if needed
- Use "### " for subsection headers if needed
- Use bullet points (- ) for lists
- Use bold (**text**) for emphasis
- ALWAYS cite sources with the citation format [cX] that appears after each message author's name

MESSAGES TO ANALYZE:
{conversation_text}
"""
        
        # Set up generation config with appropriate parameters
        generation_config = types.GenerationConfig(
            temperature=self.temperature,
            max_output_tokens=self.max_tokens
        )
        
        # Call Gemini API with the constructed prompt
        try:
            response = self._generate_content_with_retry(
                model=self.model_name,
                contents=prompt,
                generation_config=generation_config
            )
            
            # Extract the answer text from the response
            answer_text = response.text
            logger.info(f"Successfully generated answer with Gemini API")
            
        except Exception as api_error:
            logger.error(f"Error calling Gemini API: {api_error}")
            # Create a fallback response in case of API failure
            answer_text = f"I'm sorry, I encountered an error while trying to answer your question. Please try again later."
        
        # Process citations
        formatted_answer = self._parse_citations(answer_text, citation_map)
        
        # Calculate completion time
        completion_time = time.time() - start_time
        
        # Return a simplified result
        return {
            "answer": formatted_answer,
            "message_count": len(messages),
            "duration": duration_str,
            "completion_time": completion_time,
            "is_split": False
        }

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=1, max=10))
    def _generate_content_with_retry(self, model, contents, generation_config=None):
        """Generate content with Gemini API with automatic retry on failure"""
        logger.info(f"Making Gemini API request with retries enabled")
        try:
            # For compatibility with tests, handle both with and without generation_config
            if generation_config:
                # Extract the individual parameters from the generation_config
                # This is needed because the API doesn't accept the config directly
                return self.gemini_client.models.generate_content(
                    model=model,
                    contents=contents,
                )
            else:
                return self.gemini_client.models.generate_content(
                    model=model,
                    contents=contents
                )
        except Exception as e:
            logger.error(f"Gemini API error (will retry): {e}")
            raise

    def _parse_citations(self, text: str, citation_map: Dict[str, str]) -> str:
        """Parse and format citations in the summary text.
        
        This method transforms citation references in the text into clickable
        Discord message links. It handles several citation formats:
        
        1. Standard citations: [c1], [c2], etc. → converted to [1], [2], etc.
        2. Range citations: [c1-c5] → converted to [1-5]
        3. Grouped citations: [c1, c2, c3] → converted to [1, 2, 3]
        4. Complex mixed formats: [c1-c3, c5, c10] → combination of ranges and individual citations
        5. Complex formats like [c723-c741, c765] or [c178, c185-c208] → combination of ranges and individual citations
        
        Args:
            text: The summary or answer text containing citation references
            citation_map: Dictionary mapping citation IDs to Discord message URLs
            
        Returns:
            Formatted text with clickable Discord citation links
        """
        processed_text = text
        
        # Create a new map with numeric keys instead of 'c' prefixed keys
        numeric_citation_map = {}
        for citation_id, jump_url in citation_map.items():
            if citation_id.startswith('c') and citation_id[1:].isdigit():
                numeric_id = citation_id[1:]  # Remove the 'c' prefix
                numeric_citation_map[numeric_id] = jump_url
                
        # First, fix nested brackets that might appear like [[c1]] or [[[c1]]]
        processed_text = re.sub(r'\[\[\s*c(\d+)\s*\]\]', r'[c\1]', processed_text)
        processed_text = re.sub(r'\[\[\[\s*c(\d+)\s*\]\]\]', r'[c\1]', processed_text)
        
        # Handle complex mixed citations [c#-c#, c#, c#-c#, ...] first
        # This pattern matches citations with ranges and commas inside brackets
        complex_pattern = r'\[((?:c\d+(?:-c\d+)?(?:,\s*)?)+)\]'
        for match in re.finditer(complex_pattern, processed_text):
            citation_content = match.group(1)
            
            # Skip if this is a simple citation (no commas or ranges)
            if ',' not in citation_content and '-' not in citation_content:
                continue
                
            # If we have a complex citation with commas or ranges, process it
            # Replace the entire bracket content with processed citations
            original_citation = match.group(0)  # The full citation with brackets
            
            # First remove the 'c' prefix from all numbers
            simplified_content = re.sub(r'c(\d+)', r'\1', citation_content)
            
            # Split by commas to get individual citations or ranges
            citation_parts = [part.strip() for part in simplified_content.split(',')]
            replacement_parts = []
            
            for part in citation_parts:
                if '-' in part:
                    # This is a range citation like '1-5'
                    start_num, end_num = map(int, part.split('-'))
                    for i in range(start_num, end_num + 1):
                        numeric_id = str(i)
                        c_id = f'c{numeric_id}'
                        if c_id in citation_map:
                            replacement_parts.append(f"[{numeric_id}]({citation_map[c_id]})")
                        else:
                            replacement_parts.append(f"[{numeric_id}]")
                else:
                    # This is a single citation like '1'
                    numeric_id = part
                    c_id = f'c{numeric_id}'
                    if c_id in citation_map:
                        replacement_parts.append(f"[{numeric_id}]({citation_map[c_id]})")
                    else:
                        replacement_parts.append(f"[{numeric_id}]")
            
            # Join all parts with commas and replace the original citation
            replacement = ", ".join(replacement_parts)
            processed_text = processed_text.replace(original_citation, replacement, 1)
        
        # Process remaining standard citations
        # Convert [c#] citations to [#]
        processed_text = re.sub(r'\[c(\d+)\]', r'[\1]', processed_text)
        
        # Convert remaining [c#-c#] range citations to [#-#]
        range_pattern = r'\[c(\d+)-c(\d+)\]'
        for match in re.finditer(range_pattern, processed_text):
            start_num = int(match.group(1))
            end_num = int(match.group(2))
            replacement_parts = []
            
            for i in range(start_num, end_num + 1):
                numeric_id = str(i)
                c_id = f'c{numeric_id}'
                if c_id in citation_map:
                    replacement_parts.append(f"[{numeric_id}]({citation_map[c_id]})")
                else:
                    replacement_parts.append(f"[{numeric_id}]")
                    
            replacement = ", ".join(replacement_parts)
            processed_text = processed_text.replace(match.group(0), replacement, 1)
        
        # Convert remaining grouped citations like [c1, c2, c3] to [1, 2, 3]
        # First capture the content inside brackets
        grouped_pattern = r'\[(c\d+(?:,\s*c\d+)+)\]'
        for match in re.finditer(grouped_pattern, processed_text):
            citation_group = match.group(1)
            # Remove 'c' prefix from each number
            citation_ids = re.findall(r'c(\d+)', citation_group)
            replacement_parts = []
            
            for numeric_id in citation_ids:
                c_id = f'c{numeric_id}'
                if c_id in citation_map:
                    replacement_parts.append(f"[{numeric_id}]({citation_map[c_id]})")
                else:
                    replacement_parts.append(f"[{numeric_id}]")
                    
            replacement = ", ".join(replacement_parts)
            processed_text = processed_text.replace(match.group(0), replacement, 1)
        
        # Identify already processed citations to protect them
        protected_citations = {}
        protected_counter = 0
        
        # Find and protect already processed citations with format [#](url)
        already_processed_pattern = r'\[\d+\]\([^)]+\)'
        for match in re.finditer(already_processed_pattern, processed_text):
            placeholder = f"__PROTECTED_CITATION_{protected_counter}__"
            protected_citations[placeholder] = match.group(0)
            processed_text = processed_text.replace(match.group(0), placeholder, 1)
            protected_counter += 1
        
        # Handle standard citation format [1], [2], etc.
        for numeric_id, jump_url in numeric_citation_map.items():
            # Replace citations with links
            processed_text = processed_text.replace(f"[{numeric_id}]", f"[{numeric_id}]({jump_url})")
        
        # Handle citation ranges like [1-5]
        range_pattern = r'\[(\d+)-(\d+)\]'
        for match in re.finditer(range_pattern, processed_text):
            start_num = int(match.group(1))
            end_num = int(match.group(2))
            
            replacement = ""
            for i in range(start_num, end_num + 1):
                numeric_id = str(i)
                if numeric_id in numeric_citation_map:
                    if replacement:
                        replacement += ", "
                    replacement += f"[{numeric_id}]({numeric_citation_map[numeric_id]})"
                    
            if replacement:
                processed_text = processed_text.replace(match.group(0), replacement, 1)
        
        # Handle grouped citations like [1, 2, 3]
        grouped_pattern = r'\[(\d+(?:,\s*\d+)+)\]'
        for match in re.finditer(grouped_pattern, processed_text):
            citation_group = match.group(1)
            citation_ids = [c.strip() for c in citation_group.split(',')]
            
            replacement = ""
            for numeric_id in citation_ids:
                if numeric_id in numeric_citation_map:
                    if replacement:
                        replacement += ", "
                    replacement += f"[{numeric_id}]({numeric_citation_map[numeric_id]})"
                    
            if replacement:
                processed_text = processed_text.replace(match.group(0), replacement, 1)
        
        # Restore protected citations
        for placeholder, original in protected_citations.items():
            processed_text = processed_text.replace(placeholder, original)
        
        return processed_text

    def _split_long_response(self, text: str) -> Dict[str, Any]:
        """Split a long response text into multiple parts for Discord embeds
        
        Discord embeds have a 4096 character limit for the description field.
        This method splits long texts to fit within this limit.
        
        Args:
            text: The long text to split
            
        Returns:
            Dictionary with the main part and continuation parts
        """
        # Discord embed description has a 4096 character limit
        # We'll use 4000 to be safe
        max_length = 4000
        
        # If text is shorter than the limit, no splitting needed
        if len(text) <= max_length:
            return {"main_part": text, "continuation_parts": []}
        
        # Find good splitting points (paragraphs, sentences)
        parts = []
        remaining_text = text
        
        while remaining_text:
            if len(remaining_text) <= max_length:
                # If remaining text fits, add it as the last part
                parts.append(remaining_text)
                break
                
            # Try to split at a paragraph
            split_index = remaining_text[:max_length].rfind('\n\n')
            
            # If no paragraph found, try to split at a newline
            if split_index == -1:
                split_index = remaining_text[:max_length].rfind('\n')
                
            # If no newline found, try to split at a sentence
            if split_index == -1:
                # Look for sentence endings (.!?)
                for char in ['. ', '! ', '? ']:
                    potential_index = remaining_text[:max_length].rfind(char)
                    if potential_index != -1:
                        split_index = potential_index + 1  # Include the punctuation
                        break
                        
            # If no good splitting point found, force split at max_length
            if split_index == -1:
                split_index = max_length
                
            # Split the text
            parts.append(remaining_text[:split_index].strip())
            remaining_text = remaining_text[split_index:].strip()
            
        # Return the split parts
        return {
            "main_part": parts[0],
            "continuation_parts": parts[1:]
        }
