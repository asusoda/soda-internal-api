"""API contract tests.

Each case calls an endpoint that a known client uses and compares the status code and the
shape of the JSON body (keys and value types, not values) with tests/contract/snapshots.json.
The callers are listed in docs/api-contract.md.

A change that breaks a case breaks a client. If the change is intended, regenerate the
snapshots with UPDATE_CONTRACT=1 and say in the PR which client was updated to match.
"""

import json
import os
from pathlib import Path

import pytest

from tests.contract.conftest import MEMBER_EMAIL

SNAPSHOTS = Path(__file__).with_name("snapshots.json")
UPDATE = os.environ.get("UPDATE_CONTRACT") == "1"

# (case id, client, method, path, auth, json body)
# client: "website" is asusoda/website (thesoda.io), "dashboard" is this repo's dashboard/ app, "none" is no known client.
# auth: None, "officer" (platform JWT), "clerk" (Clerk session token), "member" (Discord login session).
CASES = [
    ("health", "deploy", "GET", "/health", None, None),
    ("calendar-events", "website", "GET", "/api/calendar/soda/events", None, None),
    ("leaderboard", "website", "GET", "/api/points/soda/leaderboard", None, None),
    ("leaderboard-unknown-org", "website", "GET", "/api/points/nope/leaderboard", None, None),
    ("products", "website", "GET", "/api/storefront/soda/products", None, None),
    ("product", "website", "GET", "/api/storefront/soda/products/1", None, None),
    ("member-store-clerk", "website", "GET", "/api/storefront/soda/members/store", "clerk", None),
    ("member-store-session", "dashboard", "GET", "/api/storefront/soda/members/store", "member", None),
    ("orders-by-email", "website", "GET", f"/api/storefront/soda/orders/{MEMBER_EMAIL}", "clerk", None),
    ("wallet", "website", "GET", f"/api/storefront/soda/wallet/{MEMBER_EMAIL}", "clerk", None),
    ("orders-no-auth", "website", "GET", f"/api/storefront/soda/orders/{MEMBER_EMAIL}", None, None),
    (
        "member-login",
        "website",
        "POST",
        "/api/points/soda/member_login",
        None,
        {"name": "Alice", "email": MEMBER_EMAIL, "username": "alice", "asu_id": "1200000001"},
    ),
    ("member-profile", "dashboard", "GET", "/api/points/soda/member_profile", "member", None),
    ("public-leaderboard", "dashboard", "GET", "/api/public/soda/leaderboard", None, None),
    ("organizations", "dashboard", "GET", "/api/organizations/", "officer", None),
    ("org-users", "dashboard", "GET", "/api/points/soda/users", "officer", None),
    ("org-users-no-auth", "dashboard", "GET", "/api/points/soda/users", None, None),
    ("user-points", "dashboard", "GET", f"/api/points/soda/users/{MEMBER_EMAIL}/points", "officer", None),
    ("store-orders", "dashboard", "GET", "/api/storefront/soda/orders", "officer", None),
    ("member-orders", "dashboard", "GET", "/api/storefront/soda/members/orders", "member", None),
    ("auth-name", "none", "GET", "/api/auth/name", "officer", None),
    ("auth-valid-token", "none", "GET", "/api/auth/validToken", "officer", None),
    ("superadmin-check", "dashboard", "GET", "/api/superadmin/check", "officer", None),
    ("calendar-settings", "dashboard", "GET", "/api/organizations/1/calendar", "officer", None),
    (
        "assign-points",
        "dashboard",
        "POST",
        "/api/points/soda/assign_points",
        "officer",
        {"user_identifier": MEMBER_EMAIL, "points": 5, "event": "Workshop", "awarded_by_officer": "officer"},
    ),
    (
        "checkout",
        "website",
        "POST",
        "/api/storefront/soda/checkout",
        "clerk",
        {"total_amount": 5, "items": [{"product_id": 1, "quantity": 1, "price": 5}]},
    ),
]


def shape(value):
    """Reduce a JSON value to its structure: dict keys and value types, list element shapes."""
    if isinstance(value, dict):
        return {key: shape(value[key]) for key in sorted(value)}
    if isinstance(value, list):
        shapes = []
        for item in value:
            item_shape = shape(item)
            if item_shape not in shapes:
                shapes.append(item_shape)
        return shapes
    if isinstance(value, bool):
        return "bool"
    if isinstance(value, int | float):
        return "number"
    if isinstance(value, str):
        return "string"
    return "null"


def call(client, member_client, officer_headers, clerk_headers, method, path, auth, body):
    headers = {}
    use = client
    if auth == "officer":
        headers = officer_headers
    elif auth == "clerk":
        headers = clerk_headers
    elif auth == "member":
        use = member_client
    return use.open(path, method=method, headers=headers, json=body)


def load_snapshots():
    if SNAPSHOTS.exists():
        return json.loads(SNAPSHOTS.read_text())
    return {}


_recorded = {}


@pytest.mark.parametrize(("case", "caller", "method", "path", "auth", "body"), CASES, ids=[c[0] for c in CASES])
def test_contract(client, member_client, officer_headers, clerk_headers, case, caller, method, path, auth, body):
    response = call(client, member_client, officer_headers, clerk_headers, method, path, auth, body)
    payload = response.get_json(silent=True)
    actual = {"caller": caller, "request": f"{method} {path}", "status": response.status_code, "shape": shape(payload)}

    if UPDATE:
        _recorded[case] = actual
        snapshots = load_snapshots()
        snapshots.update(_recorded)
        SNAPSHOTS.write_text(json.dumps(snapshots, indent=2, sort_keys=True) + "\n")
        return

    expected = load_snapshots().get(case)
    assert expected is not None, f"No snapshot for {case}. Run UPDATE_CONTRACT=1 uv run pytest tests/contract"
    assert actual == expected
