"""The LeetCode daily post and its solve checks, run as jobs. No Flask and no gateway bot here.

A leetcode_daily row per local date and target is claimed before posting, so two workers or a restart never
post twice. Members still to verify come from the database on every run, not from bot memory.
"""

import asyncio
import datetime
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from sqlalchemy.exc import IntegrityError

from core.config import config
from core.integrations.discord import DiscordDirectory, DiscordUnavailable, add_reaction, send_message
from core.integrations.registry import use
from core.log import get_logger
from modules.leetcode import client, service
from modules.leetcode.models import LeetCodeDaily

use("discord", "leetcode")

logger = get_logger("leetcode.daily")

DIFFICULTY_COLORS = {"Easy": 0x00B8A3, "Medium": 0xFFC01E, "Hard": 0xFF375F}
CHECK_MARK = "✅"


def question_embed(question: dict, is_daily: bool = False) -> dict:
    """The Discord embed for a question, as the API's JSON."""
    # Topics give away the intended approach, so they sit behind a spoiler
    tags = " ".join(f"`{t['name']}`" for t in question.get("topicTags", []))
    title_prefix = "\U0001f4c5 Daily Challenge" if is_daily else "\U0001f3b2 Random Problem"
    embed: dict[str, Any] = {
        "title": f"{title_prefix} — {question['title']}",
        "url": f"https://leetcode.com/problems/{question['titleSlug']}/",
        "color": DIFFICULTY_COLORS.get(question.get("difficulty", ""), 0x5865F2),
        "fields": [
            {"name": "Difficulty", "value": question.get("difficulty", "Unknown"), "inline": True},
            {"name": "Acceptance", "value": f"{question.get('acRate', 0):.1f}%", "inline": True},
            {"name": "ID", "value": f"#{question.get('frontendQuestionId', '?')}", "inline": True},
            {"name": "Topics", "value": f"||{tags}||" if tags else "None", "inline": False},
        ],
        "footer": {"text": "Good luck! Link your account with /link to get auto-verified."},
        "timestamp": datetime.datetime.now(datetime.UTC).isoformat(),
    }
    if question.get("paidOnly"):
        embed["description"] = "⚠️ This is a **premium** problem (LeetCode Plus required)."
    return embed


def _int(value: object, name: str) -> int | None:
    if value in (None, ""):
        return None
    try:
        return int(str(value))
    except ValueError:
        logger.warning("%s is not a number: %r", name, value)
        return None


def _zone() -> ZoneInfo:
    try:
        return ZoneInfo(config.TIMEZONE)
    except ZoneInfoNotFoundError:
        logger.warning("Unknown timezone %r, using UTC", config.TIMEZONE)
        return ZoneInfo("UTC")


def _time(value: object, name: str) -> datetime.time:
    try:
        hour, minute = (int(x) for x in str(value).split(":")[:2])
        return datetime.time(hour, minute)
    except ValueError:
        logger.warning("%s %r is not HH:MM, using 09:00", name, value)
        return datetime.time(9, 0)


@dataclass(frozen=True)
class Target:
    """Where one daily post goes."""

    scope: str
    channel_id: int
    role_ping: int | None
    post_time: datetime.time
    guild_id: str | None = None


def targets(db) -> list[Target]:
    """The instance post from LEETCODE_* settings, then each org that turned leetcode on and set a channel."""
    from modules.organizations import service as organizations
    from modules.organizations.models import Organization

    found = []
    channel = _int(config.LEETCODE_CHANNEL_ID, "LEETCODE_CHANNEL_ID")
    if channel is not None:
        found.append(
            Target(
                "instance",
                channel,
                _int(config.LEETCODE_ROLE_PING, "LEETCODE_ROLE_PING"),
                _time(config.LEETCODE_DAILY_TIME, "LEETCODE_DAILY_TIME"),
            )
        )
    for org in db.query(Organization).filter_by(is_active=True).order_by(Organization.id):
        settings = (org.config or {}).get("leetcode") or {}
        channel = _int(settings.get("channel_id"), f"org {org.id} leetcode channel_id")
        if channel is None or not organizations.module_enabled(org, "leetcode"):
            continue
        found.append(
            Target(
                f"org:{org.id}",
                channel,
                _int(settings.get("role_ping"), f"org {org.id} leetcode role_ping"),
                _time(settings.get("daily_time") or "09:00", f"org {org.id} leetcode daily_time"),
                str(org.guild_id),
            )
        )
    return found


def post_daily(
    db,
    now: datetime.datetime | None = None,
    fetch: Callable[[], dict] | None = None,
    send: Callable[..., dict] = send_message,
    react: Callable[..., None] = add_reaction,
) -> dict[str, dict]:
    """Post today's question once per target, at or after its time in TIMEZONE. Commits. Returns scope to result."""
    local = (now or datetime.datetime.now(datetime.UTC)).astimezone(_zone())
    results: dict[str, dict] = {}
    question: dict | None = None
    for target in targets(db):
        if local.time() < target.post_time:
            results[target.scope] = {"posted": False, "reason": "not yet"}
            continue
        if db.get(LeetCodeDaily, (local.date(), target.scope)) is not None:
            results[target.scope] = {"posted": False, "reason": "already posted"}
            continue
        if question is None:
            question = fetch() if fetch else asyncio.run(client.fetch_daily_question())
        try:
            results[target.scope] = _post(db, target, local.date(), question, send, react)
        except DiscordUnavailable:
            logger.warning("Could not post the daily LeetCode for %s", target.scope, exc_info=True)
            results[target.scope] = {"posted": False, "reason": "discord unavailable"}
    return results


def _post(db, target: Target, today: datetime.date, question: dict, send, react) -> dict:
    db.add(
        LeetCodeDaily(
            post_date=today, scope=target.scope, title_slug=question["titleSlug"], channel_id=str(target.channel_id)
        )
    )
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        return {"posted": False, "reason": "already posted"}

    payload = {
        "content": f"<@&{target.role_ping}>" if target.role_ping else None,
        "embeds": [question_embed(question, is_daily=True)],
    }
    try:
        message = send(config.BOT_TOKEN, target.channel_id, payload)
    except DiscordUnavailable:
        # Give the day back so the next run tries again
        db.query(LeetCodeDaily).filter_by(post_date=today, scope=target.scope).delete()
        db.commit()
        raise
    row = db.get(LeetCodeDaily, (today, target.scope))
    row.message_id = str(message["id"])
    db.commit()
    try:
        react(config.BOT_TOKEN, target.channel_id, message["id"], CHECK_MARK)
    except DiscordUnavailable:
        logger.warning("Could not react to the daily post", exc_info=True)
    logger.info("Posted daily LeetCode %s for %s", question["titleSlug"], target.scope)
    return {"posted": True, "slug": question["titleSlug"]}


def _solved_on(submissions: list[dict], slugs: set[str], day: datetime.date, zone: ZoneInfo) -> str | None:
    for sub in submissions:
        if sub.get("titleSlug") not in slugs:
            continue
        try:
            ts = int(sub.get("timestamp", ""))
        except (TypeError, ValueError):
            continue
        if datetime.datetime.fromtimestamp(ts, tz=zone).date() == day:
            return str(sub["titleSlug"])
    return None


def _member_check() -> Callable[[str, str], bool]:
    directory = DiscordDirectory(config.BOT_TOKEN)
    return lambda guild_id, discord_id: directory.check_user_membership(discord_id, guild_id)


def verify(
    db,
    now: datetime.datetime | None = None,
    submissions: Callable[[str], list[dict]] | None = None,
    send: Callable[..., dict] = send_message,
    is_member: Callable[[str, str], bool] | None = None,
) -> dict:
    """Check today's linked members who have not solved yet, record solves, reply under each post. Commits.

    The instance post announces every solve. An org's post announces solves of members of its server.
    """
    zone = _zone()
    today = (now or datetime.datetime.now(datetime.UTC)).astimezone(zone).date()
    posts = [p for p in db.query(LeetCodeDaily).filter_by(post_date=today) if p.message_id is not None]
    if not posts:
        return {"checked": 0, "verified": 0}
    slugs = {str(p.title_slug) for p in posts}
    if is_member is None and any(str(p.scope).startswith("org:") for p in posts):
        is_member = _member_check()
    pending = service.unsolved_links(db, today)
    verified = 0
    for discord_id, username in pending.items():
        try:
            found = submissions(username) if submissions else asyncio.run(client.fetch_recent_ac_submissions(username))
        except RuntimeError:
            logger.warning("Could not read submissions of %s", username, exc_info=True)
            continue
        slug = _solved_on(found, slugs, today, zone)
        if slug is None:
            continue
        service.record_solve(db, discord_id, slug, today)
        verified += 1
        for post in posts:
            if not _announces(db, post, discord_id, is_member):
                continue
            try:
                send(
                    config.BOT_TOKEN,
                    post.channel_id,
                    {
                        "content": f"{CHECK_MARK} <@{discord_id}> solved today's challenge as **{username}**!",
                        "message_reference": {"message_id": post.message_id, "fail_if_not_exists": False},
                        "allowed_mentions": {"users": [discord_id]},
                    },
                )
            except DiscordUnavailable:
                logger.warning("Could not announce the solve of %s", discord_id, exc_info=True)
    return {"checked": len(pending), "verified": verified}


def _announces(db, post: LeetCodeDaily, discord_id: str, is_member: Callable[[str, str], bool] | None) -> bool:
    """Whether a solve by discord_id is announced under this post."""
    scope = str(post.scope)
    if not scope.startswith("org:"):
        return True
    from modules.organizations.models import Organization

    org = db.get(Organization, int(scope.removeprefix("org:")))
    if org is None or is_member is None:
        return False
    try:
        return is_member(str(org.guild_id), discord_id)
    except DiscordUnavailable:
        logger.warning("Could not check membership of %s in %s", discord_id, org.guild_id, exc_info=True)
        return False
