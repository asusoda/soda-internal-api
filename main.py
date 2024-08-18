from flask import Flask
from flask_cors import CORS
from shared import app, config, invitation_sender
from modules.public.api import public_blueprint
from modules.points.api import points_blueprint
from modules.users.api import users_blueprint
from modules.utils.db import DBConnect
from modules.auth.api import auth_blueprint

# Initialize CORS with explicit origins allowed
CORS(app, resources={r"/*": {"origins": "http://127.0.0.1:3000/", }})

# Initialize and create tables
db_connect = DBConnect()
db_connect.check_and_create_tables()

# Register Blueprints
app.register_blueprint(public_blueprint, url_prefix="/")
app.register_blueprint(points_blueprint, url_prefix="/points")
app.register_blueprint(users_blueprint, url_prefix="/users")
app.register_blueprint(auth_blueprint, url_prefix="/auth")

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
