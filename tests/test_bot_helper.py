"""The /clear command of HelperCog needs the permissions to delete what it deletes."""

import asyncio
from types import SimpleNamespace
from typing import Any

import discord

from modules.bot.cogs.helper import HelperCog


class _Interaction:
    def __init__(self, permissions: discord.Permissions):
        self.deleted: list[str] = []
        self.sent: list[str] = []
        channel = SimpleNamespace(delete=self._delete("channel"))
        category = SimpleNamespace(name="Jeopardy", channels=[channel], delete=self._delete("category"))
        role = SimpleNamespace(name="Team 1", delete=self._delete("role"))
        self.guild = SimpleNamespace(categories=[category], roles=[role])
        self.user = SimpleNamespace(name="officer", guild_permissions=permissions)
        self.response = SimpleNamespace(send_message=self._send, defer=self._nothing)
        self.followup = SimpleNamespace(send=self._send)

    def _delete(self, kind: str):
        async def delete():
            self.deleted.append(kind)

        return delete

    async def _send(self, message, **kwargs):
        self.sent.append(message)

    async def _nothing(self):
        pass


def _run(permissions: discord.Permissions) -> _Interaction:
    interaction = _Interaction(permissions)
    cog = HelperCog.__new__(HelperCog)
    # The command function, called with the cog and a stand-in for the interaction
    clear: Any = HelperCog.clear.callback
    asyncio.run(clear(cog, interaction))
    return interaction


def test_clear_defaults_to_the_permissions_it_uses():
    wanted = discord.Permissions(manage_guild=True, manage_channels=True, manage_roles=True)
    assert HelperCog.clear.default_member_permissions == wanted


def test_clear_refuses_without_manage_channels_and_roles():
    refused = _run(discord.Permissions(manage_guild=True))
    assert refused.deleted == [] and "Manage Channels" in refused.sent[0]
    refused = _run(discord.Permissions(manage_guild=True, manage_channels=True))
    assert refused.deleted == []
    done = _run(discord.Permissions(manage_guild=True, manage_channels=True, manage_roles=True))
    assert done.deleted == ["channel", "category", "role"]
