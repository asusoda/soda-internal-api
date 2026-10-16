"""Superadmin: adding an org for a Discord server."""

from modules.superadmin.service import prefix_for

from .test_access import SUPERADMIN_ID, headers_for


class Guilds:
    def __init__(self, ready=True, guild=None):
        self.ready, self.guild = ready, guild

    def is_ready(self):
        return self.ready

    def get_guild(self, guild_id):
        return self.guild


def test_prefix_follows_the_prefix_rules():
    assert prefix_for("Robotics Club @ ASU!", 1) == "robotics_club_asu"
    assert prefix_for("A" * 40, 1) == "a" * 20
    assert prefix_for("$$", 123456789) == "org_456789"


def test_add_org_errors(client, monkeypatch, app):
    from core.config import config

    monkeypatch.setattr(config, "SUPERADMIN_USER_ID", SUPERADMIN_ID)
    headers = headers_for(SUPERADMIN_ID)

    monkeypatch.setattr(app, "discord_directory", Guilds(ready=False))
    assert client.post("/api/superadmin/add_org/77", headers=headers).status_code == 503

    monkeypatch.setattr(app, "discord_directory", Guilds())
    assert client.post("/api/superadmin/add_org/77", headers=headers).status_code == 404

    taken = {"id": "77", "name": "AIS", "icon_url": None}
    monkeypatch.setattr(app, "discord_directory", Guilds(guild=taken))
    assert client.post("/api/superadmin/add_org/77", headers=headers).status_code == 409


def _org_with_data(prefix):
    """An org with members, points, an order, a token, an owned submodule and an app without a pod."""
    import uuid

    from core.db import db_connect
    from modules.auth import machine_tokens
    from modules.organizations.models import Organization
    from modules.points.models import Points
    from modules.runpod.models import App, AppDeployment
    from modules.storefront.models import Order, OrderItem, Product
    from modules.submodules.models import Submodule
    from modules.users.models import User, UserOrganizationMembership

    db = db_connect.SessionLocal()
    try:
        org = Organization(name=prefix, prefix=prefix, guild_id=str(uuid.uuid4().int)[:18], is_active=True, config={})
        db.add(org)
        db.flush()
        user = User(username=prefix, email=f"{prefix}@asu.edu", name=prefix, uuid=str(uuid.uuid4()))
        db.add(user)
        db.flush()
        product = Product(organization_id=org.id, name="Shirt", price=5, stock=1)
        order = Order(organization_id=org.id, user_id=user.id, total_amount=5, status="pending")
        app = App(organization_id=org.id, name="bot", manifest="{}")
        db.add_all([product, order, app, UserOrganizationMembership(user_id=user.id, organization_id=org.id)])
        db.add(Points(user_id=user.id, organization_id=org.id, points=5, event="GBM", awarded_by_officer="x"))
        db.add(Submodule(key=f"{prefix}-pack", title="Pack", owner_org_id=org.id))
        db.flush()
        db.add(OrderItem(organization_id=org.id, order_id=order.id, product_id=product.id, quantity=1, price_at_time=5))
        db.add(AppDeployment(app_id=app.id, tag="v1", status="failed"))
        machine_tokens.issue(db, organization_id=org.id, name="ci", kind="app", scopes=["apps:read"])
        db.commit()
        return org.id, user.id
    finally:
        db.close()


def test_remove_org_deletes_its_rows_and_keeps_shared_ones(client, monkeypatch):
    from core.config import config
    from core.db import db_connect
    from modules.organizations.models import Organization
    from modules.points.models import Points
    from modules.storefront.models import Order, OrderItem
    from modules.submodules.models import Submodule
    from modules.users.models import User

    monkeypatch.setattr(config, "SUPERADMIN_USER_ID", SUPERADMIN_ID)
    org_id, user_id = _org_with_data("doomed")
    response = client.delete(f"/api/superadmin/remove_org/{org_id}", headers=headers_for(SUPERADMIN_ID))
    assert response.status_code == 200, response.get_json()
    assert response.get_json() == {"message": "Organization doomed removed successfully!"}

    db = db_connect.SessionLocal()
    try:
        assert db.get(Organization, org_id) is None
        for model in (Points, Order, OrderItem):
            assert db.query(model).filter_by(organization_id=org_id).count() == 0
        assert db.get(User, user_id) is not None
        assert db.query(Submodule).filter_by(key="doomed-pack").one().owner_org_id is None
        assert (
            db.query(Points)
            .filter_by(organization_id=db.query(Organization.id).filter_by(prefix="soda").scalar_subquery())
            .count()
        )
    finally:
        db.close()
    assert client.delete(f"/api/superadmin/remove_org/{org_id}", headers=headers_for(SUPERADMIN_ID)).status_code == 404


def test_remove_org_refuses_while_an_app_has_a_pod(client, monkeypatch):
    from core.config import config
    from core.db import db_connect
    from modules.runpod.models import App

    monkeypatch.setattr(config, "SUPERADMIN_USER_ID", SUPERADMIN_ID)
    org_id, _ = _org_with_data("running")
    db = db_connect.SessionLocal()
    try:
        db.query(App).filter_by(organization_id=org_id).update({"pod_id": "pod1"})
        db.commit()
    finally:
        db.close()
    response = client.delete(f"/api/superadmin/remove_org/{org_id}", headers=headers_for(SUPERADMIN_ID))
    assert response.status_code == 409
    assert "Delete them first" in response.get_json()["error"]
