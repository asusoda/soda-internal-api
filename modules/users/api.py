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
from shared import invitation_sender
from modules.auth.decoraters import auth_required

# Flask Blueprint for users
users_blueprint = Blueprint("users", __name__, template_folder=None, static_folder=None)

@users_blueprint.route("/", methods=["GET"])
def users_index():
    return jsonify({"message": "users api"}), 200

@users_blueprint.route("/invite", methods=["POST"])
def invite_users():
    email = request.args.get("email")
    if email:
        pattern = r'^[a-zA-Z0-9._%+-]+@asu\.edu$'
        if re.match(pattern, email):
            invitation_sender.emails.add(email)
            invitation_sender.add_emails_and_send_invitations()
            return jsonify({"message": "Email added"}), 200
        else:
            return jsonify({"error": "Invalid email format"}), 400
    else:
        return jsonify({"error": "No email provided"}), 400
