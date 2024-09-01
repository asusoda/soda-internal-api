from selenium import webdriver
from selenium.webdriver.chrome.service import Service as ChromeService
from webdriver_manager.chrome import ChromeDriverManager
from selenium.webdriver import ChromeOptions
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
import logging
import sys
import time
import re
import os
from flask import Blueprint, jsonify, request

class InvitationSender:
    def __init__(self, username, password):
        # Initialize WebDriver and Logger
        self.driver = None
        self.username = username
        self.password = password
        self.init_webdriver()
        self.emails = set()

    def init_webdriver(self):
        
        """Initialize the Chrome WebDriver with custom paths for ChromeDriver and Chrome binaries."""
        options = ChromeOptions()
        #options.add_argument('--headless')  # Run in headless mode
        options.add_argument('--no-sandbox')  # Bypass OS security model
        #options.add_argument('--disable-dev-shm-usage')  # Overcome limited resource problems
        options.add_argument('--user-data-dir={}/userdata'.format(os.getcwd()))  # Use user data if needed

        # Custom paths for ChromeDriver and Chrome binaries updating path to chrom driver in the root directory of the project
        # chrome_driver_path = os.getcwd() + '/chromedriver-linux64/chromedriver'  
        # chrome_binary_path = os.getcwd() + '/chrome-linux64/chromelinux64/chrome'
        # options.binary_location = chrome_binary_path

        # print(f"ChromeDriver Path: {chrome_driver_path}")
        # print(f"Chrome Binary Path: {chrome_binary_path}" + '\n')

        try:
            print("Installing ChromeDriver")
            self.driver = webdriver.Chrome(service=ChromeService(ChromeDriverManager().install()), options=options)
            print(self.driver) #debugging
            #self.driver = webdriver.Chrome(executable_path=chrome_driver_path, options=options)
            logging.info("ChromeDriver initialized successfully with custom paths.")
        except Exception as e:
            logging.error(f"Failed to initialize ChromeDriver: {e}")
            sys.exit(1)

    def login(self, retries=3):
        """Log in to the site, handling Duo 2FA if necessary, with retries on failure."""
        print("logging in") #debugging

        for attempt in range(retries):
            print(attempt)
            try:
                print("opening url")
                invitation_url = 'https://asu.campuslabs.com/engage/actioncenter/organization/soda/roster/Roster/invite'
                print("adding url to driver")
                self.driver.get(invitation_url)
                logging.info(f"Opened URL: {invitation_url}")
                print(f"Opened URL: {invitation_url}")

                # Attempt to find the email text box to check if already logged in
                email_textarea = WebDriverWait(self.driver, 10).until(
                    EC.visibility_of_element_located((By.XPATH, '//*[@id="GroupInviteByEmail"]'))
                )
                print("Already logged in. Email text box is visible.") #debugging
                logging.info("Already logged in. Email text box is visible.")
                return True

            except:
                print("Proceeding with login.") #debugging
                logging.info("Proceeding with login.")

            try:
                print("trying to submit credentials") #debugging
                WebDriverWait(self.driver, 20).until(EC.visibility_of_element_located((By.ID, 'username')))
                self.driver.find_element(By.ID, 'username').send_keys(self.username)
                self.driver.find_element(By.ID, 'password').send_keys(self.password)
                self.driver.find_element(By.NAME, 'submit').click()
                logging.info("Login credentials submitted.")
                print("Login credentials submitted.") #debugging
                

                # # Handle Duo 2FA
                print("sending Duo")
                WebDriverWait(self.driver, 20).until(
                    EC.frame_to_be_available_and_switch_to_it((By.XPATH, '//iframe[@id="duo_iframe"]')))
                WebDriverWait(self.driver, 20).until(
                    EC.element_to_be_clickable((By.XPATH, '//*[@id="login-form"]/div[2]/div/label/input'))).click()
                WebDriverWait(self.driver, 20).until(
                    EC.element_to_be_clickable((By.XPATH, '//button[normalize-space()="Send Me a Push"]'))).click()
                logging.info(f'Duo 2FA push sent.')
                print(f'Duo 2FA push sent.') #debugging

                # Confirm Duo 2FA push
                print("clicking button")
                self.driver.switch_to.default_content()
                yes_button = WebDriverWait(self.driver, 60).until(
                    EC.element_to_be_clickable((By.XPATH, '//button[contains(text(), "Yes, this is my device")]')))
                #debugging
                print("yes_button")
                yes_button.click()
                logging.info('Clicked "Yes, this is my device" button.')

                # Wait for email text box visibility
                WebDriverWait(self.driver, 60).until(
                    EC.visibility_of_element_located((By.XPATH, '//*[@id="GroupInviteByEmail"]')))
                logging.info("Email text box is visible, login successful.")
                return True

            except Exception as e:
                print(self.username)
                logging.error(f'Failed to log in: {e}')
                

            if attempt < retries - 1:
                logging.info(f"Retrying login ({attempt + 1}/{retries})...")
                time.sleep(15)  # Wait a moment before retrying
            else:
                logging.error("Max retries reached. Login failed.")
                return False

    def add_emails_and_send_invitations(self):
        """Add emails to the form and send invitations."""

        try:

            self.driver.get('https://asu.campuslabs.com/engage/actioncenter/organization/soda/roster/Roster/invite')

            email_textarea = WebDriverWait(self.driver, 20).until(
                EC.visibility_of_element_located((By.XPATH, '//*[@id="GroupInviteByEmail"]'))
            )
            email_textarea.send_keys("\n".join(self.emails))
            logging.info(f'Entered emails: {", ".join(self.emails)}')

            add_email_button = WebDriverWait(self.driver, 20).until(
                EC.element_to_be_clickable((By.XPATH, '//*[@id="GroupInviteByEmailSubmit"]'))
            )
            add_email_button.click()
            logging.info('Clicked "Add Email" button.')

            time.sleep(2)

            send_invitation_button = WebDriverWait(self.driver, 20).until(
                EC.element_to_be_clickable((By.XPATH, '//*[@id="invitationActions_sendButton"]'))
            )
            send_invitation_button.click()
            logging.info('Clicked "Send Invitations" button.')

            logging.info('Invitations sent successfully.')
            print('Invitations sent successfully.')
            time.sleep(5)
            self.emails.clear()
            
        except Exception as e:
            logging.error(f'Error during the invitation process: {e}')