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
    _instance = None  # Singleton instance

    def __init__(self, username, password):
        if InvitationSender._instance is not None:
            raise Exception("This class is a singleton!")
        else:
            InvitationSender._instance = self
            self.driver = None
            self.username = username
            self.password = password
            self.emails = set()

    @classmethod
    def get_instance(cls, username, password):
        """Static access method to get the singleton instance."""
        if cls._instance is None:
            cls._instance = InvitationSender(username, password)
        return cls._instance

    def init_webdriver(self):
        """Initialize the Chrome WebDriver with custom paths for ChromeDriver and Chrome binaries."""
        if self.driver is None:  # Initialize only if it hasn't been initialized yet
            options = ChromeOptions()
            options.add_argument("--no-sandbox")
            options.add_argument("--disable-dev-shm-usage")
            options.add_argument("--window-size=1920,1080")
            options.add_argument("--disable-gpu")
            options.add_argument("--disable-extensions")
            options.add_argument("--disable-software-rasterizer")

            user_data_dir = os.path.join(os.getcwd(), "user_data")
            if not os.path.exists(user_data_dir):
                os.makedirs(user_data_dir)
            options.add_argument(f"--user-data-dir={user_data_dir}")

            try:
                print("Installing ChromeDriver")
                self.driver = webdriver.Chrome(
                    service=ChromeService(ChromeDriverManager().install()), options=options
                )
                print("ChromeDriver initialized successfully with custom paths.")
            except Exception as e:
                logging.error(f"Failed to initialize ChromeDriver: {e}")
                sys.exit(1)

    def close(self):
        """Properly close and quit the WebDriver to free resources."""
        if self.driver:
            self.driver.quit()
            self.driver = None  # Set to None so it can be reinitialized if needed
            print("ChromeDriver closed.")

    def add_emails_and_send_invitations(self):
        """Add emails to the form and send invitations."""
        try:
            self.init_webdriver()  # Ensure the WebDriver is initialized
            self.driver.get(
                "https://asu.campuslabs.com/engage/actioncenter/organization/soda/roster/Roster/invite"
            )
            email_textarea = WebDriverWait(self.driver, 20).until(
                EC.visibility_of_element_located(
                    (By.XPATH, '//*[@id="GroupInviteByEmail"]')
                )
            )
            email_textarea.send_keys("\n".join(self.emails))
            print(f'Entered emails: {", ".join(self.emails)}')

            add_email_button = WebDriverWait(self.driver, 20).until(
                EC.element_to_be_clickable(
                    (By.XPATH, '//*[@id="GroupInviteByEmailSubmit"]')
                )
            )
            add_email_button.click()
            print('Clicked "Add Email" button.')

            time.sleep(2)

            send_invitation_button = WebDriverWait(self.driver, 20).until(
                EC.element_to_be_clickable(
                    (By.XPATH, '//*[@id="invitationActions_sendButton"]')
                )
            )
            send_invitation_button.click()
            print('Clicked "Send Invitations" button.')

            time.sleep(5)
            self.emails.clear()

        except Exception as e:
            logging.error(f"Error during the invitation process: {e}")

        finally:
            self.close()  # Ensure the WebDriver is properly closed
