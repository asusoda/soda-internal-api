from shared import app
from modules.public.api import public_blueprint
from modules.points.api import points_blueprint
from modules.utils.db import DBConnect

# Initialize and create tables
db_connect = DBConnect()
db_connect.create_tables()

app.register_blueprint(public_blueprint, url_prefix="/")
app.register_blueprint(points_blueprint, url_prefix="/points-system")

if __name__ == "__main__":
    app.run(debug=True)
