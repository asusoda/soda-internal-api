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
        # Return Monday, May 19, 2025 as the fixed date (Monday has weekday index 0)
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

class TestSingleWeekdayParsing:
    """Test specifically that 'Monday' is not defaulting to 24h"""
    
    def test_monday_not_defaulting_to_24h(self, service_with_fixed_date):
        """Test that 'monday' is parsed as a weekday, not defaulting to 24h"""
        service = service_with_fixed_date
        
        # Extract the timeframe first (simulating command parsing)
        timeframe = service.extract_timeframe_from_text("monday")
        assert timeframe == "monday", f"Expected 'monday', got '{timeframe}'"
        
        # Parse the extracted timeframe to get start/end dates
        start, end, display = service.parse_date_range(timeframe)
        
        # Verify it's actually the previous Monday, not 24h default
        today = MockDatetime.now().date()
        expected_date = today - timedelta(days=7)  # Last Monday should be 7 days ago
        
        assert start.date() == expected_date, f"Expected {expected_date}, got {start.date()}"
        assert "24h" not in display, f"Display should not contain '24h', got '{display}'"
        assert "Monday" in display, f"Display should contain 'Monday', got '{display}'"
    
    def test_end_to_end_timeframe_extraction(self, service_with_fixed_date):
        """Test end-to-end extraction and parsing for various weekday queries"""
        service = service_with_fixed_date
        today = MockDatetime.now().date()
        
        test_cases = [
            ("monday", "monday", today - timedelta(days=7)),  # Last Monday (7 days ago)
            ("summarize monday", "monday", today - timedelta(days=7)),
            ("what happened on monday", "monday", today - timedelta(days=7)),
            ("friday", "friday", today - timedelta(days=3)),  # Last Friday (3 days ago)
            ("last monday", "last monday", today - timedelta(days=7)),
            ("last friday", "last friday", today - timedelta(days=3)),
        ]
        
        for query, expected_timeframe, expected_date in test_cases:
            # Extract timeframe
            timeframe = service.extract_timeframe_from_text(query)
            assert timeframe == expected_timeframe, f"For query '{query}', expected timeframe '{expected_timeframe}', got '{timeframe}'"
            
            # Parse the timeframe into date range
            start, end, display = service.parse_date_range(timeframe)
            
            # Verify date
            assert start.date() == expected_date, f"For query '{query}', expected date {expected_date}, got {start.date()}"
            assert "24h" not in display, f"For query '{query}', display should not contain '24h', got '{display}'"

# End of tests