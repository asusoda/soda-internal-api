from flask import  jsonify, request, Blueprint, redirect, url_for
from auth.decoraters import auth_required, error_handler
import time
from selenium import webdriver
from selenium.webdriver import ChromeOptions
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from dotenv import load_dotenv
import os
import re
import logging
import sys


from shared import username, password

users_blueprint = Blueprint("users", __name__, template_folder=None, static_folder=None)

emails = set()

@users_blueprint.route("/", methods=["GET"])
def users_index():
    return jsonify({"message": "users api"}), 200


@users_blueprint.route("/invite", methods=["POST", "GET" ])
@auth_required
@error_handler
def invite_users():
    if request.args.get("instructions")!= "refresh" and request.method == "GET":
        add_emails_and_send_invitations()
        return jsonify({"message": "Invitations sent successfully"}), 200
    else:
        email = request.args.get("email")
        pattern = r'^[a-zA-Z0-9._%+-]+@asu\.edu$'
        if email is None:
            return jsonify({"error": "Missing email parameter"}), 202
        elif re.match(pattern, email):
            emails.add(email)
            if len(emails) > 10:
                if login():
                    
                    add_emails_and_send_invitations()
                    emails.clear()
                    return jsonify({"message": "Invitations sent successfully"}), 200
                else:
                    email.add(email)
                    return jsonify({"message": "Logged Out"}), 200
            else:
                return jsonify({"message": "Email added to the list"}), 200
    

    
@users_blueprint.route("/login", methods=["POST"])
@auth_required
def login():
    if login():
         return redirect(url_for('users_blueprint.invite_users', instructions="refresh"))




# Load environment variables from .env file
load_dotenv()

# Configure logging
logger = logging.getLogger('club-invitation-sender')
logger.setLevel(logging.DEBUG)
file_log_handler = logging.FileHandler('sent_invitations.log')
file_log_handler.setLevel(logging.INFO)
stdout_log_handler = logging.StreamHandler(sys.stdout)
stdout_log_handler.setLevel(logging.DEBUG)
logger.addHandler(file_log_handler)
logger.addHandler(stdout_log_handler)

# Log format
formatter = logging.Formatter('%(asctime)s [%(levelname)s]: %(message)s')
file_log_handler.setFormatter(formatter)
stdout_log_handler.setFormatter(formatter)

# Configure Chrome options
options = ChromeOptions()
options.add_argument('--user-data-dir={}/userdata'.format(os.getcwd()))  # Use user data if needed

# Initialize the WebDriver
try:
    driver = webdriver.Chrome(options=options)  # Ensure ChromeDriver is in your PATH or specify the executable_path
    logger.info("ChromeDriver initialized successfully.")
except Exception as e:
    logger.error(f"Failed to initialize ChromeDriver: {e}")
    sys.exit(1)


invitation_url = 'https://asu.campuslabs.com/engage/actioncenter/organization/soda/roster/Roster/invite'

if not username or not password or not invitation_url:
    logger.error("Environment variables (username, password, invitation_url) are not properly set.")
    sys.exit(1)

def login():
    """Log in to the site, handling Duo 2FA if necessary."""
    try:
        driver.get(invitation_url)
        logger.info(f"Opened URL: {invitation_url}")
        # Check if the email text box is already visible, indicating the user is already logged in
        try:
            email_textarea = WebDriverWait(driver, 10).until(
                EC.visibility_of_element_located((By.XPATH, '//*[@id="GroupInviteByEmail"]'))
            )
            logger.info("Already logged in. Email text box is visible.")
            return True
        except:
            logger.info("Email text box not visible. Proceeding with login.")

        WebDriverWait(driver, 20).until(EC.visibility_of_element_located((By.ID, 'username')))
        logger.info("Login page loaded.")

        driver.find_element(By.ID, 'username').send_keys(username)
        driver.find_element(By.ID, 'password').send_keys(password)
        driver.find_element(By.NAME, 'submit').click()
        logger.info("Login credentials submitted.")

        WebDriverWait(driver, 20).until(
            EC.frame_to_be_available_and_switch_to_it((By.XPATH, '//iframe[@id="duo_iframe"]')))
        logger.info("Duo 2FA iframe loaded.")

        WebDriverWait(driver, 20).until(
            EC.element_to_be_clickable((By.XPATH, '//*[@id="login-form"]/div[2]/div/label/input'))).click()
        WebDriverWait(driver, 20).until(
            EC.element_to_be_clickable((By.XPATH, '//button[normalize-space()="Send Me a Push"]'))).click()
        logger.info(f'Duo 2FA push sent.')

        # Wait for "Yes, this is my device" button and click it
        driver.switch_to.default_content()  # Switch out of the iframe
        yes_button = WebDriverWait(driver, 60).until(
            EC.element_to_be_clickable((By.XPATH, '//button[contains(text(), "Yes, this is my device")]')))
        yes_button.click()
        logger.info('Clicked "Yes, this is my device" button.')

        # Wait until the email textbox is visible
        WebDriverWait(driver, 60).until(
            EC.visibility_of_element_located((By.XPATH, '//*[@id="GroupInviteByEmail"]')))
        logger.info("Email text box is visible, login successful.")

        return True
    except Exception as e:
        logger.error(f'Failed to log in: {e}')
        return False

def add_emails_and_send_invitations():
    """Add emails to the form and send invitations."""
    try:
        # Locate the email textarea and enter the emails
        email_textarea = WebDriverWait(driver, 20).until(
            EC.visibility_of_element_located((By.XPATH, '//*[@id="GroupInviteByEmail"]'))
        )
        email_textarea.send_keys("\n".join(emails))
        logger.info(f'Entered emails: {", ".join(emails)}')

        # Click the "Add Email" button
        add_email_button = WebDriverWait(driver, 20).until(
            EC.element_to_be_clickable((By.XPATH, '//*[@id="GroupInviteByEmailSubmit"]'))
        )
        add_email_button.click()
        logger.info('Clicked "Add Email" button.')
        time.sleep(2)  # Pause to observe the action

        # Wait for the "Send Invitations" button to appear and click it
        send_invitation_button = WebDriverWait(driver, 20).until(
            EC.element_to_be_clickable((By.XPATH, '//*[@id="invitationActions_sendButton"]'))
        )
        send_invitation_button.click()
        logger.info('Clicked "Send Invitations" button.')

        logger.info('Invitations sent successfully.')
        #pause to observe the action
        time.sleep(15)

    except Exception as e:
        logger.error(f'Error during the invitation process: {e}')

def main():
    """Main function to handle the login and invitation process."""
    if login():
        try:
            add_emails_and_send_invitations()
        except Exception as e:
            logger.error(f'Error during the process: {e}')

if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        logger.error(f'Unexpected error: {e}')
    finally:
        driver.quit()  # Ensure the browser closes after the script completes