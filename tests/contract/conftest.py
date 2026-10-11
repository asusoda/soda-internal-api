"""Fixtures for the API contract tests: the Flask app, seeded data, and stand-ins for Discord, Clerk and Notion."""

import copy
import uuid

import pytest

OFFICER_DISCORD_ID = "900000000000000001"
MEMBER_DISCORD_ID = "900000000000000002"
MEMBER_EMAIL = "alice@asu.edu"

NOTION_PAGE = {
    "id": "notion-page-1",
    "properties": {
        "Name": {"type": "title", "title": [{"plain_text": "Hack Night", "text": {"content": "Hack Night"}}]},
        "Location": {"type": "select", "select": {"name": "BYENG 210"}},
        "Description": {
            "type": "rich_text",
            "rich_text": [{"plain_text": "Bring a laptop", "text": {"content": "Bring a laptop"}}],
        },
        "Date": {"type": "date", "date": {"start": "2026-10-10T18:00:00-07:00", "end": "2026-10-10T20:00:00-07:00"}},
    },
}


class FakeBot:
    """Stands in for the Discord directory: every caller is a member and an officer."""

    def is_ready(self):
        return True

    def officer_guilds(self, user_id, org_roles):
        return [1001]

    def check_user_membership(self, user_id, guild_id):
        return True

    def check_user_officer_status(self, user_id, guild_id, role_id):
        return True

    def check_role(self, guild_id, role_id, user_id):
        return True

    def list_guilds(self):
        return [{"id": "1001", "name": "SoDA", "icon_url": None}, {"id": "1003", "name": "New Club", "icon_url": None}]

    def get_guild(self, guild_id):
        return next((g for g in self.list_guilds() if g["id"] == str(guild_id)), None)

    def get_guild_roles(self, guild_id):
        return [
            {"id": "2001", "name": "Officer", "color": "#000000", "position": 1, "permissions": 0, "managed": False}
        ]

    def get_display_name(self, guild_id, user_id):
        return "officer"

    def get_member(self, guild_id, user_id):
        return {"user": {"id": str(user_id), "username": "officer"}, "nick": None, "roles": ["2001"]}


def _seed(db_connect):
    from modules.organizations.models import Organization
    from modules.points.models import Points
    from modules.storefront.models import Order, OrderItem, Product
    from modules.users.models import User, UserOrganizationMembership

    db = next(db_connect.get_db())
    try:
        soda = Organization(
            name="SoDA",
            prefix="soda",
            guild_id="1001",
            officer_role_id="2001",
            notion_database_id="notion-db-soda",
            is_active=True,
            config={},
        )
        ais = Organization(name="AI Society", prefix="ais", guild_id="1002", officer_role_id="2002", is_active=True)
        db.add_all([soda, ais])
        db.flush()

        alice = User(
            discord_id=MEMBER_DISCORD_ID,
            username="alice",
            email=MEMBER_EMAIL,
            name="Alice",
            student_id="1200000001",
            uuid=str(uuid.UUID(int=1)),
        )
        bob = User(username="bob", email="bob@asu.edu", name="Bob", student_id="1200000002", uuid=str(uuid.UUID(int=2)))
        db.add_all([alice, bob])
        db.flush()

        db.add_all(
            [
                UserOrganizationMembership(user_id=alice.id, organization_id=soda.id),
                UserOrganizationMembership(user_id=bob.id, organization_id=soda.id),
                Points(user_id=alice.id, organization_id=soda.id, points=50, event="GBM", awarded_by_officer="officer"),
                Points(user_id=bob.id, organization_id=soda.id, points=20, event="GBM", awarded_by_officer="officer"),
            ]
        )
        sticker = Product(organization_id=soda.id, name="Sticker", description="Logo sticker", price=5, stock=100)
        db.add(sticker)
        db.flush()
        order = Order(organization_id=soda.id, user_id=alice.id, total_amount=5, status="pending")
        db.add(order)
        db.flush()
        db.add(
            OrderItem(organization_id=soda.id, order_id=order.id, product_id=sticker.id, quantity=1, price_at_time=5)
        )
        db.commit()
    finally:
        db.close()


@pytest.fixture(scope="session")
def app():
    import main
    from core.db import db_connect
    from tests.conftest import create_schema

    create_schema()
    _seed(db_connect)
    setattr(main.app, "auth_bot", FakeBot())  # noqa: B010
    setattr(main.app, "discord_directory", FakeBot())  # noqa: B010
    main.app.config["TESTING"] = True
    return main.app


@pytest.fixture(autouse=True)
def stubs(app, monkeypatch):
    """Replace Clerk and Notion with local stand-ins so no test reaches the network. Each test starts with no cache."""
    from core.cache import cache
    from modules.auth import clerk
    from modules.calendar import service as calendar_service

    monkeypatch.setattr(clerk, "verify_clerk_token", lambda token: (MEMBER_EMAIL, {"id": "user_clerk_1"}))
    monkeypatch.setattr(calendar_service.get_service().notion_client, "fetch_events", lambda *a, **k: [NOTION_PAGE])
    cache.clear()


@pytest.fixture
def client(app):
    return app.test_client()


@pytest.fixture
def member_client(app):
    """A client whose session holds a Discord login, as after the OAuth callback."""
    client = app.test_client()
    with client.session_transaction() as session:
        session["discord_id"] = MEMBER_DISCORD_ID
    return client


@pytest.fixture(scope="session")
def officer_headers(app):
    from modules.auth.tokens import token_manager

    token = token_manager.generate_token(username="officer", discord_id=OFFICER_DISCORD_ID)
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def clerk_headers():
    return {"Authorization": "Bearer clerk-session-token"}


@pytest.fixture
def restore_soda_config(app):
    """Put SoDA's config JSON back after a test that changes it (the contract snapshots read it)."""
    from core.db import db_connect
    from modules.organizations.models import Organization

    db = db_connect.SessionLocal()
    original = copy.deepcopy(db.query(Organization).filter_by(prefix="soda").one().config)
    db.close()
    yield
    db = db_connect.SessionLocal()
    try:
        db.query(Organization).filter_by(prefix="soda").one().config = original
        db.commit()
    finally:
        db.close()


class WebhookResponse:
    def __init__(self, status_code: int = 204) -> None:
        self.status_code = status_code


class Sent(list):
    """Messages posted to webhooks, as (url, payload). status is the status code the next post gets."""

    status = 204


@pytest.fixture
def sent(app, monkeypatch):
    """Posts to webhooks, sent in the test thread. Removes every webhook after the test."""
    from cryptography.fernet import Fernet

    from core import net, webhooks
    from core.db import db_connect

    posts = Sent()

    def post(url, json, timeout, allow_redirects):
        posts.append((url, json))
        return WebhookResponse(posts.status)

    monkeypatch.setenv("SECRETS_KEY", Fernet.generate_key().decode())
    monkeypatch.setattr(webhooks, "spawn", lambda target, *args: target(*args))
    monkeypatch.setattr(webhooks.requests, "post", post)
    monkeypatch.setattr(webhooks, "_sent", {})
    monkeypatch.setattr(net, "check_public", lambda url: None)
    yield posts
    db = db_connect.SessionLocal()
    db.query(webhooks.Webhook).delete()
    db.commit()
    db.close()


@pytest.fixture
def clean_submodules(app):
    """Removes every submodule subscription and shared submodule source after the test.

    Shared sources have no org, so the per-org cleanups of other fixtures leave them, and they are due at once.
    """
    yield
    from core.db import db_connect
    from modules.knowledge.models import KnowledgeChunk, KnowledgeSource, KnowledgeVersion
    from modules.submodules.models import Submodule, SubmoduleSubscription

    db = db_connect.SessionLocal()
    shared = [s.id for s in db.query(KnowledgeSource.id).filter(KnowledgeSource.submodule_id.isnot(None))]
    if shared:
        db.query(KnowledgeChunk).filter(KnowledgeChunk.source_id.in_(shared)).delete(synchronize_session=False)
        db.query(KnowledgeVersion).filter(KnowledgeVersion.source_id.in_(shared)).delete(synchronize_session=False)
        db.query(KnowledgeSource).filter(KnowledgeSource.id.in_(shared)).delete(synchronize_session=False)
    db.query(SubmoduleSubscription).delete()
    db.query(Submodule).delete()
    db.commit()
    db.close()
