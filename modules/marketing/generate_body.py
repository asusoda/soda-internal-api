# this is responsible generates description for 
# discord and caption for
#  instagram
# [ instagram : {}, discord :{} ]
#  using OpenRouter with Claude

import os
import json
from datetime import datetime
from openai import OpenAI

def format_event_date(date_str):
    """Format date string to a more readable format"""
    try:
        date_obj = datetime.fromisoformat(date_str.replace('Z', '+00:00'))
        return date_obj.strftime("%A, %B %d, %Y at %I:%M %p")
    except ValueError:
        return date_str  # Return original if parsing fails

def generate_content(event, api_key=None):
    """
    Generate a text paragraph description for an event using Claude via OpenRouter
    
    Args:
        event (dict): Event data containing name, date, location, info
        api_key (str): OpenRouter API key (defaults to environment variable)
        
    Returns:
        dict: Contains generated text paragraph for the event
    """    
    
    client = OpenAI(
        base_url="https://openrouter.ai/api/v1",
        api_key=api_key,
    )
    
    # Format event data for better prompt
    formatted_date = format_event_date(event["date"])
    
    prompt = f"""
    Generate a concise text paragraph describing this Software Developers Association (SoDA) event:

    Event Name: {event['name']}
    Date: {formatted_date}
    Location: {event['location']}
    Description: {event['info']}

    The paragraph should be informative, engaging, and highlight the key details and benefits of attending.
    Format your response as a simple text paragraph.
    """

    try:
        response = client.chat.completions.create(
            extra_headers={
                "HTTP-Referer": "https://soda.engineering.asu.edu",  # Replace with your site URL
                "X-Title": "ASU SoDA",  # Replace with your site name
            },
            model="anthropic/claude-3.7-sonnet",
            messages=[
                {
                    "role": "user",
                    "content": prompt
                }
            ],
            temperature=0.4,
            max_tokens=500
        )
        
        # Extract the text response
        content_text = response.choices[0].message.content.strip()
        
        return {
            "text": content_text
        }
        
    except Exception as e:
        print(f"Error generating content with OpenRouter: {str(e)}")
        return e
        # return generate_mock_content(event)

# def generate_mock_content(event):
#     """Generate mock content for development without API access"""
#     formatted_date = format_event_date(event["date"])
    
#     return {
#             "instagram": f"🚨 Join us for {event['name']} on {formatted_date} at {event['location']}! {event['info'][:100]}... #ASUSoDA #ASU #Programming #TechEvents",
            
#             "discord": f"""
#     # 📣 **{event['name']}**

#     Hey SoDA members!

#     Join us for an exciting event:

#     📅 **Date:** {formatted_date}
#     📍 **Location:** {event['location']}
 
#     {event['info']}

#     See you there! Don't forget to RSVP.
#     """
#     }

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