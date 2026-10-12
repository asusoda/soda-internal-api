from typing import Any

from sqlalchemy import JSON, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from core.db import Base


class JeopardyGame(Base):
    __tablename__ = "jeopardy_game"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str | None] = mapped_column(String)
    data: Mapped[Any | None] = mapped_column(JSON)


class ActiveGame(Base):
    __tablename__ = "active_game"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str | None] = mapped_column(String)
    game_data: Mapped[Any | None] = mapped_column(JSON)
    helper_data: Mapped[Any | None] = mapped_column(JSON)
