from flask import Flask
from flask_cors import CORS
from shared import app
from modules.public.api import public_blueprint
from modules.points.api import points_blueprint
from modules.utils.db import DBConnect
from modules.users.user_reader import check_gForm_for_distinguished_members as check_gForm

# Initialize CORS with explicit origins allowed
CORS(app, resources={r"/*": {"origins": "http://127.0.0.1:3000/"}})

# Initialize and create tables
db_connect = DBConnect()
db_connect.check_and_create_tables()

# Check Google Form for distinguished members
check_gForm()

app.register_blueprint(public_blueprint, url_prefix="/")
app.register_blueprint(points_blueprint, url_prefix="/points-system")

if __name__ == "__main__":
    app.run(debug=True)
