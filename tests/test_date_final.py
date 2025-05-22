from modules.summarizer.service import SummarizerService
from datetime import datetime, timezone, timedelta

def test_date_parsing():
    """Test the final date parsing implementation with key cases."""
    service = SummarizerService()
    now = datetime.now(timezone.utc)
    
    test_cases = [
        ("what happened wednesday to friday", 
         "Previous Wednesday to Friday"),
        ("what happened last wednesday to friday", 
         "Last Wednesday to Friday"),
        ("monday to friday", 
         "Previous Monday to Friday"),
        ("friday to monday", 
         "Previous Friday to Monday")
    ]
    
    print(f"\nToday is {now.date()}")
    
    for query, expected_prefix in test_cases:
        print(f"\nTesting: '{query}'")
        timeframe = service.extract_timeframe_from_text(query)
        print(f"Extracted timeframe: {timeframe}")
        
        start_date, end_date, display = service.parse_date_range(timeframe)
        print(f"Start date: {start_date}")
        print(f"End date: {end_date}")
        print(f"Display: {display}")
        
        # Verify the expected prefix and that dates are in the past
        assert expected_prefix in display, f"Expected '{expected_prefix}' in display, got '{display}'"
        assert start_date.date() <= now.date(), f"Expected date in past, got {start_date}"
        assert end_date.date() <= now.date() + timedelta(days=1), f"Expected date not in future, got {end_date}"
        
    print("\nAll tests passed - date parsing is working correctly")

if __name__ == "__main__":
    test_date_parsing()