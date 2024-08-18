from flask import Flask
from flask_cors import CORS
from shared import app, config
from modules.public.api import public_blueprint
from modules.points.api import points_blueprint
from modules.users.api import InvitationSender, create_users_blueprint  # Import the necessary components
from modules.utils.db import DBConnect

# Initialize CORS with explicit origins allowed
CORS(app, resources={r"/*": {"origins": "http://127.0.0.1:3000/", }})

# Initialize and create tables
db_connect = DBConnect()
db_connect.check_and_create_tables()

# Prompt for credentials before initializing InvitationSender
username = input("Enter your ASU ID: ")
password = input("Enter your ASU password: ")

# Instantiate the InvitationSender class with credentials
invitation_sender = InvitationSender(username, password)

# Register Blueprints
app.register_blueprint(public_blueprint, url_prefix="/")
app.register_blueprint(points_blueprint, url_prefix="/points")
app.register_blueprint(create_users_blueprint(invitation_sender), url_prefix="/users")

if __name__ == "__main__":
    # Login once when the application starts
    if invitation_sender.login():
        print("Logged in successfully. Ready to send invitations.")

    if config.PROD:
        app.run(debug=False, host="0.0.0.0", port=8080)
    else:
        app.run(debug=True)

    # The invitation_sender will remain active as long as the application runs
    # Invitations will be sent whenever 10 emails are added via the /invite endpoint.
