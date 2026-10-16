"""Jeopardy in Discord: the server of the game, the start flow, teams and the announcement."""

from types import SimpleNamespace
from typing import Any, cast

import discord


def test_announcement_location_names_the_org_or_the_server(app):
    from modules.games.cog import server_name

    assert server_name(cast(discord.Guild, SimpleNamespace(id=1002, name="Guild Name"))) == "AI Society"
    assert server_name(cast(discord.Guild, SimpleNamespace(id=9999, name="Guild Name"))) == "Guild Name"


GAME = {
    "game": {
        "name": "Trivia Night",
        "description": "Questions",
        "players": 4,
        "categories": ["Code"],
        "per_category": 1,
        "teams": ["Red", "Blue"],
        "uuid": "game-1",
    },
    "questions": {"Code": [{"question": "2+2?", "answer": "4", "value": 100, "uuid": "q-1"}]},
}


class FakeRole:
    def __init__(self, name):
        self.name = name


class FakeChannel:
    def __init__(self, name):
        self.name = name
        self.sent = []

    async def edit(self, **kwargs):
        return None

    async def send(self, **kwargs):
        message = FakeMessage()
        self.sent.append(kwargs)
        return message


class FakeMessage:
    async def add_reaction(self, emoji):
        return None

    async def edit(self, **kwargs):
        return None


class FakeGuild:
    def __init__(self, guild_id, name="Guild"):
        self.id, self.name = guild_id, name
        self.default_role = FakeRole("@everyone")
        self.created: list[str] = []

    async def create_category(self, name):
        self.created.append(name)
        return FakeChannel(name)

    async def create_stage_channel(self, name, **kwargs):
        self.created.append(name)
        return FakeChannel(name)

    async def create_role(self, name):
        self.created.append(name)
        return FakeRole(name)

    async def create_voice_channel(self, name, **kwargs):
        self.created.append(name)
        return FakeChannel(name)

    async def create_text_channel(self, name, **kwargs):
        self.created.append(name)
        return FakeChannel(name)


class FakeBot:
    def __init__(self, *guilds):
        self.guilds = list(guilds)
        self.executed = []

    def execute(self, *args, **kwargs):
        self.executed.append(args)


def _player(n):
    return SimpleNamespace(id=n, display_name=f"p{n}")


def test_balance_teams_puts_each_player_in_one_team():
    from modules.games.cog import GameCog

    cog = GameCog(cast(Any, FakeBot()))
    cog.set_game(GAME, None, None)
    assert cog.game is not None
    for n in range(5):
        cog.add_member(cast(discord.Member, _player(n)))
    cog.balance_teams()
    placed = [member.id for team in cog.game.teams for member in team.members]
    assert sorted(placed) == [0, 1, 2, 3, 4]
    assert sorted(len(team.members) for team in cog.game.teams) == [2, 3]


def test_game_is_set_up_in_the_given_server_and_starts(app):
    import asyncio

    from modules.games.cog import GameCog

    first, soda = FakeGuild(1002), FakeGuild(1001)
    cog = GameCog(cast(Any, FakeBot(first, soda)))
    cog.set_game(GAME, "Friday", "6 PM")
    assert asyncio.run(cog.setup_game(cast(discord.Guild, soda)))
    assert first.created == [] and "Jeopardy" in soda.created
    for n in range(3):
        cog.add_member(cast(discord.Member, _player(n)))
    assert asyncio.run(cog.start_game())
    assert "scoreboard" in soda.created
    assert cog.game is not None and cog.game.is_started
    assert not asyncio.run(cog.start_game())


def test_set_active_game_sets_up_in_the_officers_server(client, officer_headers, monkeypatch):
    from core.db import db_connect
    from modules.games import api, service
    from modules.games.cog import GameCog

    db = db_connect.SessionLocal()
    try:
        service.save_game(db, GAME)
    finally:
        db.close()
    other, soda = FakeGuild(1002), FakeGuild(1001)
    bot = FakeBot(other, soda)
    cog = GameCog(cast(Any, bot))
    monkeypatch.setattr(api, "_ready_bot", lambda: bot)
    monkeypatch.setattr(api, "_game_cog", lambda bot: cog)

    response = client.post("/api/bot/setactivegame?name=Trivia%20Night", headers=officer_headers)
    assert response.status_code == 200, response.get_json()
    assert other.created == [] and "Jeopardy" in soda.created
    assert cog.is_setup()
    again = client.post("/api/bot/setactivegame?name=Trivia%20Night", headers=officer_headers)
    assert again.status_code == 409

    cog.add_member(cast(discord.Member, _player(1)))
    assert client.post("/api/bot/startactivegame", headers=officer_headers).status_code == 200
    assert cog.game is not None and cog.game.is_started
