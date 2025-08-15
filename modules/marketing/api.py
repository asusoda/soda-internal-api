from flask import render_template, request, jsonify, Blueprint, current_app
import os
import threading
import time
import json
from datetime import datetime
import requests

# Import our modules
from modules.marketing.events import get_upcoming_events
from modules.marketing.template import get_discord_template, get_editor_html_css, get_view_html_css
from modules.marketing.claude import generate_content, generate_grapes_code
from modules.marketing.editable_link import get_server_url
from modules.marketing.message import send_officer_notification
from shared import logger, config
from modules.marketing.selenium import post_to_social_media

# ==================================================================================================

# Create a Flask Blueprint for the marketing module
marketing_blueprint = Blueprint('marketing', __name__, template_folder='templates', static_folder='static')

# Global array to store multiple events and their generated content, will be populated by the event monitoring process
managed_events = []

# Track which event is currently being edited (for the main editor route)
current_event_id = None

# Store completed events (those with saved images)
completed_events = {}

# Store the current editor content
editor_content = {
    'html': '<div class="default">Default content - will be replaced by LLM content</div>',
    'css': '.default{padding:15px;background-color:#f0f0f0;text-align:center;}'
}

# Helper function to get marketing service
def get_marketing_service():
    """Get the marketing service from the Flask app context"""
    return current_app.marketing_service

# Global configuration
marketing_config = {
    'api_url': config.TNAY_API_URL,
    'open_router_claude_api_key': config.OPEN_ROUTER_CLAUDE_API_KEY,
    'officer_webhook_url': config.DISCORD_OFFICER_WEBHOOK_URL,
    'oneup_email': config.ONEUP_EMAIL,
    'oneup_pass': config.ONEUP_PASSWORD,
    'post_webhook_url': config.DISCORD_POST_WEBHOOK_URL,
    'check_interval': 3600,  # 1 hour by default
    'monitoring_active': False
}

# ==================================================================================================

# BEGIN ENDPOINTS

@marketing_blueprint.route('/view/<event_id>')
def view_event(event_id):
    """Render the view-only page showing a specific event design"""
    # Find the event in our database using the service
    marketing_service = get_marketing_service()
    event = marketing_service.get_event_by_id(event_id)
    
    if not event:
        return "Event not found", 404
        
    # Set the editor content to this event's content
    global editor_content
    editor_content = event['grapes_code']
    
    return render_template('view.html')

@marketing_blueprint.route('/load-content')
def load_content():
    """API endpoint to load the current editor content"""
    # Check if we have a current event being edited
    if current_event_id:
        # Find the event in our database using the service
        marketing_service = get_marketing_service()
        event = marketing_service.get_event_by_id(current_event_id)
        if event:
            return jsonify(event['grapes_code'])
    
    # Default to global editor_content if no event is being edited
    return jsonify(editor_content)

@marketing_blueprint.route('/update-content', methods=['POST'])
def update_content():
    """API endpoint to update editor content (from LLM or editor)"""
    global editor_content
    data = request.json
    editor_content = {
        'html': data.get('html', ''),
        'css': data.get('css', '')
    }
    
    # If editing a specific event, save it to the database using the service
    if current_event_id:
        marketing_service = get_marketing_service()
        event = marketing_service.get_event_by_id(current_event_id)
        if event:
            # Update the event with new grapes_code
            update_data = {
                'event_id': current_event_id,
                'grapes_code': editor_content
            }
            marketing_service.save_event(update_data)
    
    return jsonify({'status': 'success'})

@marketing_blueprint.route('/status', methods=['GET'])
def get_status():
    """Get monitoring status"""
    return jsonify({
        "monitoring_active": marketing_config['monitoring_active'],
        "check_interval": marketing_config['check_interval'],
        "api_url_configured": bool(marketing_config['api_url']),
        "officer_webhook_configured": bool(marketing_config['officer_webhook_url']),
        "post_webhook_configured": bool(marketing_config['post_webhook_url']),
        "api_key_configured": bool(marketing_config['open_router_claude_api_key'])
    })

@marketing_blueprint.route('/toggle-monitoring', methods=['POST'])
def toggle_monitoring():
    """Toggle event monitoring on/off"""
    marketing_config['monitoring_active'] = not marketing_config['monitoring_active']
    return jsonify({
        "status": "success", 
        "monitoring_active": marketing_config['monitoring_active']
    })

@marketing_blueprint.route('/')
def dashboard():
    """Admin dashboard showing all managed events"""
    # Get all events from database using the service
    marketing_service = get_marketing_service()
    managed_events = marketing_service.get_all_events()
    completed_events_dict = marketing_service.get_completed_events()
    
    # First, convert the events to safe HTML
    event_cards = []
    for event in managed_events:
        # Format the date nicely
        try:
            if event.get('date'):
                if isinstance(event['date'], str):
                    date_obj = datetime.fromisoformat(event['date'].replace('Z', '+00:00'))
                else:
                    date_obj = event['date']
                formatted_date = date_obj.strftime("%A, %B %d, %Y at %I:%M %p")
            else:
                formatted_date = "No date specified"
        except Exception:
            formatted_date = str(event.get('date', 'No date'))
            
        # Create HTML for the event card
        completed = event.get('is_completed', False) or event.get('status') == 'completed'
        checked_attr = 'checked' if completed else ''
        disabled_attr = 'disabled' if completed else ''
        
        event_card = f'''
        <div class="event-card {event.get('status', 'pending')}">
            <div class="event-header">
                <h3>{event.get('name', 'Unnamed Event')}</h3>
                <div class="event-status">
                    <input type="checkbox" {checked_attr} {disabled_attr}/>
                    <span>{event.get('status', 'pending').capitalize()}</span>
                </div>
            </div>
            <div class="event-details">
                <p><strong>Date:</strong> {formatted_date}</p>
                <p><strong>Location:</strong> {event.get('location', 'TBD')}</p>
                <div class="event-actions">
                    <a href="/marketing/events/{event.get('event_id', event.get('id'))}" class="btn btn-edit" target="_blank">Edit</a>
                    <a href="/marketing/view/{event.get('event_id', event.get('id'))}" class="btn btn-view" target="_blank">View</a>
                </div>
            </div>
        </div>
        '''
        event_cards.append(event_card)
    
    # Join all event cards
    events_html = "\\n".join(event_cards) if event_cards else '<p>No events found. Use "Process Events Now" to check for new events.</p>'
    
    return f'''
    <!DOCTYPE html>
    <html>
    <head>
        <title>SoDA Marketing Bot Dashboard</title>
        <style>
            body {{ font-family: Arial, sans-serif; max-width: 1000px; margin: 0 auto; padding: 20px; }}
            .card {{ background: #f5f5f5; border-radius: 5px; padding: 15px; margin-bottom: 15px; }}
            button {{ background: #4CAF50; color: white; border: none; padding: 10px 15px; border-radius: 4px; cursor: pointer; }}
            button.stop {{ background: #f44336; }}
            .status {{ margin: 20px 0; }}
            .status-indicator {{ display: inline-block; width: 12px; height: 12px; border-radius: 50%; margin-right: 5px; }}
            .status-active {{ background: #4CAF50; }}
            .status-inactive {{ background: #f44336; }}
            
            /* Event cards styling */
            .events-container {{ 
                display: grid;
                grid-template-columns: repeat(auto-fill, minmax(300px, 1fr));
                gap: 15px;
                margin-top: 20px;
            }}
            .event-card {{ 
                background: white;
                border-radius: 5px;
                box-shadow: 0 2px 5px rgba(0,0,0,0.1);
                padding: 15px;
                border-left: 5px solid #9b59b6;
            }}
            .event-card.completed {{ 
                border-left: 5px solid #4CAF50;
                opacity: 0.8;
            }}
            .event-header {{ 
                display: flex;
                justify-content: space-between;
                align-items: center;
                margin-bottom: 10px;
            }}
            .event-header h3 {{
                margin: 0;
                font-size: 18px;
                color: #333;
            }}
            .event-status {{
                display: flex;
                align-items: center;
            }}
            .event-status span {{
                margin-left: 5px;
                font-size: 14px;
                color: #666;
            }}
            .event-actions {{
                display: flex;
                gap: 10px;
                margin-top: 10px;
            }}
            .btn {{
                padding: 8px 12px;
                border-radius: 4px;
                text-decoration: none;
                color: white;
                font-size: 14px;
            }}
            .btn-edit {{ background-color: #3498db; }}
            .btn-view {{ background-color: #9b59b6; }}
        </style>
    </head>
    <body>
        <h1>SoDA Marketing Bot Dashboard</h1>
        
        <div class="card">
            <h2>Monitoring Status</h2>
            <div class="status">
                <span id="status-indicator" class="status-indicator status-inactive"></span>
                <span id="status-text">Loading...</span>
            </div>
            <button id="toggle-btn">Start Monitoring</button>
        </div>
        
        <div class="card">
            <h2>Actions</h2>
            <button onclick="window.open('/marketing/', '_blank')">Open Editor</button>
            <button onclick="window.open('/marketing/view', '_blank')">View Banner</button>
            <button id="process-events-btn">Process Events Now</button>
        </div>
        
        <div class="card">
            <h2>Events</h2>
            <div class="events-container">
                {events_html}
            </div>
        </div>
        
        <script>
            // Load status
            function updateStatus() {{
                fetch('/marketing/status')
                    .then(response => response.json())
                    .then(data => {{
                        const statusIndicator = document.getElementById('status-indicator');
                        const statusText = document.getElementById('status-text');
                        const toggleBtn = document.getElementById('toggle-btn');
                        
                        if (data.monitoring_active) {{
                            statusIndicator.className = 'status-indicator status-active';
                            statusText.textContent = 'Monitoring is ACTIVE';
                            toggleBtn.textContent = 'Stop Monitoring';
                            toggleBtn.className = 'stop';
                        }} else {{
                            statusIndicator.className = 'status-indicator status-inactive';
                            statusText.textContent = 'Monitoring is INACTIVE';
                            toggleBtn.textContent = 'Start Monitoring';
                            toggleBtn.className = '';
                        }}
                    }});
            }}
            
            // Toggle monitoring
            document.getElementById('toggle-btn').addEventListener('click', () => {{
                fetch('/marketing/toggle-monitoring', {{ method: 'POST' }})
                    .then(response => response.json())
                    .then(data => {{
                        updateStatus();
                    }});
            }});
            
            // Process events now
            document.getElementById('process-events-btn').addEventListener('click', () => {{
                fetch('/marketing/process-events-now', {{ method: 'POST' }})
                    .then(response => response.json())
                    .then(data => {{
                        alert(data.message);
                        // Refresh the page to show new events
                        location.reload();
                    }});
            }});
            
            // Update status on load
            updateStatus();
        </script>
    </body>
    </html>
    '''
    
@marketing_blueprint.route('/events/<event_id>')
def event_editor(event_id):
    """Render the editor page for a specific event"""
    # Find the event in our database using the service
    marketing_service = get_marketing_service()
    event = marketing_service.get_event_by_id(event_id)
    
    if not event:
        return "Event not found", 404
    
    # Set this as the current event being edited
    global current_event_id
    current_event_id = event_id
    
    # Update the editor_content with this event's content
    global editor_content
    editor_content = event['grapes_code']
    
    # Render the editor template
    return render_template('editor.html', event=event)

@marketing_blueprint.route('/events/<event_id>/update-content', methods=['POST'])
def update_event_content(event_id):
    """API endpoint to update content for a specific event"""
    # Find the event in our database using the service
    marketing_service = get_marketing_service()
    event = marketing_service.get_event_by_id(event_id)
    
    if not event:
        return jsonify({"status": "error", "message": "Event not found"}), 404
    
    data = request.json
    html_content = data.get('html', '')
    css_content = data.get('css', '')
    
    # Update the event's grapes_code using the service
    update_data = {
        'event_id': event_id,
        'grapes_code': {
            'html': html_content,
            'css': css_content
        }
    }
    
    # Save the updated event
    success = marketing_service.save_event(update_data)
    
    if success:
        return jsonify({"status": "success"})
    else:
        return jsonify({"status": "error", "message": "Failed to save event"}), 500

@marketing_blueprint.route('/events/<event_id>/save-image', methods=['POST'])
def save_event_image(event_id):
    """API endpoint to save the final image for an event"""
    # Check if the event exists using the service
    marketing_service = get_marketing_service()
    event = marketing_service.get_event_by_id(event_id)
    
    if not event:
        return jsonify({"status": "error", "message": "Event not found"}), 404
    
    # Check if there's a file in the request
    if 'file' not in request.files:
        return jsonify({"success": False, "message": "No image file found in request"})
    
    file = request.files['file']
    if file.filename == '':
        return jsonify({"success": False, "message": "No file selected"})
    
    # In production, save the file with event_id as name
    # file_path = os.path.join('static', 'images', f"{event_id}.png")
    # file.save(file_path)
    
    # Mark the event as completed using the service
    success = marketing_service.mark_event_completed(event_id)
    
    if success:
        return jsonify({"success": True, "message": "Event image saved successfully"})
    else:
        return jsonify({"success": False, "message": "Failed to mark event as completed"})

@marketing_blueprint.route('/events/<event_id>/post-to-discord', methods=['POST'])
def post_event_to_discord(event_id):
    """API endpoint to send banner image to Discord for a specific event"""
    try:
        webhook_url = marketing_config['post_webhook_url']
        
        if not webhook_url:
            return jsonify({"success": False, "message": "No post webhook URL configured"})
        
        # Check if there's a file in the request
        if 'file' not in request.files:
            return jsonify({"success": False, "message": "No image file found in request"})
        
        file = request.files['file']
        if file.filename == '':
            return jsonify({"success": False, "message": "No file selected"})
        
        # Get optional message content
        message_content = request.form.get('content', 'Generated banner from SoDA Marketing Bot')
        
        # Prepare the payload for Discord
        payload = {
            "content": message_content
        }
        
        # Create multipart form data
        files = {
            'payload_json': (None, json.dumps(payload), 'application/json'),
            'file': (file.filename, file.stream, file.content_type)
        }
        
        # Send the file to Discord webhook
        response = requests.post(webhook_url, files=files)
        
        if response.status_code == 204:  # Discord returns 204 No Content on success
            # Mark this event as completed using the service
            marketing_service = get_marketing_service()
            marketing_service.mark_event_completed(event_id)
            marketing_service.log_activity(event_id, 'post_discord', 'success', 'discord')
                
            return jsonify({
                "success": True, 
                "message": "Image successfully sent to Discord"
            })
        else:
            error_info = response.text if response.text else f"Status code: {response.status_code}"
            marketing_service = get_marketing_service()
            marketing_service.log_activity(event_id, 'post_discord', 'failed', 'discord', error_info)
            return jsonify({
                "success": False, 
                "message": f"Failed to send image to Discord: {error_info}"
            })
            
    except Exception as e:
        marketing_service = get_marketing_service()
        marketing_service.log_activity(event_id, 'post_discord', 'failed', 'discord', str(e))
        return jsonify({"success": False, "message": str(e)})

@marketing_blueprint.route('/events/<event_id>/post-to-socials', methods=['POST'])
def post_event_to_socials(event_id):
    """API endpoint to send event banner to social media platforms via OneUp"""
    try:
        # Check credentials
        oneup_email = marketing_config['oneup_email']
        oneup_password = marketing_config['oneup_pass']
        
        if not oneup_email or not oneup_password:
            return jsonify({"success": False, "message": "OneUp credentials not configured"})
        
        # Check if the event exists using the service
        marketing_service = get_marketing_service()
        event = marketing_service.get_event_by_id(event_id)
        if not event:
            return jsonify({"success": False, "message": "Event not found"})
        
        # Check if there's a file in the request
        if 'file' not in request.files:
            return jsonify({"success": False, "message": "No image file found in request"})
        
        file = request.files['file']
        if file.filename == '':
            return jsonify({"success": False, "message": "No file selected"})
        
        # Read the file data
        image_data = file.read()
        
        # Get caption from event content
        caption = ""
        if event.get('content') and isinstance(event['content'], dict):
            caption = event['content'].get('text', '')
        
        # If no content from LLM, create a simple caption
        if not caption:
            return jsonify({"success": False, "message": "No content available for caption"})
        
        # Post to social media
        result = post_to_social_media(
            image_data=image_data,
            caption=caption,
            email=oneup_email,
            password=oneup_password,
            platforms=["instagram", "linkedin"]
        )
        
        if result["success"]:
            # Mark the event as completed using the service
            marketing_service.mark_event_completed(event_id)
            marketing_service.log_activity(event_id, 'post_social', 'success', 'instagram,linkedin')
        else:
            marketing_service.log_activity(event_id, 'post_social', 'failed', 'instagram,linkedin', result.get("message"))
            
        return jsonify(result)
            
    except Exception as e:
        marketing_service = get_marketing_service()
        marketing_service.log_activity(event_id, 'post_social', 'failed', 'instagram,linkedin', str(e))
        return jsonify({"success": False, "message": f"Error posting to social media: {str(e)}"})

@marketing_blueprint.route('/process-events-now', methods=['POST'])
def process_events_now():
    """Process events immediately"""
    thread = threading.Thread(target=process_events)
    thread.daemon = True
    thread.start()
    return jsonify({"status": "success", "message": "Started Processing Events..."})

# ==================================================================================================

# Other helper functions

os.makedirs('templates', exist_ok=True)

def ensure_template_files():
    """Ensure template files exist in the templates directory"""
    editor_html_path = os.path.join('templates', 'editor.html')
    editor_template_html = get_editor_html_css()
    view_html_path = os.path.join('templates', 'view.html')
    view_template_html = get_view_html_css()
    
    # Create editor.html if it doesn't exist
    with open(editor_html_path, 'w') as f:
        f.write(editor_template_html)

    # Create view.html if it doesn't exist
    with open(view_html_path, 'w') as f:
            f.write(view_template_html)

def process_events():
    """Process events using the marketing service"""
    try:
        marketing_service = get_marketing_service()
        marketing_service.monitor_events()
        
    except Exception as e:
        logger.error(f"Error in process_events: {e}")

def monitor_events():
    """Continuously monitor for upcoming events"""
    logger.info("Starting event monitoring...")
    
    while True:
        try:
            # Only process events if monitoring is active
            if marketing_config['monitoring_active']:
                process_events()
                
            # Sleep for the configured interval
            time.sleep(marketing_config['check_interval'])
        except Exception as e:
            logger.error(f"Error in monitor_events loop: {e}")
            # Sleep briefly before retrying
            time.sleep(60)

# Ensure template files exist when the module is imported
ensure_template_files()
