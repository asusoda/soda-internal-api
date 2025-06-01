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

class TestWeekdayNameParsing:
    """Test the bare weekday name parsing functionality (without prefixes) in SummarizerService"""
    
    def test_weekday_name_parsing(self, service_with_fixed_date):
        """Test parsing expressions like 'monday', 'friday', etc. (should behave like 'last monday')"""
        service = service_with_fixed_date
        
        # Current date is Monday, May 19, 2025 in our tests (this is weekday index 0)
        today = MockDatetime.now().date()
        assert today.weekday() == 0, "Test setup error: Today should be a Monday"
        
        # For each weekday, test that bare weekday name produces same result as "last [weekday]"
        for weekday_pair in [
            ("monday", "last monday"),       # Same as today (should be previous week)
            ("tuesday", "last tuesday"),     # After today's weekday (should be previous week)
            ("wednesday", "last wednesday"), # After today's weekday (should be previous week)
            ("thursday", "last thursday"),   # After today's weekday (should be previous week)
            ("friday", "last friday"),       # After today's weekday (should be previous week)
            ("saturday", "last saturday"),   # After today's weekday (should be previous week)
            ("sunday", "last sunday"),       # After today's weekday (should be previous week)
        ]:
            bare_weekday, relative_weekday = weekday_pair
            
            # Parse both forms
            start_bare, end_bare, display_bare = service.parse_date_range(bare_weekday)
            start_relative, end_relative, display_relative = service.parse_date_range(relative_weekday)
            
            # Both should produce the same date (except for display string)
            assert start_bare.date() == start_relative.date(), f"Expected {bare_weekday} to match {relative_weekday}, but got different dates"
            assert end_bare.date() == end_relative.date(), f"Expected {bare_weekday} to match {relative_weekday}, but got different dates"
            
            # Verify that weekdays from the past week are used
            weekday_date = start_bare.date()
            assert (today - weekday_date).days <= 7, f"Expected {bare_weekday} to be within past week"
            assert (today - weekday_date).days > 0, f"Expected {bare_weekday} to be in the past"
            
            # The display string should include the weekday name capitalized
            assert bare_weekday.capitalize() in display_bare, f"Expected {bare_weekday.capitalize()} to be in display string, got: {display_bare}"
            
    def test_capitalization_variations(self, service_with_fixed_date):
        """Test that capitalization variations are handled correctly"""
        service = service_with_fixed_date
        
        # Test with different capitalizations for weekday names
        start1, end1, _ = service.parse_date_range("monday")
        start2, end2, _ = service.parse_date_range("Monday")
        start3, end3, _ = service.parse_date_range("MONDAY")
        
        # All should give the same date range
        assert start1 == start2 == start3
        assert end1 == end2 == end3
    
    def test_with_whitespace_variations(self, service_with_fixed_date):
        """Test that whitespace variations are handled correctly"""
        service = service_with_fixed_date
        
        # Test with different whitespace
        start1, end1, _ = service.parse_date_range("monday")
        start2, end2, _ = service.parse_date_range(" monday ")  # Leading/trailing space
        
        # All should give the same date range
        assert start1 == start2
        assert end1 == end2
    
    def test_extracting_timeframe(self, service_with_fixed_date):
        """Test that weekday names are properly extracted from text"""
        service = service_with_fixed_date
        
        # Test extracting weekday names from various contexts
        timeframe = service.extract_timeframe_from_text("summarize monday please")
        assert timeframe == "monday"
        
        timeframe = service.extract_timeframe_from_text("show me what happened on friday")
        assert timeframe == "friday"
        
        # Should not extract weekday names that are part of "last weekday" expressions
        timeframe = service.extract_timeframe_from_text("show me what happened last friday")
        assert timeframe == "last friday"
        
        # Test with capitalization
        timeframe = service.extract_timeframe_from_text("show me Tuesday")
        assert timeframe == "tuesday"
    
    def test_timezone_awareness(self, service_with_fixed_date):
        """Test that all returned datetimes are timezone-aware"""
        service = service_with_fixed_date
        
        # Test with different weekdays
        for weekday in ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"]:
            start, end, _ = service.parse_date_range(weekday)
            
            # Both start and end times should be timezone-aware
            assert start.tzinfo is not None, f"Start time for '{weekday}' is not timezone-aware"
            assert end.tzinfo is not None, f"End time for '{weekday}' is not timezone-aware"
            
            # Both should be UTC
            assert start.tzinfo == timezone.utc, f"Start time for '{weekday}' is not in UTC"
            assert end.tzinfo == timezone.utc, f"End time for '{weekday}' is not in UTC"
            
            # Start should be at beginning of day (00:00:00)
            assert start.hour == 0
            assert start.minute == 0
            assert start.second == 0
            
            # End should be at end of day (23:59:59)
            assert end.hour == 23
            assert end.minute == 59
            assert end.second == 59

    def test_weekday_full_day(self, service_with_fixed_date):
        """Test that the parsed date range covers a full day"""
        service = service_with_fixed_date
        
        for weekday in ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"]:
            start, end, _ = service.parse_date_range(weekday)
            
            # Check that we're getting a full day (with some tolerance for precision)
            seconds_diff = (end - start).total_seconds()
            assert abs(seconds_diff - 86399) < 1.1, f"Expected full day duration for {weekday}, got {seconds_diff} seconds"
            # The difference should be almost exactly one day

# End of tests