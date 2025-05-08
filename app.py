from modules.utils.session import SQLAlchemySessionInterface
from modules.auth.models import Session

def create_app():
    app = Flask(__name__)
    app.config.from_object('config.Config')

    # Initialize extensions
    db.init_app(app)
    migrate.init_app(app, db)
    cors.init_app(app)
    login_manager.init_app(app)

    # Configure session to use SQLAlchemy
    app.session_interface = SQLAlchemySessionInterface(db, Session, use_signer=True)

    # Register blueprints
    # ... existing code ... 