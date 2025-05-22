import pytest
from datetime import datetime, timezone, timedelta
import sys
import os

# Add the project root to the Python path to import modules properly
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

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

class TestMonthNameParsing:
    """Test the month name parsing functionality (without 'last' prefix) in SummarizerService"""
    
    def test_month_name_parsing(self, service_with_fixed_date):
        """Test parsing expressions like 'january', 'february', etc. (should behave like 'last january')"""
        service = service_with_fixed_date
        
        # Current date is May 18, 2025 in our tests
        
        # Test past months in the current year
        # For months earlier than May, just the month name should refer to this year's month, same as "last [month]"
        for month_name, last_month_name in [
            ("january", "last january"),
            ("february", "last february"),
            ("april", "last april")
        ]:
            start, end, display = service.parse_date_range(month_name)
            start_last, end_last, display_last = service.parse_date_range(last_month_name)
            
            # Both should return the same date range
            assert start == start_last
            assert end == end_last
            assert display == display_last
            
            # Ensure that results are for this year
            assert start.year == 2025
            assert start.day == 1
            assert end.year == 2025
        
        # Test for current month (May) - should match "last may" behavior
        start, end, display = service.parse_date_range("may")
        start_last, end_last, display_last = service.parse_date_range("last may")
        
        # Both should return the same date range
        assert start == start_last
        assert end == end_last
        assert display == display_last
        
        # Test for future months - should match "last [month]" behavior (refer to last year's months)
        for month_name, last_month_name in [
            ("june", "last june"),
            ("december", "last december")
        ]:
            start, end, display = service.parse_date_range(month_name)
            start_last, end_last, display_last = service.parse_date_range(last_month_name)
            
            # Both should return the same date range
            assert start == start_last
            assert end == end_last
            assert display == display_last
            
            # Ensure that results are for last year
            assert start.year == 2024
            assert start.day == 1
            assert end.year == 2024
    
    def test_capitalization_variations(self, service_with_fixed_date):
        """Test that capitalization variations are handled correctly"""
        service = service_with_fixed_date
        
        # Test with different capitalizations
        start1, end1, _ = service.parse_date_range("january")
        start2, end2, _ = service.parse_date_range("January")
        start3, end3, _ = service.parse_date_range("JANUARY")
        
        # All should give the same date range
        assert start1 == start2 == start3
        assert end1 == end2 == end3
    
    def test_with_whitespace_variations(self, service_with_fixed_date):
        """Test that whitespace variations are handled correctly"""
        service = service_with_fixed_date
        
        # Test with different whitespace
        start1, end1, _ = service.parse_date_range("january")
        start2, end2, _ = service.parse_date_range(" january ")  # Leading/trailing space
        
        # All should give the same date range
        assert start1 == start2
        assert end1 == end2
    
    def test_extracting_timeframe(self, service_with_fixed_date):
        """Test that month names are properly extracted from text"""
        service = service_with_fixed_date
        
        # Test extracting month names from various contexts
        timeframe = service.extract_timeframe_from_text("summarize january please")
        assert timeframe == "january"
        
        timeframe = service.extract_timeframe_from_text("show me what happened in march")
        assert timeframe == "march"
        
        # Should not extract month names that are part of "last month"
        timeframe = service.extract_timeframe_from_text("show me what happened last march")
        assert timeframe == "last march"
        
        # Test with capitalization
        timeframe = service.extract_timeframe_from_text("show me June")
        assert timeframe == "june"
    
    def test_month_with_date_on_first_day(self, service_with_fixed_date, monkeypatch):
        """Test behavior when current date is first day of month"""
        # Create a new mock datetime that returns the first day of a month
        class FirstDayMockDatetime(datetime):
            @classmethod
            def now(cls, tz=None):
                # Return May 1, 2025 as the fixed date
                fixed_date = datetime(2025, 5, 1, tzinfo=timezone.utc)
                if tz is not None:
                    return fixed_date.astimezone(tz)
                return fixed_date
        
        # Patch with the first day datetime
        import modules.summarizer.service
        monkeypatch.setattr(modules.summarizer.service, 'datetime', FirstDayMockDatetime)
        
        # Create a new service instance 
        service = SummarizerService()
        
        # Test current month on the first day (should be treated like last year)
        start, end, display = service.parse_date_range("may")
        assert start.year == 2024
        assert start.month == 5
        assert start.day == 1
        assert end.year == 2024
        assert end.month == 5
        assert end.day == 31

# End of tests