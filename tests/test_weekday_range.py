#!/usr/bin/env python3
"""
Test script for weekday range parsing in SummarizerService.
This script tests parsing of expressions like "Monday to Friday".
"""

import sys
import os
import re
from datetime import datetime, timezone, timedelta

# Add the project root to the Python path to import modules properly
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from modules.summarizer.service import SummarizerService


def test_weekday_range():
    """Test weekday range parsing with various expressions."""
    service = SummarizerService()
    
    # Test various weekday range combinations
    test_ranges = [
        "monday to friday",
        "monday through friday",
        "tuesday to thursday",
        "friday to monday",  # Cross-week range
        "sunday to saturday",  # Full week
        "wednesday to wednesday",  # Same day
    ]
    
    print(f"Reference date: {datetime.now()}")
    print("-" * 50)
    
    for range_text in test_ranges:
        try:
            print(f"\nTesting: '{range_text}'")
            start, end, display = service.parse_date_range(range_text)
            print(f"Start date: {start}")
            print(f"End date:   {end}")
            print(f"Display:    {display}")
            
            # Check if the parsed dates have correct timezone
            print(f"Start timezone: {start.tzinfo}")
            print(f"End timezone:   {end.tzinfo}")
            
            # Calculate the range in days
            days_diff = (end.date() - start.date()).days + 1  # +1 because end date is inclusive
            print(f"Range spans {days_diff} days")
            
            # Parse the weekday names from the input - use regex for more accurate parsing
            weekday_pattern = r'(monday|tuesday|wednesday|thursday|friday|saturday|sunday)\s+(?:to|through|until|and)\s+(monday|tuesday|wednesday|thursday|friday|saturday|sunday)'
            match = re.search(weekday_pattern, range_text.lower())
            
            if match:
                start_day, end_day = match.groups()
                print(f"Expected weekdays: {start_day.capitalize()} to {end_day.capitalize()}")
                print(f"Actual weekdays:   {start.strftime('%A')} to {end.strftime('%A')}")
            else:
                print(f"Could not extract weekday names from: {range_text}")
                print(f"Actual weekdays:   {start.strftime('%A')} to {end.strftime('%A')}")
            
        except Exception as e:
            print(f"Error parsing '{range_text}': {e}")
    
    print("\n" + "-" * 50 + "\n")
    
    # Test with more complex expressions
    complex_ranges = [
        "from monday to friday",
        "last monday to friday",
        "from last monday to friday"
    ]
    
    for range_text in complex_ranges:
        try:
            print(f"\nTesting complex expression: '{range_text}'")
            start, end, display = service.parse_date_range(range_text)
            print(f"Start date: {start}")
            print(f"End date:   {end}")
            print(f"Display:    {display}")
        except Exception as e:
            print(f"Error parsing '{range_text}': {e}")


if __name__ == "__main__":
    test_weekday_range()