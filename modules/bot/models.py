from shared import base
from sqlalchemy import Column, Integer, String, ForeignKey, Boolean, JSON


class JeopardyGame(base):
    __tablename__ = "jeopardy_game"

    id = Column(Integer, primary_key=True)
    name = Column(String)
    data = Column(JSON)


class ActiveGame(base):
    __tablename__ = "active_game"

    id = Column(Integer, primary_key=True)
    name = Column(String)
    game_data = Column(JSON)
    helper_data = Column(JSON)
