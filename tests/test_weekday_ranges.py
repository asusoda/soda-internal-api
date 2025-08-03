from modules.summarizer.service import SummarizerService
from datetime import datetime, timezone, timedelta

def test_weekday_ranges():
    """Test different variations of weekday range parsing."""
    service = SummarizerService()
    
    # Get current date info
    current_date = datetime.now(timezone.utc).date()
    current_weekday = current_date.weekday()
    
    print(f"Current date: {current_date}, Day of week: {current_weekday} (0=Monday, 6=Sunday)")
    
    # Test cases
    test_cases = [
        "what happened wednesday to friday?",
        "what happened last wednesday to friday?",
        "monday to wednesday",
        "friday to monday",
    ]
    
    for query in test_cases:
        print(f"\nTesting: '{query}'")
        timeframe = service.extract_timeframe_from_text(query)
        print(f"Extracted timeframe: {timeframe}")
        
        start_date, end_date, display = service.parse_date_range(timeframe)
        print(f"Start date: {start_date}")
        print(f"End date: {end_date}")
        print(f"Display: {display}")
        
        # Validate that the dates are not in the future
        assert start_date.date() <= current_date
        assert end_date.date() <= current_date + timedelta(days=1)  # Allow today to be included
        
    print("\nAll tests passed - no future dates were used")

if __name__ == "__main__":
    test_weekday_ranges()