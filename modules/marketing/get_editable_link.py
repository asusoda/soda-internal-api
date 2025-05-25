# pushes the code to the 
# grapejs server and forces 
# rerender
# { success 200 }
# filepath: /home/ash/student_orgs/SoDA/soda-marketing-bot/get_editable_link.py
import requests
import json
import socket
import time

def get_server_url(port=5000):
    """Get the server URL based on hostname and port"""
    hostname = socket.gethostname()
    return f"http://{hostname}:{port}"

def is_server_running(url):
    """Check if the Flask server is running"""
    try:
        response = requests.get(f"{url}/", timeout=5)
        return response.status_code == 200
    except requests.exceptions.RequestException:
        return False

def push_content_to_grapesjs(html, css, api_url=None):
    """
    Push HTML and CSS content to the GrapesJS server
    
    Args:
        html (str): HTML content
        css (str): CSS content
        api_url (str): URL of the update-content API endpoint
        
    Returns:
        dict: Response status and server URL
    """
    server_url = api_url if api_url else get_server_url()
    update_url = f"{server_url}/marketing/update-content" if not api_url else api_url
    
    if not is_server_running(server_url):
        return {
            "success": False, 
            "message": f"GrapesJS server not running at {server_url}",
            "url": None
        }
    
    payload = {
        "html": html,
        "css": css
    }
    
    try:
        response = requests.post(
            update_url,
            headers={"Content-Type": "application/json"},
            data=json.dumps(payload),
            timeout=10
        )
        
        if response.status_code == 200:
            result = response.json()
            if result.get("status") == "success":
                return {
                    "success": True,
                    "message": "Successfully updated GrapesJS content",
                    "url": f"{server_url}"
                }
        
        return {
            "success": False,
            "message": f"API request failed with status code {response.status_code}",
            "url": None
        }
    except Exception as e:
        return {
            "success": False,
            "message": f"Exception when updating GrapesJS: {str(e)}",
            "url": None
        }

def wait_for_server(url, max_attempts=5, wait_time=2):
    """Wait for server to be available"""
    attempts = 0
    while attempts < max_attempts:
        if is_server_running(url):
            return True
        time.sleep(wait_time)
        attempts += 1
    return False

# if __name__ == "__main__":
#     # Test pushing content
#     test_html = "<div>This is a test</div>"
#     test_css = "div { color: red; }"
    
#     result = push_content_to_grapesjs(test_html, test_css)
#     print(json.dumps(result, indent=2))