"""Checkout prices come from the catalog, points record who entered them, and public lists hide member details."""

import logging

import pytest

from tests.contract.conftest import MEMBER_EMAIL


@pytest.fixture
def enforce(monkeypatch):
    from core.config import config
    from modules.auth import access

    access.clear_cache()
    monkeypatch.setattr(config, "ACCESS_ENFORCE", True)
    yield
    access.clear_cache()


def _checkout(client, clerk_headers, price, total, quantity=1):
    body = {"total_amount": total, "items": [{"product_id": 1, "quantity": quantity, "price": price}]}
    return client.post("/api/storefront/soda/checkout", json=body, headers=clerk_headers)


def test_checkout_at_catalog_price(client, clerk_headers, enforce):
    assert _checkout(client, clerk_headers, price=5, total=5).status_code == 201


def test_checkout_below_catalog_price_is_refused(client, clerk_headers, enforce):
    assert _checkout(client, clerk_headers, price=1, total=1).status_code == 409


def test_checkout_price_mismatch_only_logs_in_report_mode(client, clerk_headers, caplog):
    with caplog.at_level(logging.WARNING, logger="access"):
        response = _checkout(client, clerk_headers, price=1, total=1)
    assert response.status_code == 201
    assert any("reason=checkout_price_mismatch" in r.getMessage() for r in caplog.records)


def test_checkout_quantity_must_be_positive(client, clerk_headers):
    assert _checkout(client, clerk_headers, price=5, total=-5, quantity=-1).status_code == 400


def test_points_record_the_signed_in_officer(client, officer_headers):
    body = {"user_identifier": MEMBER_EMAIL, "points": 1, "event": "Workshop", "awarded_by_officer": "Bob"}
    response = client.post("/api/points/soda/assign_points", json=body, headers=officer_headers)
    assert response.status_code in (200, 201)
    assert "Bob (entered by officer)" in response.get_data(as_text=True)


@pytest.mark.parametrize("path", ["/api/public/soda/leaderboard", "/api/public/soda/users"])
def test_public_lists_hide_member_details(client, officer_headers, path):
    anonymous = client.get(path).get_data(as_text=True)
    assert MEMBER_EMAIL not in anonymous
    assert "1200000001" not in anonymous
    assert MEMBER_EMAIL in client.get(path, headers=officer_headers).get_data(as_text=True)
