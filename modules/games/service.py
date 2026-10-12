"""Games: the Jeopardy JSON format check, the stored games and reading a game from the data folder. No Flask here."""

import json
import os
import re

from sqlalchemy.orm import Session

from core.errors import ServiceError
from modules.games import models
from modules.organizations import service as organizations
from modules.organizations.models import Organization

SAFE_FILENAME = re.compile(r"^[\w\-]+$")
GAME_KEYS = {"name", "description", "players", "categories", "per_category", "teams", "uuid"}
QUESTION_KEYS = {"question", "answer", "value", "uuid"}


class GameError(ServiceError):
    pass


def enabled_for_guilds(session, guild_ids) -> bool:
    """Whether an org on one of these Discord servers has the games module on."""
    orgs = session.query(Organization).filter(Organization.guild_id.in_([str(g) for g in guild_ids])).all()
    return any(organizations.module_enabled(org, "games") for org in orgs)


def is_valid_game(data: dict) -> bool:
    """Whether data has a game object with every game key and questions with every question key."""
    if "game" not in data or "questions" not in data:
        return False
    if not all(key in data["game"] for key in GAME_KEYS):
        return False
    for _category, questions in data["questions"].items():
        for question in questions:
            if not all(key in question for key in QUESTION_KEYS):
                return False
    return True


def list_games(session: Session) -> list[dict]:
    """The game JSON of each stored game, in the order the games were added."""
    rows = session.query(models.JeopardyGame).order_by(models.JeopardyGame.id).all()
    return [row.data for row in rows if isinstance(row.data, dict)]


def get_game(session: Session, name: str) -> dict:
    """The game JSON of the stored game with this name. Raises GameError (404) when there is no such game."""
    row = session.query(models.JeopardyGame).filter(models.JeopardyGame.name == name).first()
    if row is None or not isinstance(row.data, dict):
        raise GameError("Game not found", 404)
    return row.data


def save_game(session: Session, data: dict) -> models.JeopardyGame:
    """Store a game JSON. A stored game with the same data["game"]["name"] gets the new data."""
    if not is_valid_game(data):
        raise GameError("Invalid game JSON format")
    name = data["game"]["name"]
    row = session.query(models.JeopardyGame).filter(models.JeopardyGame.name == name).first()
    if row is None:
        row = models.JeopardyGame(name=name, data=data)
        session.add(row)
    else:
        row.data = data
    session.commit()
    return row


def read_game_file(file_name: object) -> dict:
    """The JSON of ./data/<file_name>.json. The name holds only letters, digits, - and _."""
    if not file_name or not isinstance(file_name, str):
        raise GameError("Missing or invalid file_name parameter")
    if not SAFE_FILENAME.match(file_name):
        raise GameError("Invalid file name")
    base_dir = os.path.abspath("./data")
    requested_path = os.path.abspath(os.path.join(base_dir, f"{file_name}.json"))
    if not requested_path.startswith(base_dir + os.sep):
        raise GameError("Attempted path traversal or invalid path")
    with open(requested_path) as f:
        return json.load(f)
