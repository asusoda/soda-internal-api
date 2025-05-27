# get's html and css 
# content from a generic
# template string
# "<html> css{} "

def get_base_templates():
    """
    Returns HTML and CSS templates for event banners
    
    Returns:
        dict: Dictionary containing HTML and CSS templates
    """
    # Base HTML template
    html_template = """
    <div class="banner">
        <div class="grid"></div>
        <div class="accent"></div>
        <div class="accent-2"></div>
        <div class="soda-logo">
            <h1>SoDA</h1>
            <p>Software Developers Association</p>
        </div>
        <div class="event-details">
            <h2>{{EVENT_TITLE}} <span class="highlight">{{EVENT_HIGHLIGHT}}</span></h2>
            <p>{{EVENT_DATE}}</p>
            <p>Location: <span class="highlight">{{EVENT_LOCATION}}</span></p>
            <p>{{EVENT_DESCRIPTION}}</p>
        </div>
    </div>
    """
    
    # Base CSS template
    css_template = """
    @import url('https://fonts.googleapis.com/css2?family=Poppins:wght@400;600;900&display=swap');

    /* Banner container */
    .banner {
        width: 500px;
        height: 500px;
        background-color: #000;
        position: relative;
        overflow: hidden;
        box-shadow: 0 15px 30px rgba(0,0,0,0.3);
        font-family: 'Poppins', sans-serif;
        color: white;
    }

    /* Grid background */
    .grid {
        position: absolute;
        top: 0;
        left: 0;
        right: 0;
        bottom: 0;
        background-image: 
            linear-gradient(rgba(30,30,30,0.5) 1px, transparent 1px),
            linear-gradient(90deg, rgba(30,30,30,0.5) 1px, transparent 1px);
        background-size: 20px 20px;
        z-index: 1;
    }

    /* SoDA branding */
    .soda-logo {
        position: absolute;
        top: 50px;
        left: 60px;
        z-index: 2;
    }

    .soda-logo h1 {
        font-size: 72px;
        font-weight: 900;
        letter-spacing: 1px;
        background: linear-gradient(90deg, #4776E6, #8E54E9);
        -webkit-background-clip: text;
        background-clip: text;
        -webkit-text-fill-color: transparent;
        margin: 0;
    }

    .soda-logo p {
        font-size: 18px;
        color: rgba(255,255,255,0.8);
        letter-spacing: 1px;
        margin-top: 5px;
    }

    /* Event details */
    .event-details {
        position: absolute;
        bottom: 60px;
        left: 60px;
        right: 60px;
        z-index: 2;
    }

    .event-details h2 {
        font-size: 30px;
        margin-bottom: 15px;
        color: #fff;
        font-weight: 600;
    }

    .event-details p {
        font-size: 20px;
        margin-bottom: 10px;
        color: rgba(255,255,255,0.9);
    }

    .highlight {
        color: #ff9900;
        font-weight: 600;
    }

    /* Accent decoration */
    .accent {
        position: absolute;
        right: -50px;
        top: -50px;
        width: 200px;
        height: 200px;
        background: linear-gradient(45deg, #ff9900, #ff9900aa);
        border-radius: 50%;
        z-index: 1;
        opacity: 0.4;
    }

    .accent-2 {
        position: absolute;
        left: -30px;
        bottom: -60px;
        width: 150px;
        height: 150px;
        background: linear-gradient(45deg, #4776E6, #8E54E9);
        border-radius: 50%;
        z-index: 1;
        opacity: 0.4;
    }
    """
    
    return {
        "html": html_template,
        "css": css_template
    }

def get_instagram_template():
    """Get template optimized for Instagram (square format)"""
    templates = get_base_templates()
    # Modify CSS for Instagram dimensions
    templates["css"] = templates["css"].replace("width: 500px;\n        height: 500px;", 
                                              "width: 1080px;\n        height: 1080px;")
    return templates

def get_discord_template():
    """Get template optimized for Discord"""
    return get_base_templates()

def get_email_template():
    """Get template optimized for email (landscape format)"""
    templates = get_base_templates()
    # Modify CSS for landscape email dimensions
    templates["css"] = templates["css"].replace("width: 500px;\n        height: 500px;", 
                                              "width: 1300px;\n        height: 780px;")
    return templates

def get_editor_html_css():
    """Get template HTML for grapesjs editor"""
    return ''' <!DOCTYPE html>
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
</html>'''
        
def get_view_html_css():
    """Get view HTML for grapesjs preview"""
    return '''
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
</html> '''

        