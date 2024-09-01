from flask import Flask
from flask_cors import CORS
from shared import app
from modules.public.api import public_blueprint
from modules.points.api import points_blueprint
from modules.users.api import users_blueprint
from modules.users.invite import InvitationSender
from modules.utils.db import DBConnect

# from modules.auth.api import auth_blueprint

# Initialize CORS with explicit origins allowed
CORS(
    app,
    resources={
        r"/*": {
            "origins": "http://127.0.0.1:3000/",
        }
    },
)

# Initialize and create tables
db_connect = DBConnect()
db_connect.check_and_create_tables()

# Register Blueprints
app.register_blueprint(public_blueprint, url_prefix="/")
app.register_blueprint(points_blueprint, url_prefix="/points")
app.register_blueprint(users_blueprint, url_prefix="/users")
# app.register_blueprint(auth_blueprint, url_prefix="/auth")

if __name__ == "__main__":
    app.run(debug=True)
