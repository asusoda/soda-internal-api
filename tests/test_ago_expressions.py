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
        fixed_date = datetime(2025, 5, 18, 12, 30, 0, tzinfo=timezone.utc)  # Using 12:30 to test time handling
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

class TestAgoExpressions:
    """Test parsing 'ago' expressions like '3 days ago', 'a week ago', etc."""
    
    def test_days_ago(self, service_with_fixed_date):
        """Test expressions like 'N days ago'"""
        service = service_with_fixed_date
        today = MockDatetime.now(timezone.utc)
        
        # Test "1 day ago"
        start, end, display = service.parse_date_range("1 day ago")
        assert start.date() == today.date() - timedelta(days=1)
        assert start.day == 17  # May 17th (1 day before May 18th)
        assert "1 day ago" in display.lower() or "yesterday" in display.lower()
        
        # Test "3 days ago"
        start, end, display = service.parse_date_range("3 days ago")
        assert start.date() == today.date() - timedelta(days=3)
        assert start.day == 15  # May 15th (3 days before May 18th)
        assert "3 days ago" in display.lower() or "may 15" in display.lower()
        
        # Test "10 days ago"
        start, end, display = service.parse_date_range("10 days ago")
        assert start.date() == today.date() - timedelta(days=10)
        assert start.day == 8  # May 8th (10 days before May 18th)
        assert "10 days ago" in display.lower() or "may 8" in display.lower()
    
    def test_weeks_ago(self, service_with_fixed_date):
        """Test expressions like 'N weeks ago'"""
        service = service_with_fixed_date
        today = MockDatetime.now(timezone.utc)
        
        # Test "1 week ago"
        start, end, display = service.parse_date_range("1 week ago")
        assert start.date() == today.date() - timedelta(weeks=1)
        assert "1 week ago" in display.lower() or "week" in display.lower()
        
        # Test "2 weeks ago"
        start, end, display = service.parse_date_range("2 weeks ago")
        assert start.date() == today.date() - timedelta(weeks=2)
        assert "2 weeks ago" in display.lower() or "weeks" in display.lower()
        
        # Test "4 weeks ago"
        start, end, display = service.parse_date_range("4 weeks ago")
        assert start.date() == today.date() - timedelta(weeks=4)
        assert "4 weeks ago" in display.lower() or "weeks" in display.lower()
    
    def test_months_ago(self, service_with_fixed_date):
        """Test expressions like 'N months ago'"""
        service = service_with_fixed_date
        today = MockDatetime.now(timezone.utc)
        
        # Test "1 month ago" - should be April 18th
        start, end, display = service.parse_date_range("1 month ago")
        assert start.year == today.year
        assert start.month == 4  # April
        assert start.day == today.day  # Same day of month
        assert "1 month ago" in display.lower() or "april" in display.lower()
        
        # Test "3 months ago" - should be February 18th
        start, end, display = service.parse_date_range("3 months ago")
        assert start.year == today.year
        assert start.month == 2  # February
        assert start.day == today.day  # Same day of month or the last day of month if the target month is shorter
        assert "3 months ago" in display.lower() or "february" in display.lower()
        
        # Test "6 months ago" - should be November 18th of previous year
        start, end, display = service.parse_date_range("6 months ago")
        expected_date = today - timedelta(days=180)  # Approximate
        assert abs((start.date() - expected_date.date()).days) <= 5  # Allow some wiggle room for month length differences
        assert "6 months ago" in display.lower() or "november" in display.lower()
    
    def test_years_ago(self, service_with_fixed_date):
        """Test expressions like 'N years ago'"""
        service = service_with_fixed_date
        today = MockDatetime.now(timezone.utc)
        
        # Test "1 year ago"
        start, end, display = service.parse_date_range("1 year ago")
        assert start.year == today.year - 1
        assert start.month == today.month
        assert start.day == today.day
        assert "1 year ago" in display.lower() or "2024" in display
        
        # Test "2 years ago"
        start, end, display = service.parse_date_range("2 years ago")
        assert start.year == today.year - 2
        assert start.month == today.month
        assert start.day == today.day
        assert "2 years ago" in display.lower() or "2023" in display
    
    def test_indefinite_articles(self, service_with_fixed_date):
        """Test expressions with indefinite articles like 'a day ago', 'an hour ago'"""
        service = service_with_fixed_date
        today = MockDatetime.now(timezone.utc)
        
        # Test "a day ago"
        start, end, display = service.parse_date_range("a day ago")
        assert start.date() == today.date() - timedelta(days=1)
        assert "day ago" in display.lower() or "yesterday" in display.lower()
        
        # Test "a week ago"
        start, end, display = service.parse_date_range("a week ago")
        assert start.date() == today.date() - timedelta(weeks=1)
        assert "week ago" in display.lower() or "week" in display.lower()
        
        # Test "a month ago"
        start, end, display = service.parse_date_range("a month ago")
        assert start.year == today.year
        assert start.month == 4  # April
        assert "month ago" in display.lower() or "april" in display.lower()
        
        # Test "a year ago"
        start, end, display = service.parse_date_range("a year ago")
        assert start.year == today.year - 1
        assert "year ago" in display.lower() or "2024" in display
    
    def test_text_numbers(self, service_with_fixed_date):
        """Test expressions with text numbers like 'two days ago', 'three weeks ago'"""
        service = service_with_fixed_date
        today = MockDatetime.now(timezone.utc)
        
        # Test "two days ago"
        start, end, display = service.parse_date_range("two days ago")
        assert start.date() == today.date() - timedelta(days=2)
        assert "2 days ago" in display.lower() or "days ago" in display.lower()
        
        # Test "three weeks ago"
        start, end, display = service.parse_date_range("three weeks ago")
        assert start.date() == today.date() - timedelta(weeks=3)
        assert "3 weeks ago" in display.lower() or "weeks ago" in display.lower()
        
        # Test "six months ago"
        start, end, display = service.parse_date_range("six months ago")
        expected_date = today - timedelta(days=180)  # Approximate
        assert abs((start.date() - expected_date.date()).days) <= 5  # Allow wiggle room
        assert "6 months ago" in display.lower() or "months ago" in display.lower()
    
    def test_combined_expressions(self, service_with_fixed_date):
        """Test extraction of 'ago' expressions from sentences"""
        service = service_with_fixed_date
        
        # Test extraction from questions
        timeframe = service.extract_timeframe_from_text("What happened 3 days ago?")
        assert timeframe is not None
        assert "3" in timeframe and "day" in timeframe.lower()
        
        timeframe = service.extract_timeframe_from_text("Can you summarize what people were saying two weeks ago?")
        assert timeframe is not None
        assert ("2" in timeframe or "two" in timeframe.lower()) and "week" in timeframe.lower()
        
        timeframe = service.extract_timeframe_from_text("What was discussed a month ago in this channel?")
        assert timeframe is not None
        assert "month" in timeframe.lower()
    
    def test_timezone_awareness(self, service_with_fixed_date):
        """Test timezone awareness in 'ago' expressions"""
        service = service_with_fixed_date
        
        # Test that all returned datetimes are timezone-aware
        for expression in ["1 day ago", "3 days ago", "a week ago", "2 weeks ago", 
                         "a month ago", "6 months ago", "a year ago"]:
            start, end, _ = service.parse_date_range(expression)
            
            # Start time should be timezone-aware
            assert start.tzinfo is not None, f"Start time for '{expression}' is not timezone-aware"
            if end is not None:
                assert end.tzinfo is not None, f"End time for '{expression}' is not timezone-aware"
                
            # Should be in UTC
            assert start.tzinfo == timezone.utc, f"Start time for '{expression}' is not in UTC"
            if end is not None:
                assert end.tzinfo == timezone.utc, f"End time for '{expression}' is not in UTC"

# End of tests