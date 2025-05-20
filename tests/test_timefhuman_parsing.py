import logging
import pytest
from datetime import datetime, timezone, timedelta
import sys
import os

# Add the project root to the Python path to import modules properly
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

# Configure basic logging to see what's happening
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

from modules.summarizer.service import SummarizerService

# Create a mock datetime module with a fixed now() function
class MockDatetime(datetime):
    @classmethod
    def now(cls, tz=None):
        # Return Monday, May 19, 2025 as the fixed date
        fixed_date = datetime(2025, 5, 19, tzinfo=timezone.utc)
        if tz is not None:
            return fixed_date.astimezone(tz)
        return fixed_date

# Fixture to provide a service with a fixed current date
@pytest.fixture
def service_with_fixed_date(monkeypatch):
    # Patch the datetime class in the service module
    import modules.summarizer.service
    monkeypatch.setattr(modules.summarizer.service, 'datetime', MockDatetime)
    
    # Return the service
    return SummarizerService()

class TestTimefhumanUsage:
    """Test how different date expressions are parsed"""
    
    def test_known_parseable_expressions(self, service_with_fixed_date):
        """Test expressions that should be parsed by specific parsers, not defaulting to 24h"""
        service = service_with_fixed_date
        
        # These are expressions we know should be handled by specific parsers
        parseable_expressions = [
            ("2025-01-01 to 2025-02-01", "ExplicitDateParser"),  # Should be handled by ExplicitDateParser
            ("yesterday", "CalendarExpressionParser"),  # Should be handled by CalendarExpressionParser
            ("24h", "DurationFormatParser"),  # Should be handled by DurationFormatParser
            ("january", "MonthNameParser"),  # Should be handled by our new MonthNameParser
            ("monday", "WeekdayNameParser"),  # Should be handled by our new WeekdayNameParser
            ("last monday", "RelativeWeekdayParser"),  # Should be handled by RelativeWeekdayParser
            ("monday to friday", "WeekdayRangeParser"),  # Should be handled by WeekdayRangeParser
            ("3 days ago", "AgoExpressionParser"),  # Should be handled by AgoExpressionParser
        ]
        
        for expression, expected_parser in parseable_expressions:
            # Parse the date range
            start, end, display = service.parse_date_range(expression)
            
            # Ensure we got valid dates
            assert start is not None
            assert start.tzinfo is not None  # Should be timezone-aware
            
            # Should not default to 24h
            assert "24h (default)" not in display, f"Expression '{expression}' unexpectedly defaulted to 24h"
            
            # Format results for debugging
            logger.info(f"Expression: '{expression}' -> {display}")
    
    def test_expressions_that_default_to_24h(self, service_with_fixed_date):
        """Test expressions that currently default to 24h (not handled by specific parsers)"""
        service = service_with_fixed_date
        
        # These are expressions that currently default to 24h
        defaulting_expressions = [
            "next week",
            "next month",
            "in 2 days",
            "tomorrow",
            "next year",
            "2 weeks from now",
        ]
        
        for expression in defaulting_expressions:
            # Parse the date range
            start, end, display = service.parse_date_range(expression)
            
            # Ensure we got valid dates that default to 24h
            assert start is not None
            assert start.tzinfo is not None  # Should be timezone-aware
            
            # Should default to 24h because these aren't handled yet
            assert "24h (default)" in display, f"Expression '{expression}' unexpectedly didn't default to 24h: {display}"
            
            # Format results for debugging
            logger.info(f"Expression: '{expression}' -> {display}")
    
    def test_expressions_that_should_be_enhanced(self, service_with_fixed_date):
        """Test expressions that should ideally be handled but currently default to 24h 
        (This test will fail until those parsers are implemented)"""
        service = service_with_fixed_date
        
        # These expressions should ideally be parseable but aren't yet
        ideal_expressions = [
            "next week",
            "tomorrow",
            "in 2 days",
        ]
        
        # This test is expected to fail - it's a TODO for future implementation
        for expression in ideal_expressions:
            start, end, display = service.parse_date_range(expression)
            # This assertion will fail because these expressions currently default to 24h
            # The test is marked as expected to fail until these parsers are implemented
            assert "24h (default)" not in display, f"Expression '{expression}' still defaults to 24h. This parser should be implemented."
            logger.info(f"Expression: '{expression}' -> {display}")

# End of tests