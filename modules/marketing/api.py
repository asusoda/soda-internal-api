from flask import Flask, render_template, request, jsonify, send_from_directory, Blueprint, redirect, url_for
import os
import threading
import time
import json
from datetime import datetime
import requests

# Import our modules
from get_events import get_upcoming_events
from get_template import get_discord_template
from generate_body import generate_content
from generate_code import generate_grapes_code
from get_editable_link import get_server_url
from send_message import send_officer_notification, post_instagram_post, post_linkedin_post
from dotenv import load_dotenv
from shared import logger, config
from get_database import (
    get_all_events, get_event_by_id, save_event, mark_event_completed,
    get_all_completed_events, is_event_completed
)
marketing_blueprint = Blueprint('marketing', __name__, template_folder='templates', static_folder='static')

# Load environment variables
load_dotenv()

# Global array to store multiple events and their generated content
# This will be populated by the event monitoring process
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

# Global configuration
config = {
    'api_url': config.TNAY_API_URL,
    'open_router_claude_api_key': config.OPEN_ROUTER_CLAUDE_API_KEY,
    'officer_webhook_url': config.DISCORD_OFFICER_WEBHOOK_URL,
    'oneup_email': config.ONEUP_EMAIL,
    'oneup_pass': config.ONEUP_PASSWORD,
    'post_webhook_url': config.DISCORD_POST_WEBHOOK_URL,
    'check_interval': 3600,  # 1 hour by default
    'monitoring_active': False
}

# Make sure the templates directory exists
os.makedirs('templates', exist_ok=True)

# Create template files if they don't exist
def ensure_template_files():
    """Ensure template files exist in the templates directory"""
    editor_html_path = os.path.join('templates', 'editor.html')
    view_html_path = os.path.join('templates', 'view.html')
    
    # Create editor.html if it doesn't exist
    with open(editor_html_path, 'w') as f:
        f.write('''
<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>GrapesJS Editor</title>
<!-- GrapesJS and dependencies -->
<link href="https://unpkg.com/grapesjs/dist/css/grapes.min.css" rel="stylesheet">
<script src="https://unpkg.com/grapesjs"></script>
<script src="https://unpkg.com/grapesjs-preset-webpage"></script>
<script src="https://cdnjs.cloudflare.com/ajax/libs/html2canvas/1.4.1/html2canvas.min.js"></script>

<link href="https://fonts.googleapis.com/css2?family=Leckerli+One&display=swap" rel="stylesheet">

<style>
    body, html {
        margin: 0;
        height: 100%;
    }

    @import url('https://fonts.googleapis.com/css2?family=Pacifico&display=swap');

    .topbar {
        display: flex;
        align-items: center;
        justify-content: space-between;
        padding: 8px 16px;
        background-color: #4a4a4a; /* Dark grey toolbar background */
        border-bottom: 1px solid #1a1a1a;
        height: 48px;
    }

    .topbar-title {
        font-family: 'Leckerli One', cursive;
        font-size: 24px;
        color: #e865dd; /* Beautiful purple color */
        margin: 0;
    }

    .topbar-buttons {
        display: flex;
        gap: 8px;
    }

    .gjs-btn {
        background-color: #3a3f44; /* Dark grey button */
        border: 0px solid #555;
        color: #e865dd; 
        font-size: 14px;
        padding: 6px 16px;
        border-radius: 6px;
        cursor: pointer;
        transition: background 0.2s ease, color 0.2s ease;
    }

    .gjs-btn:hover {
        background-color: #555a60;
        color: #ff85c1;
    }
    #editor {
        height: calc(100% - 56px);
    }
    .status-message {
        background: #27ae60;
        color: white;
        padding: 10px;
        text-align: center;
        position: fixed;
        top: 0;
        left: 0;
        right: 0;
        z-index: 1000;
        transform: translateY(-100%);
        transition: transform 0.3s ease;
    }
    .status-message.show {
        transform: translateY(0);
    }
</style>
</head>
<body>
<div id="status-message" class="status-message">Message</div>

<div class="topbar">
    <div class="topbar-title">GrapesJS Editor</div>
    <div class="topbar-buttons">
    <button id="view-btn" class="gjs-btn">View Page</button>
    <button id="save-btn" class="gjs-btn">Save Changes</button>
    <button id="save-html-btn" class="gjs-btn">Save as HTML</button>
    <button id="save-image-btn" class="gjs-btn">Save as Image</button>
    <button id="send-discord-btn" class="gjs-btn">Send to Discord</button>
    <button id="send-socials-btn" class="gjs-btn">Send to Socials</button>

    
    </div>
</div>

<div id="editor"></div>

<script>
    const editor = grapesjs.init({
        container: '#editor',
        height: '100%',
        width: 'auto',
        fromElement: false,
        storageManager: false,
        plugins: ['gjs-preset-webpage'],
        pluginsOpts: {
            'gjs-preset-webpage': {}
        }
    });

    // Show status message function
    function showStatusMessage(message, isError = false) {
        const statusEl = document.getElementById('status-message');
        statusEl.textContent = message;
        statusEl.style.backgroundColor = isError ? '#e74c3c' : '#27ae60';
        statusEl.classList.add('show');
        
        setTimeout(() => {
            statusEl.classList.remove('show');
        }, 3000);
    }

    // Load content from the server
    fetch('/load-content')
        .then(response => response.json())
        .then(data => {
            // Set the editor content
            editor.setComponents(data.html);
            editor.setStyle(data.css);
        })
        .catch(error => {
            console.error('Error loading content:', error);
            showStatusMessage('Error loading content', true);
        });

    // Save button handler
    document.getElementById('save-btn').addEventListener('click', () => {
        const htmlContent = editor.getHtml();
        const cssContent = editor.getCss();
        
        fetch('/update-content', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({
                html: htmlContent,
                css: cssContent
            }),
        })
        .then(response => response.json())
        .then(data => {
            if (data.status === 'success') {
                showStatusMessage('Content saved successfully!');
            } else {
                showStatusMessage('Error saving content', true);
            }
        })
        .catch(error => {
            console.error('Error saving content:', error);
            showStatusMessage('Error saving content', true);
        });
    });

    
    // Save as HTML button handler
    document.getElementById('save-html-btn').addEventListener('click', () => {
        const htmlContent = editor.getHtml();
        const cssContent = editor.getCss();

        const fullHtml = `
            <!DOCTYPE html>
            <html lang="en">
            <head>
                <meta charset="UTF-8">
                <meta name="viewport" content="width=device-width, initial-scale=1.0">
                <title>Exported GrapesJS Page</title>
                <style>
                    ${cssContent}
                </style>
            </head>
            <body>
                ${htmlContent}
            </body>
            </html>
            `;

        const blob = new Blob([fullHtml], { type: 'text/html' });
        const url = URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = 'soda_banner_full.html';
        a.click();
        URL.revokeObjectURL(url);
    });

    // Save as Image button handler
    document.getElementById('save-image-btn').addEventListener('click', () => {
        const iframe = document.querySelector('.gjs-frame');
        if (!iframe) {
            alert('GrapesJS iframe not found.');
            return;
        }

        const iframeDocument = iframe.contentDocument || iframe.contentWindow.document;

        // Try to select the banner block specifically if it exists
        let targetElement = iframeDocument.querySelector('.banner');
        if (!targetElement) {
            // Fallback to capture entire body if no .banner found
            targetElement = iframeDocument.body;
        }

        html2canvas(targetElement, {
            allowTaint: true,
            useCORS: true,
            backgroundColor: null
        }).then(canvas => {
            const link = document.createElement('a');
            link.download = 'soda_banner_only.png';
            link.href = canvas.toDataURL();
            link.click();
        }).catch(err => {
            console.error('Error capturing image:', err);
            alert('Failed to capture image.');
        });
    });

    // Send to Discord button handler
    document.getElementById('send-discord-btn').addEventListener('click', () => {
        const iframe = document.querySelector('.gjs-frame');
        if (!iframe) {
            alert('GrapesJS iframe not found.');
            return;
        }

        const iframeDocument = iframe.contentDocument || iframe.contentWindow.document;
        let targetElement = iframeDocument.querySelector('.banner');
        if (!targetElement) {
            targetElement = iframeDocument.body;
        }

        html2canvas(targetElement, {
            allowTaint: true,
            useCORS: true,
            backgroundColor: null
        }).then(canvas => {
            canvas.toBlob(blob => {
                const formData = new FormData();
                formData.append('file', blob, 'soda_banner.png');
                formData.append('content', '@audience');

                fetch('/post-to-discord', {
                    method: 'POST',
                    body: formData
                }).then(response => response.json())
                .then(data => {
                    if (data.success) {
                        showStatusMessage('Image sent to Discord successfully!');
                    } else {
                        showStatusMessage('Failed to send image to Discord', true);
                    }
                }).catch(err => {
                    console.error('Network error sending to Discord:', err);
                    showStatusMessage('Network error sending image to Discord', true);
                });
            }, 'image/png');
        }).catch(err => {
            console.error('Error capturing image:', err);
            alert('Failed to capture image.');
        });
    });
    
    // Only including the part that needs to be modified

    // Send to Socials button handler
    document.getElementById('send-socials-btn').addEventListener('click', () => {
        const iframe = document.querySelector('.gjs-frame');
        if (!iframe) {
            alert('GrapesJS iframe not found.');
            return;
        }

        // First show a loading message
        showStatusMessage('Posting to social media, please wait...', false);

        const iframeDocument = iframe.contentDocument || iframe.contentWindow.document;
        let targetElement = iframeDocument.querySelector('.banner');
        if (!targetElement) {
            targetElement = iframeDocument.body;
        }

        html2canvas(targetElement, {
            allowTaint: true,
            useCORS: true,
            backgroundColor: null
        }).then(canvas => {
            canvas.toBlob(blob => {
                const formData = new FormData();
                formData.append('file', blob, 'soda_banner.png');

                fetch('/marketing/events/<EVENT_ID>/post-to-socials'.replace('<EVENT_ID>', window.location.pathname.split('/').pop()), {
                    method: 'POST',
                    body: formData
                }).then(response => response.json())
                .then(data => {
                    if (data.success) {
                        showStatusMessage('Successfully posted to social media!');
                    } else {
                        showStatusMessage('Failed to post to social media: ' + data.message, true);
                    }
                }).catch(err => {
                    console.error('Network error when posting to social media:', err);
                    showStatusMessage('Network error when posting to social media', true);
                });
            }, 'image/png');
        }).catch(err => {
            console.error('Error capturing image:', err);
            showStatusMessage('Failed to capture image', true);
        });
    });

</script>
</body>
</html>
        ''')

    # Create view.html if it doesn't exist
    with open(view_html_path, 'w') as f:
            f.write('''
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>GrapesJS Preview</title>
    <style id="page-styles"></style>
</head>
<body>
    <div id="content-container"></div>
    
    <script>
        // Load content from the server
        fetch('/load-content')
            .then(response => response.json())
            .then(data => {
                // Set the HTML content
                document.getElementById('content-container').innerHTML = data.html;
                
                // Set the CSS content
                document.getElementById('page-styles').textContent = data.css;
            })
            .catch(error => {
                console.error('Error loading content:', error);
                document.getElementById('content-container').innerHTML = 
                    '<div style="color: red; padding: 20px; text-align: center;">' +
                    '<h2>Error Loading Content</h2>' +
                    '<p>Could not load the page content. Please try again later.</p>' +
                    '</div>';
            });
    </script>
</body>
</html>
            ''')

@marketing_blueprint.route('/view/<event_id>')
def view_event(event_id):
    """Render the view-only page showing a specific event design"""
    # Find the event in our database
    event = get_event_by_id(event_id)
    
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
        # Find the event in our database
        event = get_event_by_id(current_event_id)
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
    
    # If editing a specific event, save it to the database
    if current_event_id:
        event = get_event_by_id(current_event_id)
        if event:
            event['grapes_code'] = editor_content
            save_event(event)
            
    return jsonify({"status": "success"})

@marketing_blueprint.route('/status', methods=['GET'])
def get_status():
    """Get monitoring status"""
    return jsonify({
        "monitoring_active": config['monitoring_active'],
        "check_interval": config['check_interval'],
        "api_url_configured": bool(config['api_url']),
        "officer_webhook_configured": bool(config['officer_webhook_url']),
        "post_webhook_configured": bool(config['post_webhook_url']),
        "api_key_configured": bool(config['open_router_claude_api_key'])
    })

@marketing_blueprint.route('/toggle-monitoring', methods=['POST'])
def toggle_monitoring():
    """Toggle event monitoring on/off"""
    config['monitoring_active'] = not config['monitoring_active']
    return jsonify({
        "status": "success", 
        "monitoring_active": config['monitoring_active']
    })

@marketing_blueprint.route('/')
def dashboard():
    """Admin dashboard showing all managed events"""
    # Get all events from database
    managed_events = get_all_events()
    completed_events_dict = get_all_completed_events()
    
    # First, convert the events to safe HTML
    event_cards = []
    for event in managed_events:
        # Format the date nicely
        try:
            date_obj = datetime.fromisoformat(event['date'].replace('Z', '+00:00'))
            formatted_date = date_obj.strftime("%A, %B %d, %Y at %I:%M %p")
        except Exception:
            formatted_date = event['date']
            
        # Create HTML for the event card
        completed = event['status'] == 'completed' or event['id'] in completed_events_dict
        checked_attr = 'checked' if completed else ''
        disabled_attr = 'disabled' if completed else ''
        
        event_card = f'''
        <div class="event-card {event['status']}">
            <div class="event-header">
                <h3>{event['name']}</h3>
                <div class="event-status">
                    <input type="checkbox" {checked_attr} {disabled_attr}/>
                    <span>{event['status'].capitalize()}</span>
                </div>
            </div>
            <div class="event-details">
                <p><strong>Date:</strong> {formatted_date}</p>
                <p><strong>Location:</strong> {event['location']}</p>
                <div class="event-actions">
                    <a href="/marketing/events/{event['id']}" class="btn btn-edit" target="_blank">Edit</a>
                    <a href="/marketing/view/{event['id']}" class="btn btn-view" target="_blank">View</a>
                </div>
            </div>
        </div>
        '''
        event_cards.append(event_card)
    
    
    # Join all event cards
    events_html = "\n".join(event_cards) if event_cards else '<p>No events found. Use "Process Events Now" to check for new events.</p>'
    
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
    # Find the event in our database
    event = get_event_by_id(event_id)
    
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
    # Find the event in our database
    event = get_event_by_id(event_id)
    
    if not event:
        return jsonify({"status": "error", "message": "Event not found"}), 404
    
    data = request.json
    html_content = data.get('html', '')
    css_content = data.get('css', '')
    
    # Update the event's grapes_code
    event['grapes_code'] = {
        'html': html_content,
        'css': css_content
    }
    
    # Save the updated event
    save_event(event)
    
    return jsonify({"status": "success"})

@marketing_blueprint.route('/events/<event_id>/save-image', methods=['POST'])
def save_event_image(event_id):
    """API endpoint to save the final image for an event"""
    # Check if the event exists
    event = get_event_by_id(event_id)
    
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
    
    # Mark the event as completed
    mark_event_completed(event_id, event.get('name'))
    
    return jsonify({"success": True, "message": "Event image saved successfully"})

@marketing_blueprint.route('/events/<event_id>/post-to-discord', methods=['POST'])
def post_event_to_discord(event_id):
    """API endpoint to send banner image to Discord for a specific event"""
    try:
        webhook_url = config['post_webhook_url']
        
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
            # Mark this event as completed
            mark_event_completed(event_id)
                
            return jsonify({
                "success": True, 
                "message": "Image successfully sent to Discord"
            })
        else:
            error_info = response.text if response.text else f"Status code: {response.status_code}"
            return jsonify({
                "success": False, 
                "message": f"Failed to send image to Discord: {error_info}"
            })
            
    except Exception as e:
        return jsonify({"success": False, "message": str(e)})

@marketing_blueprint.route('/events/<event_id>/post-to-socials', methods=['POST'])
def post_event_to_socials(event_id):
    """API endpoint to send event banner to social media platforms via OneUp"""
    try:
        # Import the selenium function
        from get_selenium import post_to_social_media
        
        # Check credentials
        oneup_email = config['oneup_email']
        oneup_password = config['oneup_pass']
        
        if not oneup_email or not oneup_password:
            return jsonify({"success": False, "message": "OneUp credentials not configured"})
        
        # Check if the event exists
        event = get_event_by_id(event_id)
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
            # Mark the event as completed
            mark_event_completed(event_id, event.get('name'))
            
        return jsonify(result)
            
    except Exception as e:
        return jsonify({"success": False, "message": f"Error posting to social media: {str(e)}"})

@marketing_blueprint.route('/process-events-now', methods=['POST'])
def process_events_now():
    """Process events immediately"""
    thread = threading.Thread(target=process_events)
    thread.daemon = True
    thread.start()
    return jsonify({"status": "success", "message": "Started Processing Events..."})

def process_events():
    """Process events at the instance"""
    try:
        # PROD
        events = get_upcoming_events(config['api_url'])
        
        # DEV
        # events = get_upcoming_events(config['api_url'], mock=True)
        if events is None or len(events) == 0:
            print("No events found or error fetching events")
            return
        
        for event in events:
            # Events are already filtered to exclude existing ones in get_upcoming_events
            print(f"Processing new event: {event['name']}")
            try:
                # Step 1: Generate content for platforms
                print("Generating content...")
                content = generate_content(event, config['open_router_claude_api_key'])
                
                # Step 2: Get HTML/CSS template
                print("Getting template...")
                template = get_discord_template()
                
                # Step 3: Generate GrapesJS code
                print("Generating GrapesJS code...")
                grapes_code = generate_grapes_code(event, template, content, config['open_router_claude_api_key'])
                
                # Step 4: Create an event object with all the generated content
                event_object = {
                    'id': event['id'],
                    'name': event['name'],
                    'date': event['date'],
                    'location': event['location'],
                    'info': event['info'],
                    'content': content,
                    'grapes_code': grapes_code,
                    'created_at': datetime.now().isoformat(),
                    'status': 'pending' # pending, completed
                }
                
                # Step 5: Save the event to the database
                save_event(event_object)
                
                # Step 6: Send Discord notification with the event-specific editor URL
                print("Sending Discord notification...")
                server_url = get_server_url()
                editor_url = f"{server_url}/marketing/events/{event['id']}"
                
                notification_result = send_officer_notification(event, content, editor_url, config['officer_webhook_url'])
                if not notification_result["success"]:
                    print(f"ERROR: {notification_result['message']}")
                    return False
                
                print(f"✅ Successfully processed event: {event['name']}")
                return True
                
            except Exception as e:
                print(f"ERROR processing event {event['name']}: {str(e)}")
                return False
                
    except Exception as e:
        print(f"Error processing events: {str(e)}")

def monitor_events():
    """Continuously monitor for upcoming events"""
    print("Starting event monitoring...")
    
    while True:
        try:
            # Only process events if monitoring is active
            if config['monitoring_active']:
                process_events()
            
            # Sleep for the specified interval
            time.sleep(config['check_interval'])
            
        except Exception as e:
            print(f"Error in monitoring loop: {str(e)}")
            time.sleep(60)  # Sleep briefly before retrying          

if __name__ == '__main__':
    # Ensure template files exist
    ensure_template_files()
    
    # Start the event monitoring in a background thread
    monitor_thread = threading.Thread(target=monitor_events)
    monitor_thread.daemon = True
    monitor_thread.start()
    
    # Print some info
    print("SoDA Marketing Bot")
    print("=================")    