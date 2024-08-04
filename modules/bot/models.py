from sqlalchemy.dialects.postgresql import JSONB
import uuid
from datetime import datetime

class JeopardyGame(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    description = db.Column(db.String(500), nullable=False)
    players = db.Column(db.Integer, nullable=False)
    categories = db.Column(JSONB, nullable=False)  # Store as JSON
    per_category = db.Column(db.Integer, nullable=False)
    teams = db.Column(JSONB, nullable=False)  # Store as JSON
    uuid = db.Column(db.String(36), default=str(uuid.uuid4()), unique=True)
    questions = db.relationship('JeopardyQuestion', backref='game', lazy=True)

class JeopardyQuestion(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    question = db.Column(db.String(500), nullable=False)
    answer = db.Column(db.String(500), nullable=False)
    value = db.Column(db.Integer, nullable=False)
    uuid = db.Column(db.String(36), default=str(uuid.uuid4()), unique=True)
    game_id = db.Column(db.Integer, db.ForeignKey('jeopardy_game.id'), nullable=False)

class ActiveGame(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    game_id = db.Column(db.Integer, db.ForeignKey('jeopardy_game.id'), nullable=False)
    date = db.Column(db.Date, nullable=False)
    time = db.Column(db.Time, nullable=False)
    state = db.Column(JSONB, nullable=False)  # Store game state as JSON
    is_active = db.Column(db.Boolean, default=True)
    start_time = db.Column(db.DateTime, default=datetime.utcnow)
    end_time = db.Column(db.DateTime)
