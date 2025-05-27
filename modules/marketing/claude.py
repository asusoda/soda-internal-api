# This file consolidates all Claude API interactions for content and code generation

import re
import json
from datetime import datetime
from openai import OpenAI
from shared import logger

def format_event_date(date_str):
    """Format date string to a more readable format"""
    try:
        date_obj = datetime.fromisoformat(date_str.replace('Z', '+00:00'))
        return date_obj.strftime("%A, %B %d, %Y at %I:%M %p")
    except ValueError:
        return date_str  # Return original if parsing fails

def get_claude_client(api_key=None):
    """
    Create and return an OpenAI client configured to use Claude via OpenRouter
    
    Args:
        api_key (str): OpenRouter API key
        
    Returns:
        OpenAI: Configured client instance
    """
    return OpenAI(
        base_url="https://openrouter.ai/api/v1",
        api_key=api_key,
    )

# -- Content Generation Functions (from generate_body.py) --

def generate_content(event, api_key=None):
    """
    Generate a text paragraph description for an event using Claude via OpenRouter
    
    Args:
        event (dict): Event data containing name, date, location, info
        api_key (str): OpenRouter API key (defaults to environment variable)
        
    Returns:
        dict: Contains generated text paragraph for the event
    """    
    
    client = get_claude_client(api_key)
    
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
                "HTTP-Referer": "https://soda.engineering.asu.edu", 
                "X-Title": "ASU SoDA",
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
        logger.info(f"Error generating content with OpenRouter: {str(e)}")
        return {
            "text": f"Join us for {event['name']} on {formatted_date} at {event['location']}! {event.get('info', '')[:150]}... #ASUSoDA #SoftwareDevelopment"
        }

# -- Code Generation Functions (from generate_code.py) --

def generate_grapes_code(event, template, content=None, api_key=None):
    """
    Generate GrapesJS compatible HTML/CSS code for the event using Claude via OpenRouter
    
    Args: 
        event (dict): Event data containing name, date, etc.
        template (dict): Base HTML/CSS templates to use
        content (dict): Platform specific content (if already generated)
        api_key (str): OpenRouter API key
        
    Returns:
        dict: HTML and CSS for GrapesJS
    """
    
    client = get_claude_client(api_key)
    
    # Format the event date nicely
    try:
        date_obj = datetime.fromisoformat(event['date'].replace('Z', '+00:00'))
        formatted_date = date_obj.strftime("%A, %B %d, %Y at %I:%M %p")
    except (ValueError, KeyError):
        formatted_date = event.get('date', 'TBD')
    
    # Extract event name components for title/highlight
    name_parts = event['name'].split(' ')
    if len(name_parts) >= 4:
        # If name is long, split it for visual interest
        highlight_part = ' '.join(name_parts[-2:])
        title_part = ' '.join(name_parts[:-2])
    else:
        # If name is short, highlight last word
        highlight_part = name_parts[-1] if name_parts else ""
        title_part = ' '.join(name_parts[:-1]) if len(name_parts) > 1 else event['name']
    
    prompt = f"""
    You are an expert HTML/CSS developer. I need you to generate code for a SoDA (Software Developers Association) event banner.

    Here's the event information:
    - Event name: {event['name']} 
    - Date: {formatted_date}
    - Location: {event['location']}
    - Description: {event['info']}

    Here's a base HTML template:
    ```html
    {template['html']}
    ```

    And the CSS:
    ```css
    {template['css']}
    ```

    Please generate the final HTML and CSS with the following requirements:
    1. Replace the placeholders ({{EVENT_TITLE}}, {{EVENT_HIGHLIGHT}}, etc.) with actual event information
    2. The title part should be "{title_part}" and the highlight part should be "{highlight_part}"
    3. Ensure the code is clean and properly formatted for GrapesJS
    4. Keep the SoDA branding elements intact

    Format your response as JSON with fields "html" and "css".
    """

    try:
        response = client.chat.completions.create(
            extra_headers={
                "HTTP-Referer": "https://soda.engineering.asu.edu",
                "X-Title": "SoDA Internal API",
            },
            model="anthropic/claude-3.7-sonnet",
            messages=[
                {
                    "role": "user",
                    "content": prompt
                }
            ]
        )
        
        # Extract the response content
        content_text = response.choices[0].message.content
        
        # Parse out HTML and CSS from Claude's response
        html_match = re.search(r'```html\s*(.*?)\s*```', content_text, re.DOTALL)
        css_match = re.search(r'```css\s*(.*?)\s*```', content_text, re.DOTALL)
        
        html_code = html_match.group(1) if html_match else None
        css_code = css_match.group(1) if css_match else None
        
        if html_code and css_code:
            return {"html": html_code, "css": css_code}
        
        # If RegEx didn't work, try to extract JSON
        json_match = re.search(r'\{[\s\S]*"html"[\s\S]*"css"[\s\S]*\}', content_text)
        if json_match:
            try:
                result = json.loads(json_match.group(0))
                if "html" in result and "css" in result:
                    return result
            except json.JSONDecodeError:
                pass
        
        # Fallback to manual template filling
        logger.info("Couldn't extract HTML/CSS from Claude response, falling back to manual template")
        return fill_template_manually(event, template, content)
        
    except Exception as e:
        logger.info(f"Error generating code with Claude via OpenRouter: {str(e)}")
        return fill_template_manually(event, template, content)

def fill_template_manually(event, template, content=None):
    """
    Fill template placeholders manually if Claude API is unavailable
    
    Args:
        event (dict): Event information
        template (dict): HTML/CSS templates
        content (dict): Optional content for Discord/Instagram
        
    Returns:
        dict: Filled HTML and CSS
    """
    html = template['html']
    css = template['css']
    
    # Format the event date nicely
    try:
        date_obj = datetime.fromisoformat(event['date'].replace('Z', '+00:00'))
        formatted_date = date_obj.strftime("%A, %B %d, %Y at %I:%M %p")
    except (ValueError, KeyError):
        formatted_date = event.get('date', 'TBD')
    
    # Extract event name components for title/highlight
    name_parts = event['name'].split(' ')
    if len(name_parts) >= 4:
        # If name is long, split it for visual interest
        highlight_part = ' '.join(name_parts[-2:])
        title_part = ' '.join(name_parts[:-2])
    else:
        # If name is short, highlight last word
        highlight_part = name_parts[-1] if name_parts else ""
        title_part = ' '.join(name_parts[:-1]) if len(name_parts) > 1 else event['name']
    
    # Replace placeholders
    html = html.replace("{{EVENT_TITLE}}", title_part)
    html = html.replace("{{EVENT_HIGHLIGHT}}", highlight_part)
    html = html.replace("{{EVENT_DATE}}", formatted_date)
    html = html.replace("{{EVENT_LOCATION}}", event.get('location', 'TBD'))
    html = html.replace("{{EVENT_DESCRIPTION}}", event.get('info', ''))
    
    return {"html": html, "css": css}