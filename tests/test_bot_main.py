"""The bot process stops when it gets SIGTERM, as `podman stop` sends it."""

import asyncio
import os
import signal
import sys

import pytest

import bot_main


class FakeBot:
    """Waits in start() until close() runs, as the Discord client does."""

    def __init__(self):
        self.stopped = asyncio.Event()

    async def start(self, token):
        asyncio.get_running_loop().call_soon(os.kill, os.getpid(), signal.SIGTERM)
        await self.stopped.wait()

    async def close(self):
        self.stopped.set()

    def is_closed(self):
        return self.stopped.is_set()


@pytest.mark.skipif(sys.platform == "win32", reason="Windows has no SIGTERM handler on the event loop")
def test_sigterm_closes_the_bot(monkeypatch):
    bot = FakeBot()
    monkeypatch.setattr(bot_main, "init_sentry", lambda *args: None)
    monkeypatch.setattr(bot_main.error_alerts, "setup", lambda source: None)
    monkeypatch.setattr(bot_main.config, "BOT_TOKEN", "token")
    monkeypatch.setattr(bot_main, "create_bot", lambda loop: bot)

    assert bot_main.main() == 0
    assert bot.is_closed()
