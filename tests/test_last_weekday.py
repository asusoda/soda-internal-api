from modules.summarizer.service import SummarizerService
from datetime import datetime, timezone

def test_last_weekday_range():
    """Test that 'last Wednesday to Friday' returns dates from the previous week."""
    service = SummarizerService()
    
    # Test with explicit "last" keyword
    timeframe = service.extract_timeframe_from_text("what happened last wednesday to friday?")
    print(f"Extracted timeframe: {timeframe}")
    
    start_date, end_date, display = service.parse_date_range(timeframe)
    print(f"Start date: {start_date}")
    print(f"End date: {end_date}")
    print(f"Display: {display}")
    
    # Get current date info
    current_date = datetime.now(timezone.utc).date()
    
    # Validate that the dates are in the past
    assert start_date.date() < current_date
    assert end_date.date() < current_date
    
    print("Test passed - 'last wednesday to friday' correctly parsed as past dates")

if __name__ == "__main__":
    test_last_weekday_range()