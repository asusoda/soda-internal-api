# app.py - Consolidated Flask application with event monitoring
from flask import Flask, render_template, request, jsonify, send_from_directory, Blueprint
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

marketing_blueprint = Blueprint('marketing', __name__, template_folder='templates', static_folder='static')

# Load environment variables
load_dotenv()

# Store the current editor content
editor_content = {
    'html': '<div class="default">Default content - will be replaced by LLM content</div>',
    'css': '.default{padding:15px;background-color:#f0f0f0;text-align:center;}'
}

# Global configuration
config = {
    'api_url': config.TNAY_API_URL,
    'api_key': config.ANTHROPIC_API_KEY,
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
<!-- templates/editor.html -->
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
    <button id="send-instagram-btn" class="gjs-btn">Send to Instagram</button>
    <button id="send-linkedin-btn" class="gjs-btn">Send to LinkedIn</button>

    
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

    // View button handler
    document.getElementById('view-btn').addEventListener('click', () => {
        window.open('/view', '_blank');
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
        // Send to Instagram button handler
document.getElementById('send-instagram-btn').addEventListener('click', () => {
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
            // Prompt for a caption
            const caption = prompt('Enter Instagram caption:', 'Check out our upcoming SoDA event!');
            if (!caption) return; // User cancelled
            
            const formData = new FormData();
            formData.append('file', blob, 'soda_banner.png');
            formData.append('caption', caption);

            fetch('/post-to-instagram', {
                method: 'POST',
                body: formData
            }).then(response => response.json())
            .then(data => {
                if (data.success) {
                    showStatusMessage('Image sent to Instagram successfully!');
                } else {
                    showStatusMessage('Failed to send image to Instagram: ' + data.message, true);
                }
            }).catch(err => {
                console.error('Network error sending to Instagram:', err);
                showStatusMessage('Network error sending image to Instagram', true);
            });
        }, 'image/png');
    }).catch(err => {
        console.error('Error capturing image:', err);
        alert('Failed to capture image.');
    });
});

// Send to LinkedIn button handler
document.getElementById('send-linkedin-btn').addEventListener('click', () => {
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
            // Prompt for LinkedIn content
            const content = prompt('Enter LinkedIn post content:', 'Excited to announce our upcoming SoDA event!');
            if (!content) return; // User cancelled
            
            const formData = new FormData();
            formData.append('file', blob, 'soda_banner.png');
            formData.append('content', content);

            fetch('/post-to-linkedin', {
                method: 'POST',
                body: formData
            }).then(response => response.json())
            .then(data => {
                if (data.success) {
                    showStatusMessage('Content sent to LinkedIn successfully!');
                } else {
                    showStatusMessage('Failed to send content to LinkedIn: ' + data.message, true);
                }
            }).catch(err => {
                console.error('Network error sending to LinkedIn:', err);
                showStatusMessage('Network error sending content to LinkedIn', true);
            });
        }, 'image/png');
    }).catch(err => {
        console.error('Error capturing image:', err);
        alert('Failed to capture image.');
    });
});

</script>
</body>
</html>
        ''')

    # Create view.html if it doesn't exist
    with open(view_html_path, 'w') as f:
            f.write('''
<!-- templates/view.html -->
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

@marketing_blueprint.route('/')
def home():
    """Render the main editor page"""
    return render_template('editor.html')

@marketing_blueprint.route('/load-content', methods=['GET'])
def load_content():
    """API endpoint to load the current editor content"""
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
    return jsonify({"status": "success"})

@marketing_blueprint.route('/view')
def view():
    """Render the view-only page showing the current design"""
    return render_template('view.html')

@marketing_blueprint.route('/post-to-discord', methods=['POST'])
def post_to_discord():
    """API endpoint to send banner image to Discord via webhook"""
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

@marketing_blueprint.route('/post-to-instagram', methods=['POST'])
def post_to_instagram():
    """API endpoint to send banner image to Instagram via OneUp API"""
    try:
        oneup_api_url = config.get('oneup_api_url', os.environ.get("ONEUP_API_URL"))
        
        if not oneup_api_url:
            return jsonify({"success": False, "message": "No OneUp API URL configured"})
        
        # Check if there's a file in the request
        if 'file' not in request.files:
            return jsonify({"success": False, "message": "No image file found in request"})
        
        file = request.files['file']
        if file.filename == '':
            return jsonify({"success": False, "message": "No file selected"})
        
        # Get caption content
        caption = request.form.get('caption', 'Check out our upcoming SoDA event!')
        
        # Send to Instagram using OneUp API
        result = post_instagram_post(file.read(), caption, oneup_api_url)
        
        return jsonify(result)
            
    except Exception as e:
        return jsonify({"success": False, "message": str(e)})

@marketing_blueprint.route('/post-to-linkedin', methods=['POST'])
def post_to_linkedin():
    """API endpoint to send banner image to LinkedIn via OneUp API"""
    try:
        oneup_api_url = config.get('oneup_api_url', os.environ.get("ONEUP_API_URL"))
        
        if not oneup_api_url:
            return jsonify({"success": False, "message": "No OneUp API URL configured"})
        
        # Check if there's a file in the request
        if 'file' not in request.files:
            return jsonify({"success": False, "message": "No image file found in request"})
        
        file = request.files['file']
        if file.filename == '':
            return jsonify({"success": False, "message": "No file selected"})
        
        # Get content for LinkedIn post
        content = request.form.get('content', 'Excited to announce our upcoming SoDA event!')
        
        # Send to LinkedIn using OneUp API
        result = post_linkedin_post(file.read(), content, oneup_api_url)
        
        return jsonify(result)
            
    except Exception as e:
        return jsonify({"success": False, "message": str(e)}) 
    
@marketing_blueprint.route('/status', methods=['GET'])
def get_status():
    """Get monitoring status"""
    return jsonify({
        "monitoring_active": config['monitoring_active'],
        "check_interval": config['check_interval'],
        "api_url_configured": bool(config['api_url']),
        "officer_webhook_configured": bool(config['officer_webhook_url']),
        "post_webhook_configured": bool(config['post_webhook_url']),
        "api_key_configured": bool(config['api_key'])
    })

@marketing_blueprint.route('/toggle-monitoring', methods=['POST'])
def toggle_monitoring():
    """Toggle event monitoring on/off"""
    config['monitoring_active'] = not config['monitoring_active']
    return jsonify({
        "status": "success", 
        "monitoring_active": config['monitoring_active']
    })

@marketing_blueprint.route('/dashboard')
def dashboard():
    """Simple admin dashboard"""
    return '''
    <!DOCTYPE html>
    <html>
    <head>
        <title>SoDA Marketing Bot Dashboard</title>
        <style>
            body { font-family: Arial, sans-serif; max-width: 800px; margin: 0 auto; padding: 20px; }
            .card { background: #f5f5f5; border-radius: 5px; padding: 15px; margin-bottom: 15px; }
            button { background: #4CAF50; color: white; border: none; padding: 10px 15px; border-radius: 4px; cursor: pointer; }
            button.stop { background: #f44336; }
            .status { margin: 20px 0; }
            .status-indicator { display: inline-block; width: 12px; height: 12px; border-radius: 50%; margin-right: 5px; }
            .status-active { background: #4CAF50; }
            .status-inactive { background: #f44336; }
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
            <button onclick="window.open('/', '_blank')">Open Editor</button>
            <button onclick="window.open('/view', '_blank')">View Banner</button>
            <button id="process-events-btn">Process Events Now</button>
        </div>
        
        <script>
            // Load status
            function updateStatus() {
                fetch('/status')
                    .then(response => response.json())
                    .then(data => {
                        const statusIndicator = document.getElementById('status-indicator');
                        const statusText = document.getElementById('status-text');
                        const toggleBtn = document.getElementById('toggle-btn');
                        
                        if (data.monitoring_active) {
                            statusIndicator.className = 'status-indicator status-active';
                            statusText.textContent = 'Monitoring is ACTIVE';
                            toggleBtn.textContent = 'Stop Monitoring';
                            toggleBtn.className = 'stop';
                        } else {
                            statusIndicator.className = 'status-indicator status-inactive';
                            statusText.textContent = 'Monitoring is INACTIVE';
                            toggleBtn.textContent = 'Start Monitoring';
                            toggleBtn.className = '';
                        }
                    });
            }
            
            // Toggle monitoring
            document.getElementById('toggle-btn').addEventListener('click', () => {
                fetch('/toggle-monitoring', { method: 'POST' })
                    .then(response => response.json())
                    .then(data => {
                        updateStatus();
                    });
            });
            
            // Process events now
            document.getElementById('process-events-btn').addEventListener('click', () => {
                fetch('/process-events', { method: 'POST' })
                    .then(response => response.json())
                    .then(data => {
                        alert(data.message);
                    });
            });
            
            // Update status on load
            updateStatus();
        </script>
    </body>
    </html>
    '''

@marketing_blueprint.route('/process-events', methods=['POST'])
def process_events_now():
    """Process events immediately"""
    thread = threading.Thread(target=process_events_once)
    thread.daemon = True
    thread.start()
    return jsonify({"status": "success", "message": "Started Processing Events..."})

def process_events_once():
    """Process events one time"""
    try:
        # PROD
        events = get_upcoming_events(config['api_url'])
        
        # DEV
        # events = get_upcoming_events(config['api_url'], mock=True)
        if events is None:
            print("No events found or error fetching events")
            return jsonify({"status": "success", "message": "No events found"})
                
        for event in events:
            process_event(event)
    except Exception as e:
        print(f"Error processing events: {str(e)}")

def process_event(event):
    """Process a single event through the entire workflow"""
    print(f"\nProcessing event: {event['name']}")
    
    try:
        # Step 1: Generate content for platforms
        print("Generating content...")
        content = generate_content(event, config['api_key'])
        
        # Step 2: Get HTML/CSS template
        print("Getting template...")
        template = get_discord_template()
        
        # Step 3: Generate GrapesJS code
        print("Generating GrapesJS code...")
        grapes_code = generate_grapes_code(event, template, content, config['api_key'])
        
        # Step 4: Push content to editor
        print("Updating GrapesJS content...")
        global editor_content
        editor_content = {
            'html': grapes_code["html"],
            'css': grapes_code["css"]
        }
        
        # Step 5: Send Discord notification
        print("Sending Discord notification...")
        server_url = get_server_url()
        notification_result = send_officer_notification(event, content, server_url, config['officer_webhook_url'])
        if not notification_result["success"]:
            print(f"ERROR: {notification_result['message']}")
            return False
        
        print(f"✅ Successfully processed event: {event['name']}")
        return True
        
    except Exception as e:
        print(f"ERROR processing event {event['name']}: {str(e)}")
        return False

def monitor_events():
    """Continuously monitor for upcoming events"""
    print("Starting event monitoring...")
    
    while True:
        try:
            # Only process events if monitoring is active
            if config['monitoring_active']:
                process_events_once()
            
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