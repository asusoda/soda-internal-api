"""Store orders charge the catalog total, refunds follow a cancel or a delete, and points rows match orders."""

import pytest
from sqlalchemy import event, func

from tests.contract.conftest import MEMBER_EMAIL


@pytest.fixture
def db(app):
    from core.db import db_connect

    session = db_connect.SessionLocal()
    yield session
    session.close()


@pytest.fixture
def mug(app):
    """A 300-point product in SoDA with stock 10, and 1000 points for Alice. Both are removed after the test."""
    from core.db import db_connect
    from modules.organizations.models import Organization
    from modules.points.models import Points
    from modules.storefront.models import Order, OrderItem, Product
    from modules.users.models import User

    session = db_connect.SessionLocal()
    soda = session.query(Organization).filter_by(prefix="soda").one()
    alice = session.query(User).filter_by(email=MEMBER_EMAIL).one()
    product = Product(organization_id=soda.id, name="Mug", description="", price=300, stock=10)
    top_up = Points(user_id=alice.id, organization_id=soda.id, points=1000, event="Top up", awarded_by_officer="test")
    session.add_all([product, top_up])
    session.commit()
    product_id, top_up_id = product.id, top_up.id
    session.close()
    yield product_id
    session = db_connect.SessionLocal()
    order_ids = [row.order_id for row in session.query(OrderItem.order_id).filter_by(product_id=product_id)]
    for order_id in order_ids:
        session.query(Points).filter(Points.event.like(f"% - Order #{order_id}")).delete(synchronize_session=False)
    session.query(OrderItem).filter_by(product_id=product_id).delete(synchronize_session=False)
    session.query(Order).filter(Order.id.in_(order_ids)).delete(synchronize_session=False)
    session.query(Points).filter_by(id=top_up_id).delete(synchronize_session=False)
    session.query(Product).filter_by(id=product_id).delete(synchronize_session=False)
    session.commit()
    session.close()


def _balance(db) -> float:
    from modules.points.models import Points
    from modules.users.models import User

    db.expire_all()
    alice = db.query(User).filter_by(email=MEMBER_EMAIL).one()
    org_id = alice.memberships[0].organization_id
    return float(db.query(func.sum(Points.points)).filter_by(user_id=alice.id, organization_id=org_id).scalar() or 0)


def _stock(db, product_id) -> int:
    from modules.storefront.models import Product

    db.expire_all()
    return db.get(Product, product_id).stock


def _orders(db) -> int:
    from modules.storefront.models import Order

    db.expire_all()
    return db.query(Order).count()


def _checkout(client, clerk_headers, product_id, total, price=300, quantity=1):
    body = {"total_amount": total, "items": [{"product_id": product_id, "quantity": quantity, "price": price}]}
    return client.post("/api/storefront/soda/checkout", json=body, headers=clerk_headers)


@pytest.mark.parametrize("total", [-300, "abc", 0.0, [], "nan"])
def test_checkout_refuses_a_bad_total(client, clerk_headers, db, mug, total):
    before = _balance(db)
    assert _checkout(client, clerk_headers, mug, total).status_code == 400
    assert _balance(db) == before
    assert _stock(db, mug) == 10


def test_checkout_charges_the_catalog_total(client, clerk_headers, db, mug):
    before = _balance(db)
    response = _checkout(client, clerk_headers, mug, total=0.5, price=0.5)
    assert response.status_code == 201
    assert response.get_json()["points_deducted"] == 300
    assert response.get_json()["order"]["total_amount"] == 300
    assert _balance(db) == before - 300
    assert _stock(db, mug) == 9


def test_checkout_charges_each_unit(client, clerk_headers, db, mug):
    before = _balance(db)
    response = _checkout(client, clerk_headers, mug, total=600, quantity=2)
    assert response.status_code == 201
    assert _balance(db) == before - 600


def test_checkout_refuses_a_charge_above_the_balance(client, clerk_headers, db, mug):
    before = _balance(db)
    quantity = int(before // 300) + 1
    response = _checkout(client, clerk_headers, mug, total=1, price=300, quantity=quantity)
    assert response.status_code == 400
    assert "Insufficient points" in response.get_json()["error"]
    assert _balance(db) == before
    assert _stock(db, mug) == 10


def test_checkout_writes_nothing_if_the_charge_fails(client, clerk_headers, db, mug, monkeypatch):
    from modules.points.models import Points

    def fail(self, **kwargs):
        raise RuntimeError("points write failed")

    orders = _orders(db)
    monkeypatch.setattr(Points, "__init__", fail)
    assert _checkout(client, clerk_headers, mug, total=300).status_code == 500
    monkeypatch.undo()
    assert _orders(db) == orders
    assert _stock(db, mug) == 10


def test_cancel_refunds_once_and_restocks(client, clerk_headers, officer_headers, db, mug):
    before = _balance(db)
    order_id = _checkout(client, clerk_headers, mug, total=300).get_json()["id"]
    path = f"/api/storefront/soda/orders/{order_id}"

    assert client.put(path, json={"status": "cancelled"}, headers=officer_headers).status_code == 200
    assert _balance(db) == before
    assert _stock(db, mug) == 10

    assert client.put(path, json={"status": "cancelled"}, headers=officer_headers).status_code == 200
    assert client.put(path, json={"status": "pending"}, headers=officer_headers).status_code == 409
    assert client.delete(path, headers=officer_headers).status_code == 200
    assert _balance(db) == before
    assert _stock(db, mug) == 10


def test_delete_refunds_and_restocks(client, clerk_headers, officer_headers, db, mug):
    before = _balance(db)
    order_id = _checkout(client, clerk_headers, mug, total=300).get_json()["id"]
    assert client.delete(f"/api/storefront/soda/orders/{order_id}", headers=officer_headers).status_code == 200
    assert _balance(db) == before
    assert _stock(db, mug) == 10


def test_order_tools_refund(client, clerk_headers, db, mug):
    from modules.storefront import service

    before = _balance(db)
    first = _checkout(client, clerk_headers, mug, total=300).get_json()["order"]
    second = _checkout(client, clerk_headers, mug, total=300).get_json()["order"]
    org_id = 1
    service.update_orders(db, org_id, [first["id"]], {"status": "cancelled"})
    service.delete_orders(db, org_id, [first["id"], second["id"]])
    assert _balance(db) == before
    assert _stock(db, mug) == 10


def test_cancel_of_an_unpaid_order_gives_no_points(member_client, officer_headers, client, db, mug):
    before = _balance(db)
    body = {"total_amount": 300, "items": [{"product_id": mug, "quantity": 1, "price": 300}]}
    response = member_client.post("/api/storefront/soda/members/orders", json=body)
    assert response.status_code == 201
    path = f"/api/storefront/soda/orders/{response.get_json()['id']}"
    assert client.put(path, json={"status": "cancelled"}, headers=officer_headers).status_code == 200
    assert _balance(db) == before
    assert _stock(db, mug) == 10


def test_member_order_uses_the_catalog_total(member_client, db, mug):
    body = {"total_amount": 1, "items": [{"product_id": mug, "quantity": 2, "price": 1}]}
    response = member_client.post("/api/storefront/soda/members/orders", json=body)
    assert response.status_code == 201
    assert response.get_json()["order"]["total_amount"] == 600


def test_member_reads_own_order(member_client, client, clerk_headers, mug):
    order_id = _checkout(client, clerk_headers, mug, total=300).get_json()["id"]
    response = member_client.get(f"/api/storefront/soda/members/orders/{order_id}")
    assert response.status_code == 200
    assert response.get_json()["id"] == order_id


def test_member_cannot_read_another_members_order(member_client, db):
    from modules.storefront.models import Order
    from modules.users.models import User

    bob = db.query(User).filter_by(email="bob@asu.edu").one()
    order = Order(organization_id=1, user_id=bob.id, total_amount=5, status="pending")
    db.add(order)
    db.commit()
    try:
        assert member_client.get(f"/api/storefront/soda/members/orders/{order.id}").status_code == 404
    finally:
        db.delete(order)
        db.commit()


def test_delete_of_a_product_with_orders_is_refused(client, officer_headers, db):
    from modules.storefront import service
    from modules.storefront.models import OrderItem

    product_id = db.query(OrderItem.product_id).first().product_id
    response = client.delete(f"/api/storefront/soda/products/{product_id}", headers=officer_headers)
    assert response.status_code == 409
    assert "has orders" in response.get_json()["error"]
    with pytest.raises(service.StoreError) as raised:
        service.delete_products(db, 1, [product_id])
    assert raised.value.status == 409
    assert service.product(db, product_id, 1) is not None


def test_global_leaderboard_groups_every_selected_column(client, app):
    from core.db import db_connect

    statements = []

    def record(conn, cursor, statement, parameters, context, executemany):
        statements.append(statement)

    event.listen(db_connect.engine, "before_cursor_execute", record)
    try:
        assert client.get("/api/public/leaderboard").status_code == 200
    finally:
        event.remove(db_connect.engine, "before_cursor_execute", record)
    grouped = [s for s in statements if "GROUP BY" in s and "curr_sem_points" in s]
    assert grouped
    group_by = grouped[0].split("GROUP BY", 1)[1].split("ORDER BY", 1)[0]
    assert "users.id" in group_by
    assert "users.name" in group_by


def test_csv_import_adds_the_membership(app, db):
    from modules.organizations.models import Organization
    from modules.points.csv_import import process_csv_in_background
    from modules.points.models import Points
    from modules.users.models import User, UserOrganizationMembership

    soda = db.query(Organization).filter_by(prefix="soda").one()
    ais = db.query(Organization).filter_by(prefix="ais").one()
    carol = User(username="carol", email="carol@asu.edu", name="Carol", uuid="00000000-0000-0000-0000-0000000000c0")
    db.add(carol)
    db.flush()
    db.add(UserOrganizationMembership(user_id=carol.id, organization_id=ais.id))
    db.commit()
    try:
        csv_text = "First Name,Last Name,Email,Checked-In Date\nCarol,C,carol@asu.edu,2026-10-01\n"
        process_csv_in_background(csv_text, "Hack Night", 10, "soda")
        db.expire_all()
        member = db.query(UserOrganizationMembership).filter_by(user_id=carol.id, organization_id=soda.id).first()
        assert member is not None and member.is_active
        assert db.query(Points).filter_by(user_id=carol.id, organization_id=soda.id).count() == 1
    finally:
        db.query(Points).filter_by(user_id=carol.id).delete()
        db.query(UserOrganizationMembership).filter_by(user_id=carol.id).delete()
        db.query(User).filter_by(id=carol.id).delete()
        db.commit()
