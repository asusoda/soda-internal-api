#!/usr/bin/env python3
"""
Test script for the AVERY Summarizer module
This script tests the Gemini API integration and basic summarization functionality
without requiring a Discord connection.
"""

import os
import sys
import json
from datetime import datetime, timedelta, timezone
from dotenv import load_dotenv
from modules.summarizer.service import SummarizerService
from modules.utils.config import Config as AppConfig

# Load environment variables
load_dotenv()

def test_gemini_connection():
    """Test basic connection to the Gemini API"""
    print("=== Testing Gemini API Connection ===")
    service = SummarizerService()

    if not service.gemini_client:
        print("❌ Gemini client initialization failed. Check your API key.")
        print(f"GEMINI_API_KEY in environment: {'Yes' if os.environ.get('GEMINI_API_KEY') else 'No'}")
        print(f"GEMINI_API_KEY in config: {'Yes' if AppConfig().GEMINI_API_KEY else 'No'}")
        assert False, "Gemini client initialization failed"
    
    try:
        response = service.test_gemini_connection("Hello, Gemini! This is a test from AVERY summarizer.")
        print(f"✅ Successfully connected to Gemini API")
        print(f"Response: {response}")
        assert response is not None, "Gemini connection test failed with no response"
    except Exception as e:
        print(f"❌ Error testing Gemini connection: {e}")
        assert False, f"Error testing Gemini connection: {e}"

def test_summarization():
    """Test the summarization functionality with sample messages"""
    print("\n=== Testing Summarization Functionality ===")
    service = SummarizerService()
    
    # Create sample messages (simulating Discord messages)
    sample_messages = [
        {
            "id": "123456789",
            "content": "Hey everyone, I'm thinking we should update our website design. It's been a while since we refreshed it.",
            "author": {"id": "111", "name": "Alice"},
            "timestamp": (datetime.now(timezone.utc) - timedelta(hours=3)).strftime("%Y-%m-%d %H:%M:%S"),
            "jump_url": "https://discord.com/channels/123/456/789"
        },
        {
            "id": "123456790",
            "content": "That's a good idea. What specifically are you thinking we should change?",
            "author": {"id": "222", "name": "Bob"},
            "timestamp": (datetime.now(timezone.utc) - timedelta(hours=2, minutes=50)).strftime("%Y-%m-%d %H:%M:%S"),
            "jump_url": "https://discord.com/channels/123/456/790"
        },
        {
            "id": "123456791",
            "content": "I think we need to update the color scheme and make it more mobile-friendly. Our analytics show that 60% of visitors are on mobile now.",
            "author": {"id": "111", "name": "Alice"},
            "timestamp": (datetime.now(timezone.utc) - timedelta(hours=2, minutes=45)).strftime("%Y-%m-%d %H:%M:%S"),
            "jump_url": "https://discord.com/channels/123/456/791"
        },
        {
            "id": "123456792",
            "content": "I agree with the mobile-first approach. We should also consider updating our logo while we're at it.",
            "author": {"id": "333", "name": "Charlie"},
            "timestamp": (datetime.now(timezone.utc) - timedelta(hours=2, minutes=30)).strftime("%Y-%m-%d %H:%M:%S"),
            "jump_url": "https://discord.com/channels/123/456/792"
        },
        {
            "id": "123456793",
            "content": "Let's create a task force to work on this. Who wants to be involved?",
            "author": {"id": "111", "name": "Alice"},
            "timestamp": (datetime.now(timezone.utc) - timedelta(hours=2)).strftime("%Y-%m-%d %H:%M:%S"),
            "jump_url": "https://discord.com/channels/123/456/793"
        },
        {
            "id": "123456794",
            "content": "I can help with the design. I've been learning Figma recently.",
            "author": {"id": "444", "name": "Dave"},
            "timestamp": (datetime.now(timezone.utc) - timedelta(hours=1, minutes=45)).strftime("%Y-%m-%d %H:%M:%S"),
            "jump_url": "https://discord.com/channels/123/456/794"
        },
        {
            "id": "123456795",
            "content": "Great! Let's meet next Tuesday to discuss initial ideas. Everyone please come prepared with some examples of websites you like.",
            "author": {"id": "111", "name": "Alice"},
            "timestamp": (datetime.now(timezone.utc) - timedelta(hours=1, minutes=30)).strftime("%Y-%m-%d %H:%M:%S"),
            "jump_url": "https://discord.com/channels/123/456/795"
        }
    ]
    
    try:
        # Generate a summary
        summary_result = service.generate_summary(
            messages=sample_messages,
            duration_str="3h",
            user_id="test_user",
            channel_id="test_channel",
            guild_id="test_guild"
        )
        
        print(f"✅ Successfully generated summary")
        print("\nSUMMARY:")
        print("=" * 50)
        print(summary_result["summary"])
        print("=" * 50)
        print(f"Message count: {summary_result['message_count']}")
        print(f"Duration: {summary_result['duration']}")
        print(f"Completion time: {summary_result.get('completion_time', 'N/A')} seconds")
        
        # Assert that summary was generated successfully
        assert summary_result is not None
        assert "summary" in summary_result
        assert summary_result["summary"] != ""
    except Exception as e:
        print(f"❌ Error testing summarization: {e}")
        assert False, f"Error testing summarization: {e}"

def test_empty_messages():
    """Test summarization with no messages"""
    print("\n=== Testing Summarization with No Messages ===")
    service = SummarizerService()
    
    try:
        # Generate a summary with empty messages
        summary_result = service.generate_summary(
            messages=[],
            duration_str="24h",
            user_id="test_user",
            channel_id="test_channel",
            guild_id="test_guild"
        )
        
        print(f"✅ Successfully handled empty messages case")
        print("\nRESPONSE:")
        print("=" * 50)
        print(summary_result["summary"])
        print("=" * 50)
        
        # Assert that empty message case was handled
        assert summary_result is not None
        assert "summary" in summary_result
    except Exception as e:
        print(f"❌ Error testing empty messages: {e}")
        assert False, f"Error testing empty messages: {e}"

def test_duration_parsing():
    """Test parsing of duration strings"""
    print("\n=== Testing Duration Parsing ===")
    service = SummarizerService()
    
    test_cases = {
        "1h": timedelta(hours=1),
        "24h": timedelta(hours=24),
        "1d": timedelta(days=1),
        "3d": timedelta(days=3),
        "7d": timedelta(days=7),
        "1w": timedelta(weeks=1),
        "invalid": timedelta(hours=24),  # Should default to 24h
        None: timedelta(hours=24),  # Should default to 24h
    }
    
    for input_str, expected in test_cases.items():
        result = service.parse_duration(input_str)
        if result == expected:
            print(f"✅ Successfully parsed '{input_str}' to {result}")
        else:
            print(f"❌ Failed to parse '{input_str}'. Got {result}, expected {expected}")
        assert result == expected, f"Failed to parse '{input_str}'. Got {result}, expected {expected}"

def run_all_tests():
    """Run all test functions"""
    tests = [
        test_gemini_connection,
        test_duration_parsing,
        test_summarization,
        test_empty_messages
    ]
    
    results = []
    for test in tests:
        results.append(test())
    
    print("\n=== Test Summary ===")
    print(f"Passed: {results.count(True)}/{len(results)}")
    print(f"Failed: {results.count(False)}/{len(results)}")
    
    return all(results)

if __name__ == "__main__":
    print("AVERY Summarizer Module Test")
    print("=" * 50)
    success = run_all_tests()
    sys.exit(0 if success else 1)