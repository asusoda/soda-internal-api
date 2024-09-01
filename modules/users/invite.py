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
        print(username, password)
        self.init_webdriver()
        self.emails = set()
        print("Chrome Initialization Successful")  # debugging

    def init_webdriver(self):
        """Initialize the Chrome WebDriver with custom paths for ChromeDriver and Chrome binaries."""
        options = ChromeOptions()
        # options.add_argument('--headless')  # Run in headless mode
        options.add_argument("--no-sandbox")  # Bypass OS security model
        options.add_argument(
            "--disable-dev-shm-usage"
        )  # Overcome limited resource problems
        options.add_argument(
            "--window-size=1920,1080"
        )  # Set a large enough window size
        options.add_argument("--disable-gpu")  # Applicable to older versions of Chrome
        options.add_argument(
            "--disable-extensions"
        )  # Disable any extensions that might cause conflicts
        options.add_argument(
            "--disable-software-rasterizer"
        )  # Helps if you have rendering issues

        # Custom paths for ChromeDriver and Chrome binaries updating path to chrom driver in the root directory of the project
        # chrome_driver_path = os.getcwd() + '/chromedriver-linux64/chromedriver'
        # chrome_binary_path = os.getcwd() + '/chrome-linux64/chromelinux64/chrome'
        # options.binary_location = chrome_binary_path

        # print(f"ChromeDriver Path: {chrome_driver_path}")
        # print(f"Chrome Binary Path: {chrome_binary_path}" + '\n')

        try:
            print("Installing ChromeDriver")
            self.driver = webdriver.Chrome(
                service=ChromeService(ChromeDriverManager().install()), options=options
            )
            print(self.driver)  # debugging
            # self.driver = webdriver.Chrome(executable_path=chrome_driver_path, options=options)
            print("ChromeDriver initialized successfully with custom paths.")
        except Exception as e:
            logging.error(f"Failed to initialize ChromeDriver: {e}")
            sys.exit(1)

    def login(self, retries=30):
        """Log in to the site, handling Duo 2FA if necessary, with retries on failure."""
        print("logging in")  # debugging

        for attempt in range(retries):
            print(attempt)
            try:
                invitation_url = "https://asu.campuslabs.com/engage/actioncenter/organization/soda/roster/Roster/invite"
                self.driver.get(invitation_url)

                # Attempt to find the email text box to check if already logged in
                email_textarea = WebDriverWait(self.driver, 10).until(
                    EC.visibility_of_element_located(
                        (By.XPATH, '//*[@id="GroupInviteByEmail"]')
                    )
                )
                return True

            except:
                pass

            try:
                WebDriverWait(self.driver, 20).until(
                    EC.visibility_of_element_located((By.ID, "username"))
                )
                self.driver.find_element(By.ID, "username").send_keys(self.username)
                self.driver.find_element(By.ID, "password").send_keys(self.password)
                self.driver.find_element(By.NAME, "submit").click()

                # # Handle Duo 2FA
                # WebDriverWait(self.driver, 20).until(
                #     EC.frame_to_be_available_and_switch_to_it((By.XPATH, '//iframe[@id="duo_iframe"]')))
                # WebDriverWait(self.driver, 20).until(
                #     EC.element_to_be_clickable((By.XPATH, '//*[@id="login-form"]/div[2]/div/label/input'))).click()
                # WebDriverWait(self.driver, 20).until(
                #     EC.element_to_be_clickable((By.XPATH, '//button[normalize-space()="Send Me a Push"]'))).click()

                time.sleep(10)

                self.driver.switch_to.default_content()
                yes_button = WebDriverWait(self.driver, 60).until(
                    EC.element_to_be_clickable(
                        (
                            By.XPATH,
                            '//button[contains(text(), "Yes, this is my device")]',
                        )
                    )
                )

                yes_button.click()
                print('Clicked "Yes, this is my device" button.')

                # Wait for email text box visibility
                WebDriverWait(self.driver, 60).until(
                    EC.visibility_of_element_located(
                        (By.XPATH, '//*[@id="GroupInviteByEmail"]')
                    )
                )
                return True

            except Exception as e:
                logging.error(f"Failed to log in: {e}")

            if attempt < retries - 1:
                print(f"Retrying login ({attempt + 1}/{retries})...")
                time.sleep(15)  # Wait a moment before retrying
            else:
                logging.error("Max retries reached. Login failed.")
                return False

    def add_emails_and_send_invitations(self):
        """Add emails to the form and send invitations."""

        try:
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
