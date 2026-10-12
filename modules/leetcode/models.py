from datetime import date, datetime

from sqlalchemy import Date, DateTime, Integer, String, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column

from core.db import Base


class LeetCodeLink(Base):
    __tablename__ = "leetcode_link"

    discord_id: Mapped[str] = mapped_column(String, primary_key=True)
    leetcode_username: Mapped[str] = mapped_column(String, nullable=False)
    created_at: Mapped[datetime | None] = mapped_column(DateTime, server_default=func.now())


class LeetCodeSolve(Base):
    __tablename__ = "leetcode_solve"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    discord_id: Mapped[str] = mapped_column(String, nullable=False, index=True)
    title_slug: Mapped[str] = mapped_column(String, nullable=False)
    solved_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    created_at: Mapped[datetime | None] = mapped_column(DateTime, server_default=func.now())

    __table_args__ = (UniqueConstraint("discord_id", "solved_date", name="uq_solve_user_date"),)


class LeetCodeDaily(Base):
    """One row per local date and target: each daily post happens once, whichever process gets there first.

    scope is "instance" for the post configured by LEETCODE_CHANNEL_ID, or "org:<id>" for an org's own post.
    """

    __tablename__ = "leetcode_daily"

    post_date: Mapped[date] = mapped_column(Date, primary_key=True)
    scope: Mapped[str] = mapped_column(String, primary_key=True, server_default="instance")
    title_slug: Mapped[str] = mapped_column(String, nullable=False)
    channel_id: Mapped[str] = mapped_column(String, nullable=False)
    message_id: Mapped[str | None] = mapped_column(String, nullable=True)
    posted_at: Mapped[datetime | None] = mapped_column(DateTime, server_default=func.now())
