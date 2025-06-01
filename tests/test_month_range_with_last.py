from modules.summarizer.service import SummarizerService
from datetime import datetime, timezone, timedelta
import unittest

class TestMonthRangeWithLast(unittest.TestCase):
    """Test parsing month ranges with 'last' modifier."""
    
    def test_last_month_to_month(self):
        """Test parsing 'last [month] to [month]' expressions."""
        service = SummarizerService()
        reference_date = datetime(2025, 5, 18, tzinfo=timezone.utc)  # May 18, 2025
        
        # Test case from the error log
        query = "last january to march"
        timeframe = service.extract_timeframe_from_text(query)
        self.assertIsNotNone(timeframe, "Should extract a timeframe")
        print(f"Extracted timeframe: {timeframe}")
        
        start_date, end_date, display = service.parse_date_range(timeframe, reference_date)
        
        # Verify that we got a range from January to March
        self.assertEqual(start_date.month, 1, "Start month should be January")
        self.assertEqual(end_date.month, 3, "End month should be March")
        
        # For January-March range, both should be in the same year
        # (since January comes before March in the calendar)
        self.assertEqual(start_date.year, end_date.year, 
                         "For same-calendar-direction ranges, months should be in same year")
        
        # Verify that the year is the CURRENT year, not previous year
        # This is because in May 2025, "last january to march" refers to Jan-Mar 2025
        # since those months have already passed in the current year
        self.assertEqual(start_date.year, reference_date.year, 
                         "Year should be current year when months have already passed")
        
        # Check that the display string correctly indicates the range
        self.assertIn("January", display, "Display should mention January")
        self.assertIn("March", display, "Display should mention March")
        self.assertIn(str(reference_date.year), display, "Display should show current year")
        
        print(f"Start date: {start_date}")
        print(f"End date: {end_date}")
        print(f"Display: {display}")
        
        # Also test with a reference date before the months in question
        # For example, if it's February 2025, "last january" should refer to January 2024
        early_reference_date = datetime(2025, 2, 15, tzinfo=timezone.utc)  # February 15, 2025
        early_start_date, early_end_date, early_display = service.parse_date_range(timeframe, early_reference_date)
        
        # Since we're in February and asking about January-March, this should use previous year
        self.assertEqual(early_start_date.year, early_reference_date.year - 1, 
                        "When current date is in the range, 'last' should refer to previous year")
        print(f"Early reference date: {early_reference_date}")
        print(f"Early start date: {early_start_date}")
        print(f"Early end date: {early_end_date}")
        print(f"Early display: {early_display}")

    def test_last_december_to_february(self):
        """Test cross-year ranges like 'last December to February'."""
        service = SummarizerService()
        reference_date = datetime(2025, 5, 18, tzinfo=timezone.utc)  # May 18, 2025
        
        query = "last december to february"
        timeframe = service.extract_timeframe_from_text(query)
        self.assertIsNotNone(timeframe, "Should extract a timeframe")
        print(f"Extracted timeframe: {timeframe}")
        
        start_date, end_date, display = service.parse_date_range(timeframe, reference_date)
        
        # December should be month 12
        self.assertEqual(start_date.month, 12, "Start month should be December")
        # February should be month 2
        self.assertEqual(end_date.month, 2, "End month should be February")
        
        # In May 2025, "last december to february" should refer to Dec 2024 - Feb 2025
        # The end month is in the current year if it has already passed, but start month is previous year
        self.assertEqual(start_date.year, reference_date.year - 1, 
                         "For cross-year ranges with 'last', start month should be in previous year")
        self.assertEqual(end_date.year, reference_date.year, 
                         "For cross-year ranges with 'last', end month should be in current year when it has passed")
        
        # Also verify year boundary crossing
        self.assertEqual(start_date.year + 1, end_date.year, 
                         "For Dec-Feb ranges, Feb should be in the year after Dec")
        
        print(f"Start date: {start_date}")
        print(f"End date: {end_date}")
        print(f"Display: {display}")
        
        # Also test with March reference date (where February is recent)
        march_reference_date = datetime(2025, 3, 15, tzinfo=timezone.utc)  # March 15, 2025
        march_start_date, march_end_date, march_display = service.parse_date_range(timeframe, march_reference_date)
        
        # In March, "last december to february" should also use Dec 2024 - Feb 2025
        self.assertEqual(march_start_date.year, march_reference_date.year - 1, 
                         "December should be in previous year") 
        self.assertEqual(march_end_date.year, march_reference_date.year, 
                         "February should be in current year when reference is March")
        
        print(f"March reference date: {march_reference_date}")
        print(f"March start date: {march_start_date}")
        print(f"March end date: {march_end_date}")
        print(f"March display: {march_display}")

if __name__ == "__main__":
    unittest.main()