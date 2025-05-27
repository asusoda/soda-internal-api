# all selenium related functions should be defined in get_selenium.py and used in api.py

# all selenium related functions should be defined in get_selenium.py and used in api.py
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException
import time
import os
import tempfile

def create_driver(headless=True):
    """
    Create a configured Selenium WebDriver for Chrome
    
    Args:
        headless (bool): Whether to run in headless mode
        
    Returns:
        WebDriver: Configured Chrome WebDriver instance
    """
    chrome_options = Options()
    
    if headless:
        chrome_options.add_argument("--headless")
    
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    chrome_options.add_argument("--disable-gpu")
    chrome_options.add_argument("--window-size=1920,1080")
    chrome_options.add_argument("--disable-extensions")
    
    # Create the driver
    driver = webdriver.Chrome(options=chrome_options)
    return driver

def login_to_oneup(driver, email, password):
    """
    Login to OneUp platform
    
    Args:
        driver (WebDriver): Selenium WebDriver instance
        email (str): OneUp account email
        password (str): OneUp account password
        
    Returns:
        bool: True if login successful, False otherwise
    """
    try:
        # Navigate to the OneUp login page
        driver.get("https://app.oneupapp.io/login")
        
        # Wait for the login form to load
        WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((By.ID, "email"))
        )
        
        # Enter email and password
        driver.find_element(By.ID, "email").send_keys(email)
        driver.find_element(By.ID, "password").send_keys(password)
        
        # Click the login button
        login_button = driver.find_element(By.XPATH, "//button[contains(text(), 'Log In')]")
        login_button.click()
        
        # Wait for dashboard to load - look for the "Create Post" button
        WebDriverWait(driver, 15).until(
            EC.presence_of_element_located((By.XPATH, "//button[contains(text(), 'Create Post')]"))
        )
        
        return True
    except (TimeoutException, NoSuchElementException) as e:
        print(f"Login error: {str(e)}")
        return False

def create_social_media_post(driver, image_data, caption, platforms=None):
    """
    Create a new post on OneUp
    
    Args:
        driver (WebDriver): Selenium WebDriver instance
        image_data (bytes): Image data to upload
        caption (str): Caption for the post
        platforms (list): List of platforms to post to, defaults to ["instagram", "linkedin"]
        
    Returns:
        bool: True if post was created successfully, False otherwise
    """
    if platforms is None:
        platforms = ["instagram", "linkedin"]
    
    try:
        # Click "Create Post" button
        create_post_button = driver.find_element(By.XPATH, "//button[contains(text(), 'Create Post')]")
        create_post_button.click()
        
        # Wait for the post editor to appear
        WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((By.XPATH, "//div[contains(@class, 'post-editor')]"))
        )
        
        # Select platforms
        for platform in platforms:
            try:
                platform_checkbox = driver.find_element(
                    By.XPATH, f"//label[contains(text(), '{platform.title()}')]"
                )
                platform_checkbox.click()
                time.sleep(0.5)  # Small delay between clicks
            except NoSuchElementException:
                print(f"Platform {platform} not found")
        
        # Upload image
        # First, we need to save the image data to a temporary file
        with tempfile.NamedTemporaryFile(suffix='.png', delete=False) as temp_file:
            temp_file.write(image_data)
            temp_file_path = temp_file.name
        
        # Find the file upload element and upload the image
        file_input = driver.find_element(By.XPATH, "//input[@type='file']")
        file_input.send_keys(temp_file_path)
        
        # Wait for image to upload
        WebDriverWait(driver, 20).until(
            EC.presence_of_element_located((By.XPATH, "//div[contains(@class, 'image-preview')]"))
        )
        
        # Enter caption
        caption_area = driver.find_element(By.XPATH, "//div[contains(@class, 'ql-editor')]")
        caption_area.send_keys(caption)
        
        # Click "Post Now" button
        post_now_button = driver.find_element(By.XPATH, "//button[contains(text(), 'Post Now')]")
        post_now_button.click()
        
        # Wait for confirmation message
        WebDriverWait(driver, 20).until(
            EC.presence_of_element_located((By.XPATH, "//div[contains(text(), 'Your post has been scheduled')]"))
        )
        
        # Clean up the temporary file
        os.unlink(temp_file_path)
        
        return True
    except (TimeoutException, NoSuchElementException) as e:
        print(f"Error creating post: {str(e)}")
        return False

def post_to_social_media(image_data, caption, email, password, platforms=None):
    """
    Main function to post to social media using OneUp
    
    Args:
        image_data (bytes): Image data to upload
        caption (str): Caption for the post
        email (str): OneUp account email
        password (str): OneUp account password
        platforms (list): List of platforms to post to
        
    Returns:
        dict: Result status and message
    """
    driver = None
    try:
        driver = create_driver()
        
        # Login to OneUp
        login_success = login_to_oneup(driver, email, password)
        if not login_success:
            return {
                "success": False,
                "message": "Failed to login to OneUp"
            }
        
        # Create the post
        post_success = create_social_media_post(driver, image_data, caption, platforms)
        if not post_success:
            return {
                "success": False,
                "message": "Failed to create social media post"
            }
        
        return {
            "success": True,
            "message": "Successfully posted to social media"
        }
    except Exception as e:
        return {
            "success": False,
            "message": f"Error posting to social media: {str(e)}"
        }
    finally:
        if driver:
            driver.quit()