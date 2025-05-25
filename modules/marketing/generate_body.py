# this is responsible generates description for 
# discord and caption for
#  instagram
# [ instagram : {}, discord :{} ]
#  using claude

import os
import json
from datetime import datetime
import anthropic

def format_event_date(date_str):
    """Format date string to a more readable format"""
    try:
        date_obj = datetime.fromisoformat(date_str.replace('Z', '+00:00'))
        return date_obj.strftime("%A, %B %d, %Y at %I:%M %p")
    except ValueError:
        return date_str  # Return original if parsing fails

def generate_content(event, api_key=None):
    """
    Generate platform-specific descriptions for an event using Claude
    
    Args:
        event (dict): Event data containing name, date, location, info
        api_key (str): Claude API key (defaults to environment variable)
        
    Returns:
        dict: Contains generated content for different platforms
    """
    if not api_key:
        api_key = os.environ.get("ANTHROPIC_API_KEY")
    
    
    client = anthropic.Anthropic(api_key=api_key)
    
    # Format event data for better prompt
    formatted_date = format_event_date(event["date"])
    
    prompt = f"""
    Generate social media content for a Software Developers Association (SoDA) event:

    Event Name: {event['name']}
    Date: {formatted_date}
    Location: {event['location']}
    Description: {event['info']}

    Create the following content:
    1. Instagram caption (limited to 280 characters, including relevant hashtags like #ASUSoDA #ASU #Programming)
    2. Discord announcement (longer form, more detailed with formatting, addressing members directly)
    
    Format your response as JSON with fields "instagram" and "discord".
    """

    try:
        response = client.messages.create(
            model="claude-3-7-sonnet-20240620",
            max_tokens=1000,
            temperature=0.4,
            messages=[
                {
                    "role": "user",
                    "content": prompt
                }
            ]
        )
        
        # Extract the JSON response
        content_text = response.content[0].text
        # Find JSON within the text (in case Claude adds explanatory text)
        start_idx = content_text.find('{')
        end_idx = content_text.rfind('}') + 1
        
        if start_idx >= 0 and end_idx > start_idx:
            json_str = content_text[start_idx:end_idx]
            try:
                content = json.loads(json_str)
                return content
            except json.JSONDecodeError:
                print("Error parsing JSON from Claude response")
        
        print("Couldn't extract valid JSON from Claude response")
        return generate_mock_content(event)
        
    except Exception as e:
        print(f"Error generating content with Claude: {str(e)}")
        return generate_mock_content(event)

def generate_mock_content(event):
    """Generate mock content for development without API access"""
    formatted_date = format_event_date(event["date"])
    
    return {
            "instagram": f"🚨 Join us for {event['name']} on {formatted_date} at {event['location']}! {event['info'][:100]}... #ASUSoDA #ASU #Programming #TechEvents",
            
            "discord": f"""
    # 📣 **{event['name']}**

    Hey SoDA members!

    Join us for an exciting event:

    📅 **Date:** {formatted_date}
    📍 **Location:** {event['location']}

    {event['info']}

    See you there! Don't forget to RSVP.
    """
    }

# if __name__ == "__main__":
#     # Test with a sample event
#     test_event = {
#         "name": "Amazon ML Specialist Guest Lecture",
#         "date": "2025-05-21T18:00:00",
#         "location": "PSH 150",
#         "info": "Learn about the latest in machine learning and AI technologies at Amazon"
#     }
    
#     content = generate_content(test_event)
#     print("=== Instagram ===")
#     print(content["instagram"])
#     print("\n=== Discord ===")
#     print(content["discord"])