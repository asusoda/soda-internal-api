import os
import time
from google import genai
from google.genai import types
from datetime import datetime, timedelta, timezone
from typing import List, Dict, Any, Optional, Tuple, Union
from modules.utils.db import DBConnect
from modules.summarizer.models import SummarizerConfig, SummaryLog
import logging
from modules.utils.config import Config as AppConfig
import dateparser
import re
from timefhuman import timefhuman

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
            
    def extract_timeframe_from_text(self, text: str) -> Optional[str]:
        """Extract time-related expressions from natural language text.
        
        This method uses a multi-layered approach to extract time expressions:
        1. Check for exact matches of common time expressions (today, yesterday, etc.)
        2. Check if the text contains standard duration formats (e.g., "24h", "3d")
        3. Try to extract time expressions using timefhuman
        4. Use regex pattern matching to extract time-related phrases
        
        The method distinguishes between two types of time expressions:
        - Calendar-aligned expressions ("today", "last month") - These align with calendar boundaries
        - Duration-based expressions ("7d", "past month"/"30d") - These represent exact time durations
        
        Args:
            text: Text to analyze for time expressions
            
        Returns:
            Extracted time expression or None if no valid expression found
            - Calendar expressions return string descriptors ("today", "last month")
            - Duration expressions return standardized formats ("7d", "30d")
            - Date ranges return formatted strings ("from 2023-01-01 to 2023-01-31")
            - Returns None if no time expression is found or recognized
        """
        if not text:
            return None
        
        # Remove any question marks which can confuse timefhuman
        clean_text = text.replace('?', '').strip()
        text_lower = clean_text.lower()
        
        # Special case for 'how does this system work' type phrases - explicitly return None
        if text_lower.startswith('how') and ('work' in text_lower or 'system' in text_lower):
            return None
            
        # Unified expression mapping: maps text patterns to their normalized values
        # - Duration-based expressions use standardized Nd format
        # - Calendar-based expressions use descriptive strings for calendar alignment
        # This distinction matters for timezone interpretation later in the process
        time_expressions = {
            # Calendar-aligned expressions (based on local calendar dates)
            "today": "today", 
            "yesterday": "yesterday",
            "this week": "this week", 
            "last week": "last week",
            "this month": "this month", 
            "last month": "last month",
            "this year": "this year", 
            "last year": "last year",
            
            # Duration-based expressions (N days/months/years ago until now)
            "past week": "7d", 
            "the past week": "7d",
            "last 7 days": "7d",
            "past month": "30d", 
            "the past month": "30d",
            "last 30 days": "30d",
            "past year": "365d", 
            "the past year": "365d",
            "last 365 days": "365d"
        }
        
        # Use module-level TIME_PHRASES constant to check for time keywords
        contains_time_keyword = False
        for phrase in TIME_PHRASES:
            if phrase in text_lower:
                contains_time_keyword = True
                break
                
        if not contains_time_keyword:
            # No time-related words found, return None early
            return None
            
        # Check for expressions in a single loop
        for expr, value in time_expressions.items():
            if expr in text_lower:
                return value
            
        # 2. Check if this is already a standard duration format
        duration_match = re.match(r'^(\d+)([hdw])$', text_lower)
        if duration_match:
            # Already in our standard format, no extraction needed
            return text_lower
        
        # We already checked for time keywords at the beginning of the method
            
        # 3. Try using timefhuman for complex expressions
        try:
            # Use local time for better relative date handling
            local_now = datetime.now()
            
            # Try to extract a datetime or datetime range with timefhuman
            # Log timezone information for debugging
            logger.debug(f"Using reference time for extraction: {local_now} (local timezone)")
            parsed = timefhuman(clean_text, now=local_now)
            
            # Check if we got a valid result
            if parsed and parsed != []:
                # Successfully parsed - convert to a string representation
                if isinstance(parsed, list):
                    # It's a list of datetimes (likely a range)
                    if len(parsed) == 2:
                        # It's a datetime range (start and end)
                        start, end = parsed
                        return f"from {start.strftime('%Y-%m-%d')} to {end.strftime('%Y-%m-%d')}"
                    elif len(parsed) == 1:
                        # It's a single datetime
                        dt = parsed[0]
                        # Check if it's a date only (no specific time)
                        if dt.hour == 0 and dt.minute == 0 and dt.second == 0:
                            return dt.strftime("%Y-%m-%d") 
                        else:
                            # Specific time - create a 24h window
                            return f"24 hours ending {dt.strftime('%Y-%m-%d %H:%M')}"
                elif isinstance(parsed, datetime):
                    # It's a single datetime
                    # Check if it's a date only (no specific time)
                    if parsed.hour == 0 and parsed.minute == 0 and parsed.second == 0:
                        return parsed.strftime("%Y-%m-%d") 
                    else:
                        # Specific time - create a window
                        return f"24 hours ending {parsed.strftime('%Y-%m-%d %H:%M')}"
                
        except Exception as e:
            logger.debug(f"Failed to extract datetime with timefhuman: {e}")
            
        # Pattern matching for time references that need regex for more flexible matching
        # Dictionary mapping regex patterns to standard timeframe formats
        # Sorted from more specific to more general to avoid mismatches
        std_patterns = {
            # Number-based duration patterns (most explicit)
            r'\b(?:last|past|previous)\s+(\d+)\s+days?\b': lambda m: f"{m.group(1)}d",
            r'\b(?:last|past|previous)\s+(\d+)\s+weeks?\b': lambda m: f"{int(m.group(1))*7}d",
            r'\b(?:last|past|previous)\s+(\d+)\s+months?\b': lambda m: f"{int(m.group(1))*30}d",
            r'\b(?:last|past|previous)\s+(\d+)\s+years?\b': lambda m: f"{int(m.group(1))*365}d",
            
            # Day expressions
            r'\b(?:last|previous)\s+day\b': "1d",
            r'\byesterday\b': "yesterday",  # Calendar-aligned
            
            # Week expressions - distinguish between calendar week and 7-day period
            r'\b(?:last|previous)\s+week\b': "last week",  # Calendar-aligned
            r'\bpast\s+week\b': "7d",                      # Duration-based
            r'\brecent\s+week\b': "7d",
            
            # Month expressions - calendar month vs 30-day period
            r'\b(?:last|previous)\s+month\b': "last month", # Calendar-aligned
            r'\bpast\s+month\b': "30d",                     # Duration-based
            r'\brecent\s+month\b': "30d",
            
            # Year expressions
            r'\b(?:last|previous)\s+year\b': "last year",    # Calendar-aligned
            r'\bpast\s+year\b': "365d",                     # Duration-based
            
            # Compound patterns with articles
            r'\bthe\s+(?:last|previous)\s+(day|week|month|year)\b': lambda m: "1d" if m.group(1) == "day" else 
                                                                      "last week" if m.group(1) == "week" else 
                                                                      "last month" if m.group(1) == "month" else "last year",
            
            r'\bthe\s+past\s+(\d+)\s+(days?|weeks?|months?|years?)\b': lambda m: f"{int(m.group(1))*1}d" if "day" in m.group(2) else 
                                                                        f"{int(m.group(1))*7}d" if "week" in m.group(2) else 
                                                                        f"{int(m.group(1))*30}d" if "month" in m.group(2) else 
                                                                        f"{int(m.group(1))*365}d",
                                                                        
            r'\bthe\s+past\s+(week|month|year)\b': lambda m: "7d" if m.group(1) == "week" else 
                                                 "30d" if m.group(1) == "month" else "365d"
        }
        
        for pattern, mapper in std_patterns.items():
            match = re.search(pattern, text_lower)
            if match:
                # If the mapper is a function, call it with the match object
                if callable(mapper):
                    return mapper(match)
                # Otherwise, return the static value
                return mapper
                
        # 5. Extract time-related context if we found a time keyword
        time_related_text = None
        for phrase in TIME_PHRASES:  # Use the module-level constant
            if phrase in text_lower:
                # Find the complete expression including context around the keyword
                # This regex looks for 3 words before and after the time phrase
                pattern = r'(\S+\s+){0,3}' + re.escape(phrase) + r'(\s+\S+){0,3}'
                match = re.search(pattern, text_lower)
                if match:
                    time_related_text = match.group(0).strip()
                    break
        
        # Return the extracted time context if found
        if time_related_text:
            # Try dateparser on the extracted time-related text segment
            try:
                # Use local time as reference
                local_time = datetime.now()
                parsed = dateparser.parse(time_related_text, settings={'RELATIVE_BASE': local_time})
                
                if parsed:
                    # Return a date string if we successfully parsed a date
                    return parsed.strftime("%Y-%m-%d")
                else:
                    # Return the extracted text if dateparser couldn't handle it
                    return time_related_text
            except Exception as e:
                logger.debug(f"Failed dateparser extraction: {e}")
                return time_related_text
        
        # No valid timeframe found
        return None

    def parse_date_range(self, text: str) -> Tuple[datetime, Optional[datetime], str]:
        """Parse natural language date/time expressions into a start and end datetime.
        
        This method distinguishes between two types of time expressions:
        1. Calendar-aligned expressions ("today", "last week") - based on local calendar dates
        2. Duration-based expressions ("7d", "30d") - specific number of days back from now
        
        The method uses a layered approach to handle various date formats:
        1. Common expressions (today, yesterday, this week, etc.) from dictionary
        2. Single dates (YYYY-MM-DD) for full day ranges
        3. Date ranges (from YYYY-MM-DD to YYYY-MM-DD)
        4. Standard duration formats (24h, 3d, 1w)
        5. Natural language parsing with timefhuman/dateparser
        
        Args:
            text: Natural language text describing a time period
                 
        Returns:
            Tuple containing:
            - start_time: The parsed start time as a datetime object (timezone-aware)
            - end_time: The parsed end time as a datetime object, or None for duration-based queries
            - display_range: A string representation of the time range for display purposes
            
        Note on timezones: 
        - Calendar-based expressions use local date boundaries (e.g., "today" is midnight-to-midnight in local time)
        - Duration-based expressions use exact time offsets from the current time (e.g., "24h" is exactly 24 hours)
        - All returned datetime objects are timezone-aware (using timezone.utc)
        - Local time is used as the reference point for parsing relative expressions
        """
        # Default to 24 hours if no text provided
        if not text or text.strip() == "":
            end_time = datetime.now(timezone.utc)
            start_time = end_time - timedelta(hours=24)
            return start_time, None, "24h"
        
        text = text.strip().lower()
        
        # Get local time for relative expressions
        local_now = datetime.now()
        today = local_now.date()
        
        # Helper functions to calculate date ranges (defined once and cached)
        def week_start(d): return d - timedelta(days=d.weekday())
        def week_end(d): return d
        def prev_week_start(d): return week_start(d) - timedelta(days=7)
        def prev_week_end(d): return week_start(d) - timedelta(days=1)
        def month_start(d): return d.replace(day=1)
        def month_end(d): return d
        def prev_month_start(d): return (month_start(d) - timedelta(days=1)).replace(day=1)
        def prev_month_end(d): return month_start(d) - timedelta(days=1)
        
        # Pre-calculate common date values to avoid repeated calculations
        today_start_end = (today, today)
        yesterday_start_end = (today - timedelta(days=1), today - timedelta(days=1))
        this_week_start_end = (week_start(today), week_end(today))
        last_week_start_end = (prev_week_start(today), prev_week_end(today))
        this_month_start_end = (month_start(today), month_end(today))
        last_month_start_end = (prev_month_start(today), prev_month_end(today))
        
        # Define pattern handlers for various date formats
        # Maps patterns or expressions to handler functions
        pattern_handlers = {
            # 1. Common calendar expressions (direct matches)
            "today": lambda: (today_start_end, f"{today.strftime('%Y-%m-%d')} ({today.strftime('%A')})"),
            "yesterday": lambda: (yesterday_start_end, f"{yesterday_start_end[0].strftime('%Y-%m-%d')} ({yesterday_start_end[0].strftime('%A')})"),
            "this week": lambda: (this_week_start_end, 
                                f"{this_week_start_end[0].strftime('%Y-%m-%d')} ({this_week_start_end[0].strftime('%a')}) to {this_week_start_end[1].strftime('%Y-%m-%d')} ({this_week_start_end[1].strftime('%a')})"),
            "last week": lambda: (last_week_start_end,
                                f"{last_week_start_end[0].strftime('%Y-%m-%d')} ({last_week_start_end[0].strftime('%a')}) to {last_week_start_end[1].strftime('%Y-%m-%d')} ({last_week_start_end[1].strftime('%a')})"),
            "this month": lambda: (this_month_start_end,
                                 f"{this_month_start_end[0].strftime('%Y-%m-%d')} to {this_month_start_end[1].strftime('%Y-%m-%d')}"),
            "last month": lambda: (last_month_start_end,
                                 f"{last_month_start_end[0].strftime('%Y-%m-%d')} to {last_month_start_end[1].strftime('%Y-%m-%d')}"),
            
            # 2. Single date format regex
            r'^(\d{4}-\d{2}-\d{2})$': lambda m: ((datetime.strptime(m.group(1), "%Y-%m-%d").date(), 
                                                    datetime.strptime(m.group(1), "%Y-%m-%d").date()), 
                                                   m.group(1)),
            
            # 3. Date range format regex
            r'^from\s+(\d{4}-\d{2}-\d{2})\s+to\s+(\d{4}-\d{2}-\d{2})$': lambda m: ((datetime.strptime(m.group(1), "%Y-%m-%d").date(), 
                                                                                       datetime.strptime(m.group(2), "%Y-%m-%d").date()),
                                                                                      f"{m.group(1)} to {m.group(2)}"),
            
            # 4. Standard duration format regex
            r'^(\d+)([hdw])$': lambda m: self._handle_duration_format(m)
        }
        
        # Process patterns in order of specificity using the pattern_handlers dictionary
        
        # 1. Check for direct string matches in pattern_handlers
        if text in pattern_handlers:
            # Direct match for a common expression - call its handler
            date_tuple, display_range = pattern_handlers[text]()
            start_date, end_date = date_tuple
            
            # Convert dates to timezone-aware datetime objects
            start_time = datetime.combine(start_date, datetime.min.time()).replace(tzinfo=timezone.utc)
            end_time = datetime.combine(end_date, datetime.max.time()).replace(hour=23, minute=59, second=59, tzinfo=timezone.utc)
            
            return start_time, end_time, display_range
        
        # 2. Try regex pattern matches
        for pattern, handler in pattern_handlers.items():
            # Skip direct string matches - we already checked those
            if not pattern.startswith('^'):
                continue
                
            match = re.match(pattern, text)
            if match:
                # Call the pattern's handler with the match object
                date_tuple, display_range = handler(match)
                
                # Handle special case for duration format which returns final values directly
                if pattern == r'^(\d+)([hdw])$':
                    return date_tuple[0], date_tuple[1], display_range
                    
                # For other patterns, convert dates to datetime objects
                start_date, end_date = date_tuple
                start_time = datetime.combine(start_date, datetime.min.time()).replace(tzinfo=timezone.utc)
                end_time = datetime.combine(end_date, datetime.max.time()).replace(hour=23, minute=59, second=59, tzinfo=timezone.utc)
                
                return start_time, end_time, display_range
        
        # 5. Try natural language parsing with timefhuman using local time as reference
        try:
            # Parse with timefhuman using local time as the reference
            parsed = timefhuman(text, now=local_now)
            
            if parsed:
                # Handle date/time list (range)
                if isinstance(parsed, list):
                    if len(parsed) == 2:
                        start_dt, end_dt = parsed
                        
                        # Ensure timezone awareness
                        if start_dt.tzinfo is None:
                            start_dt = start_dt.replace(tzinfo=timezone.utc)
                        if end_dt.tzinfo is None:
                            end_dt = end_dt.replace(tzinfo=timezone.utc)
                        
                        # Make end time inclusive if it's a date without time
                        if end_dt.hour == 0 and end_dt.minute == 0:
                            end_dt = end_dt.replace(hour=23, minute=59, second=59)
                        
                        if start_dt.date() == end_dt.date():
                            display_range = start_dt.strftime("%Y-%m-%d")
                        else:
                            display_range = f"{start_dt.strftime('%Y-%m-%d')} to {end_dt.strftime('%Y-%m-%d')}"
                        
                        return start_dt, end_dt, display_range
                    
                    elif len(parsed) == 1:
                        # Single date in a list
                        dt = parsed[0]
                        if dt.tzinfo is None:
                            dt = dt.replace(tzinfo=timezone.utc)
                        
                        if dt.hour == 0 and dt.minute == 0:
                            # Full day
                            return dt, dt.replace(hour=23, minute=59, second=59), dt.strftime("%Y-%m-%d")
                        else:
                            # 24h window ending at the time
                            return dt - timedelta(hours=24), dt, f"24h ending {dt.strftime('%Y-%m-%d %H:%M')}"
                
                # Handle single datetime
                elif isinstance(parsed, datetime):
                    dt = parsed
                    if dt.tzinfo is None:
                        dt = dt.replace(tzinfo=timezone.utc)
                    
                    if dt.hour == 0 and dt.minute == 0:
                        # Full day
                        return dt, dt.replace(hour=23, minute=59, second=59), dt.strftime("%Y-%m-%d")
                    else:
                        # 24h window
                        return dt - timedelta(hours=24), dt, f"24h ending {dt.strftime('%Y-%m-%d %H:%M')}"
        
        except Exception as e:
            logger.debug(f"Natural language parsing failed: {e}")
        
        # 6. Try dateparser as a last resort (has good multi-language support)
        try:
            # Use local time as the reference for better user experience
            parsed = dateparser.parse(text, settings={'RELATIVE_BASE': local_now})
            
            if parsed:
                # Make timezone aware
                if parsed.tzinfo is None:
                    parsed = parsed.replace(tzinfo=timezone.utc)
                
                if parsed.hour == 0 and parsed.minute == 0:
                    # Full day
                    return parsed, parsed.replace(hour=23, minute=59, second=59), parsed.strftime("%Y-%m-%d")
                else:
                    # 24h window ending at the specific time
                    return parsed - timedelta(hours=24), parsed, f"24h ending {parsed.strftime('%Y-%m-%d %H:%M')}"
        
        except Exception as e:
            logger.debug(f"Dateparser failed: {e}")
        
        # Improved fallback with more detailed logging
        end_time = datetime.now(timezone.utc)
        start_time = end_time - timedelta(hours=24)
        
        # Log detailed information about the failed parsing attempt
        logger.info(f"Unable to parse time expression: '{text}'")
        logger.info(f"Tried: common expressions, date formats, duration formats, timefhuman, and dateparser")
        logger.info(f"Falling back to default 24-hour window: {start_time.isoformat()} to {end_time.isoformat()}")
        
        # Return a more descriptive display format for the fallback case
        return start_time, None, "last 24 hours (default)"
    
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
            question: The specific question to answer about the conversation
            duration_str: Duration or date range string
            user_id: Discord user ID who requested the answer
            channel_id: Discord channel ID where the question was asked
            guild_id: Discord guild/server ID

        Returns:
            Dictionary with answer text and metrics
        """
        if not self.gemini_client:
            raise Exception("Gemini client not initialized")

        if not messages:
            return {
                "answer": f"""# No Messages Found 🔎

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
        logger.info(f"Question request for channel {channel_id} - Found {len(messages)} messages over {duration_str}")
        logger.info(f"Question: {question}")

        db = next(self.db_connect.get_db())

        try:
            # Create log entry (reusing SummaryLog for simplicity)
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

                # Log the number of messages being analyzed
                logger.info(f"Formatting {len(messages)} messages for question answering with citations")

                # Create prompt for Gemini
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
                {formatted_messages}
                """

                # Generate answer using the Genai API
                try:
                    # Configure the generation parameters
                    generation_config = types.GenerateContentConfig(
                        temperature=self.temperature,
                        max_output_tokens=self.max_tokens,
                        top_p=0.8,
                        top_k=40
                    )

                    # Send request to Gemini API
                    response = self.gemini_client.models.generate_content(
                        model=self.model_name,
                        contents=prompt,
                        config=generation_config
                    )

                    # Log response details
                    logger.info(f"Gemini response type: {type(response)}")
                    logger.info(f"Response structure: {response.model_dump_json(exclude_none=True)[:100]}...")

                    # Get the answer text
                    answer = response.text.strip()
                    logger.info(f"Generated answer with {len(answer)} characters")

                    # Check for empty or very short answers
                    if not answer or len(answer) < 50:
                        logger.warning(f"Gemini returned empty or very short answer: '{answer}' - this might indicate an issue with the API")
                        answer = """# Unable to Generate Answer ⚠️

I encountered a problem generating an answer for your question. This is likely due to an issue with the AI service.

## Options

- Try again later when the service may be less busy
- Try rephrasing your question
- Try with a different time period"""
                    else:
                        # Parse and format citations
                        answer = self._parse_citations(answer, citation_map)
                        
                        # Split the answer if it's too long for Discord
                        if len(answer) > 4000:  # Using 4000 to leave some buffer
                            logger.info(f"Answer exceeds Discord's limit ({len(answer)} chars). Splitting into parts.")
                            answer_parts = self._split_summary_for_discord(answer)
                            # Return as multiple parts
                            return {
                                "answer": answer_parts[0],
                                "continuation_parts": answer_parts[1:],
                                "message_count": len(messages),
                                "duration": duration_str,
                                "completion_time": time.time() - start_time,
                                "error": False,
                                "is_split": True
                            }

                except Exception as api_error:
                    logger.error(f"Error in Gemini API call: {api_error}")
                    answer = """# API Error ⚠️

I encountered an error while trying to answer your question. The AI service returned an error.

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
                    "answer": answer,
                    "message_count": len(messages),
                    "duration": duration_str,
                    "completion_time": completion_time,
                    "error": False,
                    "is_split": False
                }

            except Exception as e:
                # Log error
                logger.error(f"Error generating answer: {e}")

                # Update log entry with error
                log_entry.error = True
                log_entry.error_message = str(e)
                db.commit()

                return {
                    "answer": """# Error Answering Question ⚠️

I encountered an unexpected error while processing your request.

## Technical Details

An error occurred during answer generation.

## Next Steps

- Try again with a simpler question
- Try with a shorter time period
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
        """Parse and format citations in the summary text.
        
        This method transforms citation references in the text into clickable
        Discord message links. It handles several citation formats:
        
        1. Standard citations: [c1], [c2], etc.
        2. Range citations: [c1-c5] (expands to individual citations)
        3. Grouped citations: [c1, c2, c3]
        4. Citations without brackets: c1 (converted to proper format)
        
        Args:
            text: The summary or answer text containing citation references
            citation_map: Dictionary mapping citation IDs to Discord message URLs
            
        Returns:
            Text with citations converted to clickable Discord message links
        """
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
        
        The splitting algorithm works as follows:
        1. First attempt to split at main section headers (# or ##)
        2. If not enough headers are found, fall back to splitting at paragraph breaks
        3. If paragraphs are too long, split at line breaks
        4. As a last resort, split exactly at the character limit
        5. Add continuation indicators to parts after the first one
        
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
        
    def _handle_duration_format(self, match) -> Tuple[Tuple[datetime, Optional[datetime]], str]:
        """Handle standard duration formats (e.g., 24h, 3d, 1w).
        
        Args:
            match: Regex match object with groups for value and unit
            
        Returns:
            Tuple containing:
            - Tuple of (start_time, end_time) where end_time is None for durations
            - Display range string
        """
        value, unit = match.groups()
        value = int(value)
        
        # For duration formats, always use UTC time with clear display formatting
        end_time = datetime.now(timezone.utc)
        unit_name = {"h": "hour", "d": "day", "w": "week"}[unit]
        plural = "s" if value > 1 else ""
        
        if unit == 'h':
            start_time = end_time - timedelta(hours=value)
            display_range = f"last {value} {unit_name}{plural}"
        elif unit == 'd':
            start_time = end_time - timedelta(days=value)
            display_range = f"last {value} {unit_name}{plural}"
        elif unit == 'w':
            start_time = end_time - timedelta(weeks=value)
            display_range = f"last {value} {unit_name}{plural}"
        else:
            # Fallback to 24h (shouldn't happen with regex validation)
            start_time = end_time - timedelta(hours=24)
            display_range = "last 24 hours"
            
        return (start_time, None), display_range
        
    def _split_by_size(self, text: str, max_size: int) -> List[str]:
        """Split text by size, trying to split at paragraph boundaries.
        
        This method implements a hierarchical splitting approach:
        1. First tries to split at paragraph boundaries (double newlines)
        2. If that doesn't work well, tries single line breaks
        3. As a last resort, splits at the exact character limit
        
        The method prioritizes keeping logical sections together while ensuring
        no part exceeds Discord's character limits.
        
        Args:
            text: Text to split
            max_size: Maximum size for each part
            
        Returns:
            List of text parts, each under max_size characters
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
