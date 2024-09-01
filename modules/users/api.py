from selenium import webdriver
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
from modules.auth.decoraters import auth_required
from modules.users.invite import InvitationSender
from shared import config

# Flask Blueprint for users
users_blueprint = Blueprint("users", __name__, template_folder=None, static_folder=None)


@users_blueprint.route("/", methods=["GET"])
def users_index():
    return jsonify({"message": "users api"}), 200


@users_blueprint.route("/invite", methods=["POST"])
def invite_users():
    email = request.args.get("email")
    if email:
        pattern = r"^[a-zA-Z0-9._%+-]+@asu\.edu$"
        try:
            invitation_sender = InvitationSender(config.USERNAME, config.PASSWORD)
            if re.match(pattern, email):
                invitation_sender.emails.add(email)
                invitation_sender.add_emails_and_send_invitations()
                return jsonify({"message": "Email added"}), 200
            else:
                return jsonify({"error": "Invalid email format"}), 400

        except Exception as e:
            logging.error(f"An error occurred while inviting users: {e}")
            return jsonify({"error": "Failed to send invitation"}), 500

        finally:
            # Ensure the WebDriver is closed after processing the request
            invitation_sender.close()
    else:
        return jsonify({"error": "No email provided"}), 400
