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

# if __name__ == "__main__":
#     # Test the templates
#     import json
#     templates = {
#         "base": get_base_templates(),
#         "instagram": get_instagram_template(),
#         "discord": get_discord_template(),
#         "email": get_email_template()
#     }
    
#     print("Available templates:")
#     for name in templates.keys():
#         print(f"- {name}")