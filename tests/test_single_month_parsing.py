import logging
import pytest
from datetime import datetime, timezone, timedelta
import sys
import os

# Add the project root to the Python path to import modules properly
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

# Configure basic logging to see what's happening
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

from modules.summarizer.service import SummarizerService

# Create a mock datetime module with a fixed now() function
class MockDatetime(datetime):
    @classmethod
    def now(cls, tz=None):
        # Return May 18, 2025 as the fixed date
        fixed_date = datetime(2025, 5, 18, tzinfo=timezone.utc)
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

class TestSingleMonthParsing:
    """Test specifically that 'January' is not defaulting to 24h"""
    
    def test_january_not_defaulting_to_24h(self, service_with_fixed_date):
        """Test that 'january' is parsed as a month, not defaulting to 24h"""
        service = service_with_fixed_date
        
        # Extract the timeframe first (simulating command parsing)
        timeframe = service.extract_timeframe_from_text("january")
        assert timeframe == "january", f"Expected 'january', got '{timeframe}'"
        
        # Parse the extracted timeframe to get start/end dates
        start, end, display = service.parse_date_range(timeframe)
        
        # Verify it's actually January 2025, not 24h default
        assert start.year == 2025, f"Expected year 2025, got {start.year}"
        assert start.month == 1, f"Expected month 1, got {start.month}"
        assert start.day == 1, f"Expected day 1, got {start.day}"
        assert end.month == 1, f"Expected month 1, got {end.month}"
        assert end.day == 31, f"Expected day 31, got {end.day}"
        assert "24h" not in display, f"Display should not contain '24h', got '{display}'"
    
    def test_end_to_end_timeframe_extraction(self, service_with_fixed_date):
        """Test end-to-end extraction and parsing for various month queries"""
        service = service_with_fixed_date
        
        test_cases = [
            ("january", "january", 2025, 1),
            ("summarize january", "january", 2025, 1),
            ("what happened in january", "january", 2025, 1),
            ("june", "june", 2024, 6),
            ("last january", "last january", 2025, 1),
            ("last june", "last june", 2024, 6),
        ]
        
        for query, expected_timeframe, expected_year, expected_month in test_cases:
            # Extract timeframe
            timeframe = service.extract_timeframe_from_text(query)
            assert timeframe == expected_timeframe, f"For query '{query}', expected timeframe '{expected_timeframe}', got '{timeframe}'"
            
            # Parse the timeframe into date range
            start, end, display = service.parse_date_range(timeframe)
            
            # Verify year and month
            assert start.year == expected_year, f"For query '{query}', expected year {expected_year}, got {start.year}"
            assert start.month == expected_month, f"For query '{query}', expected month {expected_month}, got {start.month}"
            assert "24h" not in display, f"For query '{query}', display should not contain '24h', got '{display}'"

# End of tests