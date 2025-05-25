#  considers template and
# description to generate
# actual code for 
# grapeJS using claude
# <code>

import os
import anthropic
import re
from datetime import datetime

def generate_grapes_code(event, template, content=None, api_key=None):
    """
    Generate GrapesJS compatible HTML/CSS code for the event using Claude
    
    Args:
        event (dict): Event data containing name, date, etc.
        template (dict): Base HTML/CSS templates to use
        content (dict): Platform specific content (if already generated)
        api_key (str): Claude API key
        
    Returns:
        dict: HTML and CSS for GrapesJS
    """
    if not api_key:
        api_key = os.environ.get("ANTHROPIC_API_KEY")
    
    
    client = anthropic.Anthropic(api_key=api_key)
    
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
        response = client.messages.create(
            model="claude-3-7-sonnet-20240620",
            max_tokens=2000,
            temperature=0.2,
            messages=[
                {
                    "role": "user",
                    "content": prompt
                }
            ]
        )
        
        # Extract the JSON response
        content_text = response.content[0].text
        
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
                import json
                result = json.loads(json_match.group(0))
                if "html" in result and "css" in result:
                    return result
            except json.JSONDecodeError:
                pass
        
        # Fallback to manual template filling
        print("Couldn't extract HTML/CSS from Claude response, falling back to manual template")
        return fill_template_manually(event, template, content)
        
    except Exception as e:
        print(f"Error generating code with Claude: {str(e)}")
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

# if __name__ == "__main__":
#     # Test with a sample event
#     from get_template import get_discord_template
    
#     test_event = {
#         "name": "Amazon ML Specialist Guest Lecture",
#         "date": "2025-05-21T18:00:00",
#         "location": "PSH 150",
#         "info": "Learn about the latest in machine learning and AI technologies at Amazon"
#     }
    
#     template = get_discord_template()
#     result = generate_grapes_code(test_event, template)
    
#     print("=== HTML ===")
#     print(result["html"])
#     print("\n=== CSS ===")
#     print(result["css"])