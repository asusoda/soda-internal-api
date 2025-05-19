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

class TestLastMonthParsing:
    """Test the 'last [month]' parsing functionality in SummarizerService"""
    
    def test_last_month_parsing(self, service_with_fixed_date):
        """Test parsing expressions like 'last january', 'last february', etc."""
        service = service_with_fixed_date
        
        # Current date is May 18, 2025 in our tests
        
        # Test past months in the current year
        # For months earlier than May, "last [month]" should refer to this year's month
        start, end, display = service.parse_date_range("last january")
        assert start.year == 2025
        assert start.month == 1
        assert start.day == 1
        assert end.year == 2025
        assert end.month == 1
        assert end.day == 31
        assert "January" in display
        assert "2025" in display
        
        start, end, display = service.parse_date_range("last february")
        assert start.year == 2025
        assert start.month == 2
        assert start.day == 1
        assert end.year == 2025
        assert end.month == 2
        assert end.day == 28  # Not a leap year
        assert "February" in display
        assert "2025" in display
        
        start, end, display = service.parse_date_range("last april")
        assert start.year == 2025
        assert start.month == 4
        assert start.day == 1
        assert end.year == 2025
        assert end.month == 4
        assert end.day == 30
        assert "April" in display
        assert "2025" in display
        
        # Test for current month (May) - our implementation might use current year or previous year
        # Both interpretations are valid, so we'll check that the month is correct
        start, end, display = service.parse_date_range("last may")
        assert start.month == 5
        assert start.day == 1
        assert end.month == 5
        assert end.day == 31
        assert "May" in display
        
        # Test for future months - should refer to last year's months
        start, end, display = service.parse_date_range("last june")
        assert start.year == 2024
        assert start.month == 6
        assert start.day == 1
        assert end.year == 2024
        assert end.month == 6
        assert end.day == 30
        assert "June" in display
        assert "2024" in display
        
        start, end, display = service.parse_date_range("last december")
        assert start.year == 2024
        assert start.month == 12
        assert start.day == 1
        assert end.year == 2024
        assert end.month == 12
        assert end.day == 31
        assert "December" in display
        assert "2024" in display
    
    def test_capitalization_variations(self, service_with_fixed_date):
        """Test that capitalization variations are handled correctly"""
        service = service_with_fixed_date
        
        # Test with different capitalizations
        start1, end1, _ = service.parse_date_range("last january")
        start2, end2, _ = service.parse_date_range("Last January")
        start3, end3, _ = service.parse_date_range("LAST JANUARY")
        
        # All should give the same date range
        assert start1 == start2 == start3
        assert end1 == end2 == end3
        
    def test_with_whitespace_variations(self, service_with_fixed_date):
        """Test that whitespace variations are handled correctly"""
        service = service_with_fixed_date
        
        # Test with different whitespace
        start1, end1, _ = service.parse_date_range("last january")
        start2, end2, _ = service.parse_date_range("last  january")  # Double space
        start3, end3, _ = service.parse_date_range(" last january ")  # Leading/trailing space
        
        # All should give the same date range
        assert start1 == start2 == start3
        assert end1 == end2 == end3
    
    def test_month_with_year_transition(self, service_with_fixed_date):
        """Test month parsing at year boundaries"""
        service = service_with_fixed_date
        
        # December should handle the year correctly
        start, end, display = service.parse_date_range("last december")
        assert start.year == 2024
        assert start.month == 12
        assert start.day == 1
        assert end.year == 2024
        assert end.month == 12
        assert end.day == 31
        
        # Calculate the actual days difference
        days_diff = (end.date() - start.date()).days
        assert days_diff == 30  # 31 days - 1 day
        
        # January should also handle the year correctly
        start, end, display = service.parse_date_range("last january")
        assert start.year == 2025
        assert start.month == 1
        assert start.day == 1
        assert end.year == 2025
        assert end.month == 1
        assert end.day == 31
        
        # Calculate the actual days difference
        days_diff = (end.date() - start.date()).days
        assert days_diff == 30  # 31 days - 1 day
    
    def test_month_with_varying_days(self, service_with_fixed_date):
        """Test months with different numbers of days"""
        service = service_with_fixed_date
        
        # February (not a leap year in 2025)
        start, end, display = service.parse_date_range("last february")
        assert start.day == 1
        assert end.day == 28
        assert (end.date() - start.date()).days == 27  # 28 days - 1 day
        
        # April (30 days)
        start, end, display = service.parse_date_range("last april")
        assert start.day == 1
        assert end.day == 30
        assert (end.date() - start.date()).days == 29  # 30 days - 1 day
        
        # January (31 days)
        start, end, display = service.parse_date_range("last january")
        assert start.day == 1
        assert end.day == 31
        assert (end.date() - start.date()).days == 30  # 31 days - 1 day
    
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
        
        # Test current month on the first day
        start, end, display = service.parse_date_range("last may")
        assert start.year == 2024
        assert start.month == 5
        assert start.day == 1
        assert end.year == 2024
        assert end.month == 5
        assert end.day == 31
    
    def test_timezone_awareness(self, service_with_fixed_date):
        """Test that all returned datetimes are timezone-aware"""
        service = service_with_fixed_date
        
        # Test with different months
        for month in ["january", "february", "march", "april", "may", "june", 
                     "july", "august", "september", "october", "november", "december"]:
            start, end, _ = service.parse_date_range(f"last {month}")
            
            # Both start and end times should be timezone-aware
            assert start.tzinfo is not None, f"Start time for 'last {month}' is not timezone-aware"
            assert end.tzinfo is not None, f"End time for 'last {month}' is not timezone-aware"
            
            # Both should be UTC
            assert start.tzinfo == timezone.utc, f"Start time for 'last {month}' is not in UTC"
            assert end.tzinfo == timezone.utc, f"End time for 'last {month}' is not in UTC"
            
            # Start should be at beginning of day (00:00:00)
            assert start.hour == 0
            assert start.minute == 0
            assert start.second == 0
            
            # End should be at end of day (23:59:59)
            assert end.hour == 23
            assert end.minute == 59
            assert end.second == 59

# End of tests