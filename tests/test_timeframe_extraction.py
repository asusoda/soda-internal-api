#!/usr/bin/env python3
"""
Test script for timeframe extraction and date range parsing in SummarizerService.
This script tests the full pipeline from user query to date range.
"""

import sys
import os
from datetime import datetime, timezone, timedelta

# Add the project root to the Python path to import modules properly
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from modules.summarizer.service import SummarizerService


def test_query_parsing():
    """Test full date extraction and parsing pipeline with various queries."""
    service = SummarizerService()
    
    # List of test queries
    test_queries = [
        "What happened from Monday to Friday?",
        "Summarize what people talked about Monday through Friday",
        "What discussions took place last Monday to Friday?",
        "What happened from Friday to Monday?",
        "What did people talk about last January to last February?",
        "What happened Tuesday to Thursday?",
        "What happened on Monday?",
        "What happened in the last 24 hours?",
        "What was discussed yesterday?",
        "What happened Sunday to Saturday?"
    ]
    
    print(f"Reference date: {datetime.now()}")
    print("-" * 50)
    
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
                
                # Show the range in days
                if end and start:
                    days_diff = (end.date() - start.date()).days + 1  # +1 because end date is inclusive
                    print(f"Spans {days_diff} days")
            else:
                print("No timeframe extracted - would use default")
                
        except Exception as e:
            print(f"Error processing query: {e}")
    
    print("\n" + "-" * 50)


if __name__ == "__main__":
    test_query_parsing()