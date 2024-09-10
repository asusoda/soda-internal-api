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
from modules.auth.decoraters import auth_required, error_handler
from modules.points.models import User
from shared import config, db_connect

# Flask Blueprint for users
users_blueprint = Blueprint("users", __name__, template_folder=None, static_folder=None)

@users_blueprint.route("/", methods=["GET"])
def users_index():
    return jsonify({"message": "users api"}), 200


@users_blueprint.route("/create", methods=["POST"])
def create_user():
    data = request.get_json()  # Get JSON data from the request body
    name = data.get("name")
    email = data.get("email")
    asu_id = data.get("asu_id")
    standing = data.get("standing")
    major = data.get("major")

    print(f"Creating {name}, {email}, {standing}, {major}, {asu_id}")
    print(f"Type: {type(name)}, {type(email)}, {type(standing)}, {type(major)}, {type(asu_id)}")
    # Create user in the database
    def add_user_to_db(db_connect, asu_id, name, email, year, major):
        db = next(db_connect.get_db())
        try:
            user = User(asu_id=asu_id, name=name, email=email, academic_standing=year, major=major)
            db_user = db_connect.create_user(db, user)
            print(
                f"Successfully added user: {db_user.name} ({db_user.email}) with ASU ID {db_user.asu_id}"
            )
        except Exception as e:
            print(f"Error adding user: {e}")
        
        finally:
            db.close()
            print("Database connection closed")

    add_user_to_db(db_connect, asu_id, name, email, standing, major)
    return jsonify({"message": "User created successfully"}), 201

