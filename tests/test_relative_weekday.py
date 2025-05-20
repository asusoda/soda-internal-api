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
        # Return May 18, 2025 as the fixed date (a Sunday)
        fixed_date = datetime(2025, 5, 18, 12, 30, 0, tzinfo=timezone.utc)
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

class TestRelativeWeekdayExpressions:
    """Test parsing expressions like 'last Monday', 'previous Tuesday', etc."""
    
    def test_last_weekday(self, service_with_fixed_date):
        """Test expressions like 'last Monday', 'last Tuesday', etc."""
        service = service_with_fixed_date
        today = MockDatetime.now(timezone.utc).date()  # Sunday, May 18, 2025
        
        # Test "last Monday" (should be 7 days ago)
        start, end, display = service.parse_date_range("last monday")
        expected_date = today - timedelta(days=6)  # Monday was 6 days ago
        assert start.date() == expected_date
        assert "Monday" in display or "monday" in display.lower()
        assert end.date() == start.date()  # Should be a single day
        
        # Test "last Friday" (should be 2 days ago)
        start, end, display = service.parse_date_range("last friday")
        expected_date = today - timedelta(days=2)  # Friday was 2 days ago
        assert start.date() == expected_date
        assert "Friday" in display or "friday" in display.lower()
        assert end.date() == start.date()
        
        # Test "last Sunday" (should be 7 days ago, not today)
        start, end, display = service.parse_date_range("last sunday")
        expected_date = today - timedelta(days=7)  # Last Sunday, not today
        assert start.date() == expected_date
        assert "Sunday" in display or "sunday" in display.lower()
        assert end.date() == start.date()
    
    def test_previous_weekday(self, service_with_fixed_date):
        """Test expressions like 'previous Monday', 'previous Tuesday', etc."""
        service = service_with_fixed_date
        today = MockDatetime.now(timezone.utc).date()  # Sunday, May 18, 2025
        
        # Test "previous Monday" (should be same as "last Monday")
        start, end, display = service.parse_date_range("previous monday")
        expected_date = today - timedelta(days=6)  # Monday was 6 days ago
        assert start.date() == expected_date
        assert "Monday" in display or "monday" in display.lower()
        assert "Previous" in display or "previous" in display.lower()
        
        # Test "previous Wednesday" (should be 4 days ago)
        start, end, display = service.parse_date_range("previous wednesday")
        expected_date = today - timedelta(days=4)  # Wednesday was 4 days ago
        assert start.date() == expected_date
        assert "Wednesday" in display or "wednesday" in display.lower()
        assert "Previous" in display or "previous" in display.lower()
    
    def test_last_vs_this_weekday(self, service_with_fixed_date, monkeypatch):
        """Test difference between 'last Monday' and 'this Monday' when today is Monday"""
        # Create a mock datetime that returns a Monday
        class MondayMockDatetime(datetime):
            @classmethod
            def now(cls, tz=None):
                # Return May 12, 2025 as the fixed date (a Monday)
                fixed_date = datetime(2025, 5, 12, 12, 30, 0, tzinfo=timezone.utc)
                if tz is not None:
                    return fixed_date.astimezone(tz)
                return fixed_date
        
        # Patch with Monday datetime
        import modules.summarizer.service
        monkeypatch.setattr(modules.summarizer.service, 'datetime', MondayMockDatetime)
        
        # Create a new service instance
        service = SummarizerService()
        today = MondayMockDatetime.now(timezone.utc).date()  # Monday, May 12, 2025
        
        # Test "last Monday" (should be 7 days ago when today is Monday)
        start, end, display = service.parse_date_range("last monday")
        expected_date = today - timedelta(days=7)  # Last Monday
        assert start.date() == expected_date
        assert "Monday" in display or "monday" in display.lower()
        assert "Last" in display or "last" in display.lower()
        
        # Test "this Monday" (should be today when today is Monday)
        start, end, display = service.parse_date_range("this monday")
        assert start.date() == today
        assert "Monday" in display or "monday" in display.lower()
        assert "This" in display or "this" in display.lower()
    
    def test_capitalization_variations(self, service_with_fixed_date):
        """Test that capitalization variations are handled correctly"""
        service = service_with_fixed_date
        
        # Test with different capitalizations
        start1, end1, _ = service.parse_date_range("last monday")
        start2, end2, _ = service.parse_date_range("Last Monday")
        start3, end3, _ = service.parse_date_range("LAST MONDAY")
        
        # All should give the same date range
        assert start1 == start2 == start3
        assert end1 == end2 == end3
    
    def test_with_whitespace_variations(self, service_with_fixed_date):
        """Test that whitespace variations are handled correctly"""
        service = service_with_fixed_date
        
        # Test with different whitespace
        start1, end1, _ = service.parse_date_range("last monday")
        start2, end2, _ = service.parse_date_range("last  monday")  # Double space
        start3, end3, _ = service.parse_date_range(" last monday ")  # Leading/trailing space
        
        # All should give the same date range
        assert start1 == start2 == start3
        assert end1 == end2 == end3
    
    def test_combined_expressions(self, service_with_fixed_date):
        """Test extraction of relative weekday expressions from sentences"""
        service = service_with_fixed_date
        
        # Test extraction from questions
        timeframe = service.extract_timeframe_from_text("What happened last Tuesday?")
        assert timeframe is not None
        assert "tuesday" in timeframe.lower()
        
        timeframe = service.extract_timeframe_from_text("Can you summarize what people were saying previous Friday?")
        assert timeframe is not None
        assert "friday" in timeframe.lower()
        
        timeframe = service.extract_timeframe_from_text("What was discussed last Monday in this channel?")
        assert timeframe is not None
        assert "monday" in timeframe.lower()
    
    def test_timezone_awareness(self, service_with_fixed_date):
        """Test timezone awareness in relative weekday expressions"""
        service = service_with_fixed_date
        
        # Test that all returned datetimes are timezone-aware
        for weekday in ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"]:
            start, end, _ = service.parse_date_range(f"last {weekday}")
            
            # Start time should be timezone-aware
            assert start.tzinfo is not None, f"Start time for 'last {weekday}' is not timezone-aware"
            assert end.tzinfo is not None, f"End time for 'last {weekday}' is not timezone-aware"
                
            # Should be in UTC
            assert start.tzinfo == timezone.utc, f"Start time for 'last {weekday}' is not in UTC"
            assert end.tzinfo == timezone.utc, f"End time for 'last {weekday}' is not in UTC"
            
            # Start should be at beginning of day (00:00:00)
            assert start.hour == 0
            assert start.minute == 0
            assert start.second == 0
            
            # End should be at end of day (23:59:59)
            assert end.hour == 23
            assert end.minute == 59
            assert end.second == 59

# End of tests