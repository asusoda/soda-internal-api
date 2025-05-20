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

class TestTimefhumanFallback:
    """Test that timefhuman is still used as a fallback for complex date expressions"""
    
    def test_complex_date_expressions(self, service_with_fixed_date):
        """Test that complex date expressions use timefhuman fallback"""
        service = service_with_fixed_date
        
        # These expressions should be handled by either the parsers or timefhuman fallback
        test_cases = [
            "2025-01-01 to 2025-02-01",  # Should be handled by ExplicitDateParser
            "next week",  # Should be handled by a relative time parser
            "2 days ago",  # Should be handled by AgoExpressionParser
            "from May 1 to May 15",  # Should be handled by MonthRangeParser
            "yesterday"  # Should be handled by CalendarExpressionParser
        ]
        
        for expression in test_cases:
            # Parse the date range
            start, end, display = service.parse_date_range(expression)
            
            # Make sure we got valid dates
            assert start is not None
            assert start.tzinfo is not None  # Should be timezone-aware
            
            # It shouldn't default to 24h
            assert "24h (default)" not in display, f"Expression '{expression}' defaulted to 24h"
            
            # For validation purposes, logging the results
            print(f"Expression: '{expression}' -> Start: {start}, End: {end}, Display: '{display}'")
    
    def test_timefhuman_vs_default_behavior(self, service_with_fixed_date, monkeypatch):
        """Test to ensure timefhuman actually parses differently than the default 24h window"""
        service = service_with_fixed_date
        
        # Use a date expression that should be parsed by timefhuman
        expression = "May 1 to May 15, 2025"
        
        # Get the normal parsing result
        start_normal, end_normal, display_normal = service.parse_date_range(expression)
        
        # Now mock _parse_with_timefhuman to return the default behavior
        def mock_parse(*args, **kwargs):
            reference_date = args[1] if len(args) > 1 else None
            if reference_date is None:
                reference_date = datetime.now()
            
            end_time = reference_date.replace(tzinfo=timezone.utc)
            start_time = end_time - timedelta(hours=24)
            return start_time, None, "24h (default)"
            
        # Patch the method
        import modules.summarizer.service
        monkeypatch.setattr(service, '_parse_with_timefhuman', mock_parse)
        
        # Get the result with mocked timefhuman
        start_mock, end_mock, display_mock = service.parse_date_range(expression)
        
        # The results should be different
        assert start_normal != start_mock, "Timefhuman fallback not being used"
        assert display_normal != display_mock, "Timefhuman fallback not being used"
        assert "24h (default)" not in display_normal, "Normal parsing incorrectly defaulted to 24h"
        assert "24h (default)" in display_mock, "Mocked parsing should default to 24h"

# End of tests