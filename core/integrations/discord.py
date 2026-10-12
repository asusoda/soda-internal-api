"""Discord over the REST API with the bot token, without the gateway bot.

DiscordDirectory reads guilds, roles and members, cached for a short time. send_message and
add_reaction post to channels.
"""

import os
import threading
import time
from urllib.parse import quote, urlencode

import requests
from sqlalchemy import text

from core.integrations.registry import Integration, IntegrationError, register
from core.log import get_logger

logger = get_logger("discord_directory")

API = "https://discord.com/api/v10"


MAX_LISTED_MEMBERS = 10_000


class DiscordUnavailable(Exception):
    """Discord could not be reached or refused the bot token."""


def _member_summary(member: dict) -> dict:
    """The id, display name, username, avatar URL and role ids of a guild member object."""
    user = member.get("user") or {}
    user_id = str(user.get("id", ""))
    avatar = user.get("avatar")
    return {
        "id": user_id,
        "name": member.get("nick") or user.get("global_name") or user.get("username") or user_id,
        "username": user.get("username"),
        "avatar": f"https://cdn.discordapp.com/avatars/{user_id}/{avatar}.png?size=64" if avatar else None,
        "roles": [str(role) for role in member.get("roles") or []],
        "bot": bool(user.get("bot")),
    }


class DiscordDirectory:
    def __init__(self, token: str | None, ttl_seconds: int = 60, http=None):
        self.token = token
        self.ttl_seconds = ttl_seconds
        self.http = http or requests.Session()
        self._cache: dict[str, tuple[float, object]] = {}
        self._lock = threading.Lock()

    def is_ready(self) -> bool:
        return bool(self.token)

    def _get(self, path: str, ttl: int | None = None):
        """GET a Discord API path. Returns the JSON body, or None for 404. Cached for ttl seconds."""
        now = time.monotonic()
        with self._lock:
            cached = self._cache.get(path)
            if cached and cached[0] > now:
                return cached[1]
        if not self.token:
            raise DiscordUnavailable("BOT_TOKEN is not set")
        headers = {"Authorization": f"Bot {self.token}"}
        try:
            response = self.http.get(f"{API}{path}", headers=headers, timeout=10)
            if response.status_code == 429:
                # One retry after the wait Discord asks for, if it is short
                retry_after = float(response.json().get("retry_after", 1))
                if retry_after > 5:
                    raise DiscordUnavailable(f"rate limited for {retry_after}s")
                time.sleep(retry_after)
                response = self.http.get(f"{API}{path}", headers=headers, timeout=10)
        except requests.RequestException as e:
            raise DiscordUnavailable(str(e)) from e
        if response.status_code == 404:
            body = None
        elif response.status_code == 200:
            body = response.json()
        else:
            raise DiscordUnavailable(f"GET {path} returned {response.status_code}")
        with self._lock:
            self._cache[path] = (now + (ttl if ttl is not None else self.ttl_seconds), body)
        return body

    def clear_cache(self) -> None:
        with self._lock:
            self._cache.clear()

    def identity(self) -> dict:
        """The Discord app that owns the token: {app_id, app_name, bot_name}."""
        app = self._get("/oauth2/applications/@me", ttl=3600) or {}
        bot = app.get("bot") or {}
        return {"app_id": str(app.get("id", "")), "app_name": app.get("name"), "bot_name": bot.get("username")}

    # Guilds and roles

    def list_guilds(self) -> list[dict]:
        """Guilds the bot is in: [{id, name, icon_url}]."""
        guilds = self._get("/users/@me/guilds", ttl=300) or []
        return [
            {
                "id": str(g["id"]),
                "name": g["name"],
                "icon_url": f"https://cdn.discordapp.com/icons/{g['id']}/{g['icon']}.png" if g.get("icon") else None,
            }
            for g in guilds
        ]

    def get_guild(self, guild_id) -> dict | None:
        return next((g for g in self.list_guilds() if g["id"] == str(guild_id)), None)

    def get_guild_roles(self, guild_id) -> list[dict]:
        """Roles of a guild: [{id, name, color, position, permissions, managed}]."""
        roles = self._get(f"/guilds/{int(guild_id)}/roles", ttl=300) or []
        return [
            {
                "id": str(r["id"]),
                "name": r["name"],
                "color": f"#{int(r.get('color', 0)):06x}",
                "position": r.get("position", 0),
                "permissions": int(r.get("permissions", 0)),
                "managed": bool(r.get("managed")),
            }
            for r in roles
        ]

    # Members

    def get_member(self, guild_id, user_id) -> dict | None:
        """The guild member, or None if the user is not in the guild."""
        return self._get(f"/guilds/{int(guild_id)}/members/{int(user_id)}")

    def get_display_name(self, guild_id, user_id) -> str | None:
        member = self.get_member(guild_id, user_id)
        if not member:
            return None
        user = member.get("user", {})
        return member.get("nick") or user.get("global_name") or user.get("username")

    def search_members(self, guild_id, query: str, limit: int = 10) -> list[dict]:
        """Members whose username or server nickname starts with query, as id, name, username and avatar."""
        path = f"/guilds/{int(guild_id)}/members/search?{urlencode({'query': query, 'limit': int(limit)})}"
        return [_member_summary(member) for member in self._get(path, ttl=30) or []]

    def list_members(self, guild_id, max_members: int = MAX_LISTED_MEMBERS) -> list[dict]:
        """Every guild member, up to max_members, in the search_members shape. Needs the Server Members intent."""
        members: list[dict] = []
        after = "0"
        while len(members) < max_members:
            path = f"/guilds/{int(guild_id)}/members?{urlencode({'limit': 1000, 'after': after})}"
            page = self._get(path, ttl=120) or []
            members += [_member_summary(member) for member in page]
            if len(page) < 1000:
                break
            after = members[-1]["id"]
        return members[:max_members]

    def check_user_membership(self, user_id, guild_id) -> bool:
        return self.get_member(guild_id, user_id) is not None

    def check_user_officer_status(self, user_id, guild_id, role_id) -> bool:
        member = self.get_member(guild_id, user_id)
        return bool(member) and str(role_id) in {str(r) for r in member.get("roles", [])}

    def officer_guilds(self, user_id, org_roles: list[tuple[str, str | None]]) -> list[str]:
        """Guild ids from org_roles, (guild id, officer role id) pairs, where the user holds the role."""
        return [
            guild_id
            for guild_id, role_id in org_roles
            if role_id and self.check_user_officer_status(user_id, guild_id, role_id)
        ]


def _call(method: str, path: str, token: str | None, payload: dict | None = None) -> dict:
    if not token:
        raise DiscordUnavailable("BOT_TOKEN is not set")
    try:
        response = requests.request(
            method, f"{API}{path}", json=payload, headers={"Authorization": f"Bot {token}"}, timeout=10
        )
    except requests.RequestException as e:
        raise DiscordUnavailable(str(e)) from e
    if response.status_code >= 300:
        raise DiscordUnavailable(f"{method} {path} returned {response.status_code}")
    return response.json() if response.content else {}


def send_message(token: str | None, channel_id: int | str, payload: dict) -> dict:
    """Post a message (content, embeds, message_reference) to a channel. Returns the message."""
    return _call("POST", f"/channels/{int(channel_id)}/messages", token, payload)


def add_reaction(token: str | None, channel_id: int | str, message_id: int | str, emoji: str) -> None:
    _call("PUT", f"/channels/{int(channel_id)}/messages/{int(message_id)}/reactions/{quote(emoji)}/@me", token)


def _guild_id(db, org_id: int) -> str | None:
    row = db.execute(text("SELECT guild_id FROM organizations WHERE id = :id"), {"id": org_id}).first()
    return str(row[0]) if row else None


def _test(db, org_id: int) -> str:
    directory = DiscordDirectory(os.environ.get("BOT_TOKEN"))
    try:
        bot = directory.identity().get("bot_name") or "The bot"
        guild_id = _guild_id(db, org_id)
        guild = directory.get_guild(guild_id) if guild_id else None
    except DiscordUnavailable as e:
        raise IntegrationError(f"Discord refused the bot token or could not be reached: {e}") from e
    if not guild:
        raise IntegrationError(
            f"{bot} is not in this org's Discord server. Invite it with the bot and applications.commands scopes"
        )
    return f"Connected as {bot}, in {guild.get('name', 'the server')}."


register(
    Integration(
        key="discord",
        title="Discord",
        description="Connect the org's Discord server. One Discord app serves every org; the deployment sets it in Doppler.",
        docs="modules/discord-bot",
        deployment=lambda: bool(os.environ.get("BOT_TOKEN")),
        test=_test,
    )
)
