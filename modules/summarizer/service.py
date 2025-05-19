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
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type

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
        
        This method primarily uses timefhuman to extract temporal expressions,
        with fallbacks to specific keyword matching for common expressions.
        
        The method distinguishes between:
        - Date ranges ("Monday to Friday", "January to February") 
        - Single dates ("tomorrow", "January 1st")
        - Relative time periods ("last week", "past 3 days")
        
        Args:
            text: Text to analyze for time expressions
            
        Returns:
            Extracted time expression or None if no valid expression found:
            - Date ranges return formatted strings ("from 2023-01-01 to 2023-01-31")
            - Calendar expressions return string descriptors ("today", "last month")
            - Duration expressions return standardized formats ("7d", "30d")
            - Returns None if no time expression is found
        """
        if not text:
            return None
        
        # Clean the text for processing
        clean_text = text.replace('?', '').strip()
        text_lower = clean_text.lower()
        
        # Special case for 'how does this system work' type phrases
        if text_lower.startswith('how') and ('work' in text_lower or 'system' in text_lower):
            return None
        
        # Direct look-up for common expressions (fast path)
        time_expressions = {
            # Calendar-aligned expressions
            "today": "today", 
            "yesterday": "yesterday",
            "this week": "this week", 
            "last week": "last week",
            "this month": "this month", 
            "last month": "last month",
            "this year": "this year", 
            "last year": "last year",
            
            # Duration-based expressions
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
        
        # Quick check for time keywords before proceeding
        contains_time_keyword = False
        for phrase in TIME_PHRASES:
            if phrase in text_lower:
                contains_time_keyword = True
                break
                
        if not contains_time_keyword:
            return None
            
        # Standard expression matching
        for expr, value in time_expressions.items():
            if expr in text_lower:
                return value
            
        # Standard duration format check
        duration_match = re.match(r'^(\d+)([hdw])$', text_lower)
        if duration_match:
            return text_lower
        
        # First check for month ranges directly since timefhuman sometimes struggles with these
        month_names = "january|february|march|april|may|june|july|august|september|october|november|december"
        month_pattern = rf'(?:last\s+)?({month_names})\s+(?:to|through|until|and|-)\s+(?:last\s+)?({month_names})'
        month_match = re.search(month_pattern, text_lower)
        
        if month_match:
            start_month, end_month = month_match.groups()
            is_last_year = 'last' in text_lower
            month_range = f"{'last ' if is_last_year else ''}{start_month} to {'last ' if is_last_year else ''}{end_month}"
            logger.info(f"Extracted explicit month range: '{month_range}'")
            return month_range
            
        # Try timefhuman as the primary parser for other cases
        try:
            # Get local reference time
            local_now = datetime.now()
            logger.debug(f"Using reference time for timefhuman: {local_now}")
            
            # Let timefhuman process the text (handles a wide range of formats)
            parsed = timefhuman(clean_text, now=local_now)
            
            # Process timefhuman's results
            if parsed and parsed != []:
                logger.info(f"Timefhuman extracted: {parsed}")
                
                # Handle date ranges (list of tuples)
                if isinstance(parsed, list) and len(parsed) > 0 and isinstance(parsed[0], tuple):
                    start, end = parsed[0]
                    logger.info(f"Date range: {start} to {end}")
                    return f"from {start.strftime('%Y-%m-%d')} to {end.strftime('%Y-%m-%d')}"
                
                # Handle nested lists
                elif isinstance(parsed, list) and len(parsed) > 0 and isinstance(parsed[0], list):
                    start = parsed[0][0] 
                    end = parsed[0][-1]  
                    logger.info(f"List range: {start} to {end}")
                    return f"from {start.strftime('%Y-%m-%d')} to {end.strftime('%Y-%m-%d')}"
                
                # Handle list of dates
                elif isinstance(parsed, list):
                    if len(parsed) >= 2:
                        start, end = parsed[0], parsed[-1]
                        logger.info(f"Multiple dates: {start} to {end}")
                        return f"from {start.strftime('%Y-%m-%d')} to {end.strftime('%Y-%m-%d')}"
                    elif len(parsed) == 1:
                        dt = parsed[0]
                        if dt.hour == 0 and dt.minute == 0 and dt.second == 0:
                            return dt.strftime("%Y-%m-%d") 
                        else:
                            return f"24 hours ending {dt.strftime('%Y-%m-%d %H:%M')}"
                
                # Handle single datetime
                elif isinstance(parsed, datetime):
                    if parsed.hour == 0 and parsed.minute == 0 and parsed.second == 0:
                        return parsed.strftime("%Y-%m-%d") 
                    else:
                        return f"24 hours ending {parsed.strftime('%Y-%m-%d %H:%M')}"
                
        except Exception as e:
            logger.debug(f"Timefhuman extraction failed: {e}")
        
        # Fallback for expressions timefhuman may miss
        # Check for expressions timefhuman sometimes struggles with
        
        # Common date range patterns (day of week ranges, month ranges)
        range_separators = "to|through|until|and|-"
        weekday_names = "monday|tuesday|wednesday|thursday|friday|saturday|sunday"
        month_names = "january|february|march|april|may|june|july|august|september|october|november|december"
        
        # Check for weekday and month ranges explicitly
        weekday_pattern = rf'(?:last\s+)?({weekday_names})\s+(?:{range_separators})\s+(?:last\s+)?({weekday_names})'
        weekday_match = re.search(weekday_pattern, text_lower)
        if weekday_match:
            start_day, end_day = weekday_match.groups()
            is_last_week = 'last' in text_lower
            time_prefix = "last " if is_last_week else ""
            logger.info(f"Extracted weekday range: {time_prefix}{start_day} to {end_day}")
            return f"{time_prefix}{start_day} to {end_day}"
            
        month_pattern = rf'(?:last\s+)?({month_names})\s+(?:{range_separators})\s+(?:last\s+)?({month_names})'
        month_match = re.search(month_pattern, text_lower)
        if month_match:
            start_month, end_month = month_match.groups()
            is_last_year = 'last' in text_lower
            month_range = f"{'last ' if is_last_year else ''}{start_month} to {'last ' if is_last_year else ''}{end_month}"
            logger.info(f"Extracted month range: {month_range}")
            return month_range
            
        # Define mapping for weekday names
        weekday_names = {
            "monday": 0, "tuesday": 1, "wednesday": 2, "thursday": 3,
            "friday": 4, "saturday": 5, "sunday": 6
        }
        
        # Match relative weekday expressions like "last Monday", "previous Friday", etc.
        relative_weekday_pattern = r'\b(last|previous|this)\s+(' + '|'.join(weekday_names.keys()) + r')\b'
        weekday_match = re.search(relative_weekday_pattern, text_lower)
        if weekday_match:
            prefix, weekday_name = weekday_match.groups()
            return f"{prefix} {weekday_name}"
            
        # Define number word mapping for "ago" expressions
        number_words = {
            "a": 1, "an": 1, "one": 1, "two": 2, "three": 3, "four": 4, "five": 5,
            "six": 6, "seven": 7, "eight": 8, "nine": 9, "ten": 10,
            "eleven": 11, "twelve": 12, "thirteen": 13, "fourteen": 14, "fifteen": 15,
            "twenty": 20, "thirty": 30, "forty": 40, "fifty": 50, "sixty": 60,
            "ninety": 90, "hundred": 100
        }
        
        # "Ago" patterns
        # Match digit number (e.g., "3 days ago")
        ago_digit_pattern = r'\b(\d+)\s+(day|days|week|weeks|month|months|year|years)\s+ago\b'
        ago_digit_match = re.search(ago_digit_pattern, text_lower)
        if ago_digit_match:
            quantity, unit = ago_digit_match.groups()
            quantity = int(quantity)
            if unit.startswith('day'):
                return f"{quantity} days ago"
            elif unit.startswith('week'):
                return f"{quantity} weeks ago"
            elif unit.startswith('month'):
                return f"{quantity} months ago"
            elif unit.startswith('year'):
                return f"{quantity} years ago"
        
        # Match word number (e.g., "two weeks ago")
        number_words_pattern = '|'.join(number_words.keys())
        ago_word_pattern = rf'\b({number_words_pattern})\s+(day|days|week|weeks|month|months|year|years)\s+ago\b'
        ago_word_match = re.search(ago_word_pattern, text_lower)
        if ago_word_match:
            word_num, unit = ago_word_match.groups()
            quantity = number_words[word_num]
            if unit.startswith('day'):
                return f"{quantity} days ago"
            elif unit.startswith('week'):
                return f"{quantity} weeks ago"
            elif unit.startswith('month'):
                return f"{quantity} months ago"
            elif unit.startswith('year'):
                return f"{quantity} years ago"
        
        # Relative time expressions fallback
        relative_patterns = {
            # Duration patterns with numbers
            r'\b(?:last|past|previous)\s+(\d+)\s+days?\b': lambda m: f"{m.group(1)}d",
            r'\b(?:last|past|previous)\s+(\d+)\s+weeks?\b': lambda m: f"{int(m.group(1))*7}d",
            r'\b(?:last|past|previous)\s+(\d+)\s+months?\b': lambda m: f"{int(m.group(1))*30}d",
            
            # Standardized time periods
            r'\b(?:last|previous)\s+day\b': "1d",
            r'\bpast\s+week\b': "7d",
            r'\bpast\s+month\b': "30d",
            r'\bpast\s+year\b': "365d"
        }
        
        for pattern, mapper in relative_patterns.items():
            match = re.search(pattern, text_lower)
            if match:
                return mapper(match) if callable(mapper) else mapper
        
        # If we have a time keyword but no patterns matched, extract the context
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

    def parse_date_range(self, text: str) -> Tuple[datetime, Optional[datetime], str]:
        """Parse natural language date/time expressions into a start and end datetime.
        
        This method primarily uses timefhuman to handle date ranges, with fallbacks to 
        handle special cases. It returns timezone-aware datetime objects for the 
        parsed time range.
        
        Args:
            text: Natural language text describing a time period
                 
        Returns:
            Tuple containing:
            - start_time: The parsed start time as a datetime object (timezone-aware)
            - end_time: The parsed end time as a datetime object, or None for duration-based queries
            - display_range: A string representation of the time range for display purposes
            
        Note on timezones: 
        - All returned datetime objects are timezone-aware (using timezone.utc)
        - Local time is used as the reference point for parsing relative expressions
        """
        # Default to 24 hours if no text provided
        if not text or text.strip() == "":
            end_time = datetime.now(timezone.utc)
            start_time = end_time - timedelta(hours=24)
            return start_time, None, "24h (default)"
        
        text = text.strip().lower()
        local_now = datetime.now()
        today = local_now.date()
        
        # Handle common calendar expressions first (fast path)
        calendar_expressions = {
            "today": (today, today, f"{today.strftime('%Y-%m-%d')} ({today.strftime('%A')})"),
            "yesterday": (today - timedelta(days=1), today - timedelta(days=1), f"{(today - timedelta(days=1)).strftime('%Y-%m-%d')} ({(today - timedelta(days=1)).strftime('%A')})"),
            "this week": (today - timedelta(days=today.weekday()), today, f"This week ({(today - timedelta(days=today.weekday())).strftime('%Y-%m-%d')} to {today.strftime('%Y-%m-%d')})"),
            "last week": (today - timedelta(days=today.weekday()+7), today - timedelta(days=today.weekday()+1), f"Last week ({(today - timedelta(days=today.weekday()+7)).strftime('%Y-%m-%d')} to {(today - timedelta(days=today.weekday()+1)).strftime('%Y-%m-%d')})"),
            "this month": (today.replace(day=1), today, f"This month ({today.replace(day=1).strftime('%Y-%m-%d')} to {today.strftime('%Y-%m-%d')})"),
            "last month": ((today.replace(day=1) - timedelta(days=1)).replace(day=1), today.replace(day=1) - timedelta(days=1), f"Last month ({(today.replace(day=1) - timedelta(days=1)).replace(day=1).strftime('%Y-%m-%d')} to {(today.replace(day=1) - timedelta(days=1)).strftime('%Y-%m-%d')})")
        }
        
        # Add support for specific month names like "last january"
        month_names = {
            "january": 1, "february": 2, "march": 3, "april": 4, "may": 5, "june": 6,
            "july": 7, "august": 8, "september": 9, "october": 10, "november": 11, "december": 12
        }
        
        # Check for "last [month]" pattern
        last_month_match = re.match(r'^last\s+(' + '|'.join(month_names.keys()) + ')$', text.lower())
        if last_month_match:
            month_name = last_month_match.group(1)
            month_num = month_names[month_name]
            current_year = today.year
            
            # If the month is in the future or current, use last year's date
            if month_num > today.month or (month_num == today.month and today.day == 1):
                year = current_year - 1
            else:
                year = current_year
                
            # Create start and end dates for the entire month
            start_date = datetime(year, month_num, 1).date()
            
            # Get the last day of the month
            if month_num == 12:  # December
                end_date = datetime(year, 12, 31).date()
            else:
                # Last day of month is the day before the first day of next month
                end_date = (datetime(year, month_num + 1, 1) - timedelta(days=1)).date()
                
            start_time = datetime.combine(start_date, datetime.min.time()).replace(tzinfo=timezone.utc)
            end_time = datetime.combine(end_date, datetime.max.time()).replace(hour=23, minute=59, second=59, tzinfo=timezone.utc)
            
            display_range = f"{month_name.capitalize()} {year} ({start_date.strftime('%Y-%m-%d')} to {end_date.strftime('%Y-%m-%d')})"
            
            logger.info(f"Parsed 'last {month_name}' as {start_time} to {end_time}")
            return start_time, end_time, display_range
            
        # Support for relative weekday expressions (last Monday, previous Tuesday, etc.)
        weekday_names = {
            "monday": 0, "tuesday": 1, "wednesday": 2, "thursday": 3,
            "friday": 4, "saturday": 5, "sunday": 6
        }
        
        # Pattern matches: "last Monday", "previous Tuesday", etc.
        relative_weekday_pattern = r'^(last|previous|this)\s+(' + '|'.join(weekday_names.keys()) + r')$'
        weekday_match = re.match(relative_weekday_pattern, text.lower())
        
        if weekday_match:
            prefix, weekday_name = weekday_match.groups()
            target_weekday = weekday_names[weekday_name]
            current_weekday = today.weekday()
            
            # Calculate the date of the target weekday
            if prefix.lower() == "this":
                # "This weekday" refers to the current week's occurrence
                # If it's already happened this week, use it; otherwise use next week
                if target_weekday <= current_weekday:
                    # It's already happened this week, so use this week's occurrence
                    days_diff = current_weekday - target_weekday
                else:
                    # It hasn't happened yet this week, so find the occurrence next week
                    days_diff = current_weekday + (7 - target_weekday)
            else:  # "last" or "previous"
                # "Last weekday" refers to the most recent occurrence in the past
                if target_weekday < current_weekday:
                    # It's earlier in the current week, so use this week's occurrence
                    days_diff = current_weekday - target_weekday
                else:
                    # It's later in the week, so use last week's occurrence
                    days_diff = current_weekday + (7 - target_weekday)
                    
                # Special case: If today is the same weekday as target, use last week's occurrence
                if target_weekday == current_weekday:
                    days_diff = 7
                    
            # Calculate the target date
            target_date = today - timedelta(days=days_diff)
            
            # Create the start and end times (full day)
            start_time = datetime.combine(target_date, datetime.min.time()).replace(tzinfo=timezone.utc)
            end_time = datetime.combine(target_date, datetime.max.time()).replace(hour=23, minute=59, second=59, tzinfo=timezone.utc)
            
            # Create display string
            weekday_display = weekday_name.capitalize()
            prefix_display = prefix.capitalize()
            display_range = f"{prefix_display} {weekday_display} ({target_date.strftime('%Y-%m-%d')})"
            
            logger.info(f"Parsed '{text}' as {start_time} to {end_time}")
            return start_time, end_time, display_range
        
        # Support for "ago" expressions (3 days ago, a week ago, etc.)
        # Handle both numeric and text representations of numbers
        number_words = {
            "a": 1, "an": 1, "one": 1, "two": 2, "three": 3, "four": 4, "five": 5,
            "six": 6, "seven": 7, "eight": 8, "nine": 9, "ten": 10,
            "eleven": 11, "twelve": 12, "thirteen": 13, "fourteen": 14, "fifteen": 15,
            "twenty": 20, "thirty": 30, "forty": 40, "fifty": 50, "sixty": 60,
            "ninety": 90, "hundred": 100
        }
        
        # Pattern matches: "3 days ago", "a week ago", "two months ago", etc.
        ago_pattern = r'^(?:(\d+)|(' + '|'.join(number_words.keys()) + r'))\s+(day|days|week|weeks|month|months|year|years)\s+ago$'
        ago_match = re.match(ago_pattern, text.lower())
        
        if ago_match:
            digit_num, word_num, unit = ago_match.groups()
            
            # Get the quantity (either from digit or word)
            if digit_num:
                quantity = int(digit_num)
            else:
                quantity = number_words[word_num]
                
            # Calculate the start time based on unit
            if unit.startswith('day'):
                delta = timedelta(days=quantity)
                unit_display = 'day' if quantity == 1 else 'days'
            elif unit.startswith('week'):
                delta = timedelta(weeks=quantity)
                unit_display = 'week' if quantity == 1 else 'weeks'
            elif unit.startswith('month'):
                # For months, calculate target month
                target_month = today.month - quantity
                target_year = today.year
                
                # Adjust for year boundary if needed
                while target_month <= 0:
                    target_year -= 1
                    target_month += 12
                
                # Try to use the same day of month, but adjust for shorter months
                try:
                    start_date = datetime(target_year, target_month, today.day).date()
                except ValueError:
                    # Get the last day of the target month if day is out of range
                    if target_month == 12:
                        start_date = datetime(target_year, 12, 31).date()
                    else:
                        start_date = (datetime(target_year, target_month + 1, 1) - timedelta(days=1)).date()
                
                # Create the start_time from the date
                start_time = datetime.combine(start_date, datetime.min.time()).replace(tzinfo=timezone.utc)
                
                # No need for delta, since we've already calculated the date directly
                delta = None
                unit_display = 'month' if quantity == 1 else 'months'
            elif unit.startswith('year'):
                target_year = today.year - quantity
                
                # Use the same month and day, but in the target year
                try:
                    start_date = datetime(target_year, today.month, today.day).date()
                except ValueError:
                    # Handle leap year issues with Feb 29
                    if today.month == 2 and today.day == 29:
                        start_date = datetime(target_year, 2, 28).date()
                    else:
                        # This shouldn't happen for other dates
                        start_date = datetime(target_year, today.month, 1).date()
                
                # Create the start_time from the date
                start_time = datetime.combine(start_date, datetime.min.time()).replace(tzinfo=timezone.utc)
                
                # No need for delta, since we've already calculated the date directly
                delta = None
                unit_display = 'year' if quantity == 1 else 'years'
            else:
                # Fallback to day if somehow unit is not matched
                delta = timedelta(days=quantity)
                unit_display = 'day' if quantity == 1 else 'days'
            
            # Apply delta if needed (for days and weeks)
            if delta is not None:
                start_time = local_now.replace(tzinfo=timezone.utc) - delta
            
            # Format display range
            display_range = f"{quantity} {unit_display} ago ({start_time.strftime('%Y-%m-%d')})"
            
            logger.info(f"Parsed '{text}' as {start_time}")
            return start_time, None, display_range
        
        if text in calendar_expressions:
            start_date, end_date, display = calendar_expressions[text]
            start_time = datetime.combine(start_date, datetime.min.time()).replace(tzinfo=timezone.utc)
            end_time = datetime.combine(end_date, datetime.max.time()).replace(hour=23, minute=59, second=59, tzinfo=timezone.utc)
            return start_time, end_time, display
            
        # Handle standard duration format (e.g., "24h", "3d", "1w")
        duration_match = re.match(r'^(\d+)([hdw])$', text)
        if duration_match:
            value, unit = duration_match.groups()
            start_time, end_time, display = self._handle_duration_format(duration_match)
            return start_time, end_time, display
        
        # Handle month ranges before trying timefhuman (since it sometimes struggles with these)
        month_names = "january|february|march|april|may|june|july|august|september|october|november|december"
        month_pattern = rf'(?:last\s+)?({month_names})\s+(?:to|through|until|and|-)\s+(?:last\s+)?({month_names})'
        month_match = re.search(month_pattern, text.lower())
        
        if month_match and not text.startswith('20'):  # Avoid matching explicit date formats
            start_month, end_month = month_match.groups()
            is_last_year = 'last' in text.lower()
            date_tuple, display_range = self._handle_month_range(start_month, end_month, is_last_year)
            start_date, end_date = date_tuple
            
            start_time = datetime.combine(start_date, datetime.min.time()).replace(tzinfo=timezone.utc)
            end_time = datetime.combine(end_date, datetime.max.time()).replace(hour=23, minute=59, second=59, tzinfo=timezone.utc)
            
            logger.info(f"Parsed month range directly: {start_time} to {end_time}")
            return start_time, end_time, display_range
            
        # Use timefhuman as primary datetime parser for other cases
        try:
            # Let timefhuman handle most natural language expressions  
            logger.info(f"Parsing with timefhuman: '{text}'")
            parsed = timefhuman(text, now=local_now)
            
            if parsed:
                logger.info(f"Timefhuman parsed result: {parsed}")
                
                # CASE 1: Date range as list of tuples [(start, end)]
                if isinstance(parsed, list) and len(parsed) > 0 and isinstance(parsed[0], tuple):
                    start, end = parsed[0]
                    
                    # Ensure timezone awareness
                    if start.tzinfo is None:
                        start = start.replace(tzinfo=timezone.utc)
                    if end.tzinfo is None:
                        end = end.replace(tzinfo=timezone.utc)
                        
                    # Make end time inclusive (end of day)
                    if end.hour == 0 and end.minute == 0 and end.second == 0:
                        end = end.replace(hour=23, minute=59, second=59)
                        
                    # Create a human-readable display format
                    if start.date() == end.date():
                        display_range = start.strftime("%Y-%m-%d")
                    else:
                        display_range = f"{start.strftime('%Y-%m-%d')} to {end.strftime('%Y-%m-%d')}"
                    
                    logger.info(f"Parsed date range: {start} to {end}")
                    return start, end, display_range
                
                # CASE 2: Nested lists [[date1, date2]]
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
                
                # CASE 3: Simple list of dates [date1, date2]
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
                
                # CASE 4: Single datetime
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
                        return dt - timedelta(hours=24), dt, f"24h ending {dt.strftime('%Y-%m-%d %H:%M')}"
        
        except Exception as e:
            logger.debug(f"Timefhuman parsing failed: {e}")
        
        # Handle specific patterns that timefhuman might struggle with
        
        # Handle explicit date format "from YYYY-MM-DD to YYYY-MM-DD"
        explicit_date_pattern = r'^(?:from\s+)?(\d{4}-\d{2}-\d{2})\s+(?:to|through|until|and|-)\s+(\d{4}-\d{2}-\d{2})$'
        explicit_date_match = re.match(explicit_date_pattern, text)
        
        if explicit_date_match:
            start_date_str, end_date_str = explicit_date_match.groups()
            start_date = datetime.strptime(start_date_str, "%Y-%m-%d").date()
            end_date = datetime.strptime(end_date_str, "%Y-%m-%d").date()
            
            start_time = datetime.combine(start_date, datetime.min.time()).replace(tzinfo=timezone.utc)
            end_time = datetime.combine(end_date, datetime.max.time()).replace(hour=23, minute=59, second=59, tzinfo=timezone.utc)
            
            display_range = f"{start_date_str} to {end_date_str}"
            logger.info(f"Parsed explicit date range: {start_time} to {end_time}")
            return start_time, end_time, display_range
        
        # Month ranges (e.g., "January to February", "last January to February")
        month_names = "january|february|march|april|may|june|july|august|september|october|november|december"
        month_pattern = rf'^(?:from\s+)?(?:last\s+)?({month_names})\s+(?:to|through|until|and|-)\s+(?:last\s+)?({month_names})'
        month_range_match = re.match(month_pattern, text)
        
        if month_range_match:
            start_month, end_month = month_range_match.groups()
            is_last_year = 'last' in text
            date_tuple, display_range = self._handle_month_range(start_month, end_month, is_last_year)
            start_date, end_date = date_tuple
            
            start_time = datetime.combine(start_date, datetime.min.time()).replace(tzinfo=timezone.utc)
            end_time = datetime.combine(end_date, datetime.max.time()).replace(hour=23, minute=59, second=59, tzinfo=timezone.utc)
            
            logger.info(f"Parsed month range: {start_time} to {end_time}")
            return start_time, end_time, display_range
            
        # Weekday ranges (e.g., "Monday to Friday")
        weekday_names = "monday|tuesday|wednesday|thursday|friday|saturday|sunday"
        range_separators = "to|through|until|and|-"
        weekday_pattern = rf'^(?:from\s+)?(?:last\s+)?({weekday_names})\s+(?:{range_separators})\s+(?:last\s+)?({weekday_names})'
        weekday_range_match = re.match(weekday_pattern, text)
        
        if weekday_range_match:
            weekday_map = {
                'monday': 0, 'tuesday': 1, 'wednesday': 2, 'thursday': 3,
                'friday': 4, 'saturday': 5, 'sunday': 6
            }
            
            start_weekday_name, end_weekday_name = weekday_range_match.groups()
            start_weekday = weekday_map[start_weekday_name]
            end_weekday = weekday_map[end_weekday_name]
            
            current_date = datetime.now().date()
            current_weekday = current_date.weekday()
            
            # Check if "last" was mentioned in the query
            is_last_week = 'last' in text.lower()
            
            # Always look at the most recent past occurrence of the weekdays
            # Never look into the future, always use the most recent past days
            
            # Calculate days to go back to reach the most recent occurrence of each day
            days_to_start = (current_weekday - start_weekday) % 7
            if days_to_start == 0 and datetime.now().hour < 12:
                # If it's the same day but before noon, use today
                days_to_start = 0
            elif days_to_start == 0:
                # If it's the same day but after noon, use last week
                days_to_start = 7
                
            days_to_end = (current_weekday - end_weekday) % 7
            if days_to_end == 0 and datetime.now().hour < 12:
                # If it's the same day but before noon, use today
                days_to_end = 0
            elif days_to_end == 0:
                # If it's the same day but after noon, use last week
                days_to_end = 7
            
            # If "last" is explicitly mentioned, go back one more week
            if is_last_week:
                days_to_start += 7
                days_to_end += 7
                
            # Calculate the dates
            start_date = current_date - timedelta(days=days_to_start)
            end_date = current_date - timedelta(days=days_to_end)
            
            # Ensure end date is after or equal to start date
            if end_date < start_date:
                # For cases like "Friday to Monday" where Friday is before Monday in the week
                # but the most recent Monday might be later than the most recent Friday
                
                # Check if we need to go back one more week for the end date
                if (current_weekday > end_weekday) and (end_weekday < start_weekday):
                    # The end weekday is earlier in the week than start weekday
                    # and we've already passed the end weekday this week
                    end_date = end_date + timedelta(days=7)
                elif days_between := (7 + end_weekday - start_weekday) % 7:
                    # Handle cross-week ranges
                    end_date = start_date + timedelta(days=days_between)
            
            start_time = datetime.combine(start_date, datetime.min.time()).replace(tzinfo=timezone.utc)
            end_time = datetime.combine(end_date, datetime.max.time()).replace(hour=23, minute=59, second=59, tzinfo=timezone.utc)
            
            # Fixed dates in tests use "Previous" for all non-explicit "last" ranges
            if is_last_week:
                time_descriptor = "Last "
            else:
                time_descriptor = "Previous "
                
            display_range = f"{time_descriptor}{start_weekday_name.capitalize()} to {end_weekday_name.capitalize()} ({start_date.strftime('%Y-%m-%d')} to {end_date.strftime('%Y-%m-%d')})"
            
            logger.info(f"Parsed weekday range: {start_time} to {end_time}")
            return start_time, end_time, display_range
        
        # Try dateparser as a last resort
        try:
            parsed = dateparser.parse(text, settings={'RELATIVE_BASE': local_now})
            
            if parsed:
                if parsed.tzinfo is None:
                    parsed = parsed.replace(tzinfo=timezone.utc)
                
                if parsed.hour == 0 and parsed.minute == 0:
                    # Full day
                    return parsed, parsed.replace(hour=23, minute=59, second=59), parsed.strftime("%Y-%m-%d")
                else:
                    # 24h window
                    return parsed - timedelta(hours=24), parsed, f"24h ending {parsed.strftime('%Y-%m-%d %H:%M')}"
        except Exception as e:
            logger.debug(f"Dateparser failed: {e}")
        
        # Fall back to 24-hour window if all parsing attempts fail
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

                    # Send request to Gemini API with retry
                    response = self._generate_content_with_retry(
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

                    # Send request to Gemini API with retry
                    response = self._generate_content_with_retry(
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
        
    def _handle_month_range(self, start_month: str, end_month: str, is_last_year: bool = False) -> Tuple[Tuple[datetime.date, datetime.date], str]:
        """Handle month-to-month range expressions with smart year detection.
        
        Args:
            start_month: Name of the starting month (e.g., 'january')
            end_month: Name of the ending month (e.g., 'february')
            is_last_year: Whether to use last year's date for the range
            
        Returns:
            Tuple containing:
            - Tuple of (start_date, end_date) as date objects
            - Display range string
        """
        # Month name to number mapping
        month_map = {
            'january': 1, 'february': 2, 'march': 3, 'april': 4,
            'may': 5, 'june': 6, 'july': 7, 'august': 8,
            'september': 9, 'october': 10, 'november': 11, 'december': 12
        }
        
        # Get current date reference
        current_date = datetime.now().date()
        current_year = current_date.year
        
        # Determine the year for start month
        if is_last_year:
            year = current_year - 1
        else:
            year = current_year
            # If both months are future months, use previous year
            if month_map[start_month] > current_date.month and month_map[end_month] > current_date.month:
                year = current_year - 1
        
        # Create start date (first day of start month)
        start_date = datetime(year, month_map[start_month], 1).date()
        
        # Determine year for end month (handle year transitions)
        end_year = year
        if month_map[end_month] < month_map[start_month]:
            # Handle ranges like "November to January" that cross year boundary
            end_year = year + 1
            
        # Calculate end date (last day of end month)
        if month_map[end_month] == 12:  # December
            end_date = datetime(end_year, 12, 31).date()
        else:
            # Get the last day of the month by finding the first day of next month and going back one day
            next_month = month_map[end_month] + 1
            next_month_year = end_year
            end_date = datetime(next_month_year, next_month, 1).date() - timedelta(days=1)
        
        # Create user-friendly display string
        display_start = start_month.capitalize()
        display_end = end_month.capitalize()
        
        if year == end_year and year == current_year:
            display_range = f"{display_start} to {display_end} {year}"
        else:
            display_range = f"{display_start} {year} to {display_end} {end_year}"
            
        return (start_date, end_date), display_range
        
    def _handle_duration_format(self, match) -> Tuple[datetime, Optional[datetime], str]:
        """Handle standard duration formats (e.g., 24h, 3d, 1w).
        
        Args:
            match: Regex match object with groups for value and unit
            
        Returns:
            Tuple containing:
            - start_time: datetime at the beginning of the duration
            - end_time: datetime at the end of the duration or None
            - display_range: string representation of the duration
        """
        value, unit = match.groups()
        value = int(value)
        
        # Get current time in UTC
        end_time = datetime.now(timezone.utc)
        
        # Map units to timedelta arguments and display names
        unit_config = {
            'h': {'timedelta_kwarg': 'hours', 'name': 'hour'},
            'd': {'timedelta_kwarg': 'days', 'name': 'day'},
            'w': {'timedelta_kwarg': 'weeks', 'name': 'week'}
        }
        
        # Calculate the start time using the appropriate timedelta
        timedelta_args = {unit_config[unit]['timedelta_kwarg']: value}
        start_time = end_time - timedelta(**timedelta_args)
        
        # Create user-friendly display string
        unit_name = unit_config[unit]['name']
        plural = "s" if value > 1 else ""
        display_range = f"last {value} {unit_name}{plural}"
            
        return start_time, None, display_range
        
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
        
    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=1, max=10))
    def _generate_content_with_retry(self, model: str, contents: str, config: Any) -> Any:
        """Generate content with Gemini API with automatic retries.
        
        This method is a thin wrapper around the Gemini generate_content method
        that adds retry logic for handling transient errors.
        
        Args:
            model: The model name to use
            contents: The prompt content
            config: Generation configuration
            
        Returns:
            The Gemini API response
        """
        logger.info("Making Gemini API request with retries enabled")
        return self.gemini_client.models.generate_content(
            model=model,
            contents=contents,
            config=config
        )
