#!/usr/bin/env python3
"""
Test script for month range parsing in SummarizerService.
This script tests parsing of expressions like "January to February".
"""

import sys
import os
import re
from datetime import datetime, timezone, timedelta

# Add the project root to the Python path to import modules properly
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from modules.summarizer.service import SummarizerService


def test_month_range():
    """Test month range parsing with various expressions."""
    service = SummarizerService()
    
    # Test various month range combinations
    test_ranges = [
        "january to february",
        "january through february",
        "march to may",
        "november to january",  # Cross-year range
        "october to september",  # Across multiple months
        "july to july",  # Same month
        "last january to last february",
        "from last november to last january"
    ]
    
    print(f"Reference date: {datetime.now()}")
    print("-" * 50)
    
    for range_text in test_ranges:
        try:
            print(f"\nTesting: '{range_text}'")
            
            # For more detailed info, first extract the timeframe
            timeframe = service.extract_timeframe_from_text(range_text)
            print(f"Extracted timeframe: '{timeframe}'")
            
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
            
            # Parse the month names from the input - use regex for more accurate parsing
            month_pattern = r'(?:last\s+)?(january|february|march|april|may|june|july|august|september|october|november|december)\s+(?:to|through|until|and)\s+(?:last\s+)?(january|february|march|april|may|june|july|august|september|october|november|december)'
            match = re.search(month_pattern, range_text.lower())
            
            if match:
                start_month, end_month = match.groups()
                print(f"Expected months: {start_month.capitalize()} to {end_month.capitalize()}")
                print(f"Actual months:   {start.strftime('%B')} to {end.strftime('%B')}")
                print(f"With years:      {start.strftime('%B %Y')} to {end.strftime('%B %Y')}")
            else:
                print(f"Could not extract month names from: {range_text}")
                print(f"Actual months:   {start.strftime('%B')} to {end.strftime('%B')}")
            
        except Exception as e:
            print(f"Error parsing '{range_text}': {e}")
    
    # Test with more complex queries
    print("\n" + "-" * 50 + "\n")
    
    # List of test queries
    test_queries = [
        "What happened from January to February?",
        "Summarize what people talked about last January through last February",
        "What discussions took place from March to May?",
        "What happened from November to January?",
        "What did people talk about from July to August?",
    ]
    
    for query in test_queries:
        try:
            print(f"\nQuery: '{query}'")
            
            # First, extract the timeframe from the query
            timeframe = service.extract_timeframe_from_text(query)
            print(f"Extracted timeframe: '{timeframe}'")
            
            if timeframe:
                # Then, parse the extracted timeframe into a date range
                start, end, display = service.parse_date_range(timeframe)
                print(f"Parsed date range: {start} to {end}")
                print(f"Display format:    {display}")
                
                # Show the range in months
                if end and start:
                    days_diff = (end.date() - start.date()).days + 1  # +1 because end date is inclusive
                    print(f"Spans {days_diff} days")
                    print(f"From {start.strftime('%B %Y')} to {end.strftime('%B %Y')}")
            else:
                print("No timeframe extracted - would use default")
                
        except Exception as e:
            print(f"Error processing query: {e}")
    
    print("\n" + "-" * 50)


if __name__ == "__main__":
    test_month_range()