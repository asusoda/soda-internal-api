"""DELETE /api/points/<org>/entries/<id> deletes one point entry of the org by its id."""

import pytest

from tests.contract.conftest import MEMBER_EMAIL


def _add_entry(org_prefix: str, event: str, points: float) -> int:
    from core.db import db_connect
    from modules.organizations.models import Organization
    from modules.points.models import Points
    from modules.users.models import User

    with db_connect.SessionLocal() as db:
        org = db.query(Organization).filter_by(prefix=org_prefix).one()
        alice = db.query(User).filter_by(email=MEMBER_EMAIL).one()
        entry = Points(user_id=alice.id, organization_id=org.id, points=points, event=event, awarded_by_officer="test")
        db.add(entry)
        db.commit()
        return entry.id


def _entry_ids(event: str) -> list[int]:
    from core.db import db_connect
    from modules.points.models import Points

    with db_connect.SessionLocal() as db:
        return [row.id for row in db.query(Points).filter_by(event=event).order_by(Points.id)]


@pytest.fixture
def remove_test_entries(app):
    yield
    from core.db import db_connect
    from modules.points.models import Points

    with db_connect.SessionLocal() as db:
        db.query(Points).filter(Points.event.in_(["Twice", "Other org"])).delete()
        db.commit()


def test_delete_by_id_removes_only_that_entry(client, officer_headers, remove_test_entries):
    first = _add_entry("soda", "Twice", 5)
    second = _add_entry("soda", "Twice", 7)

    response = client.delete(f"/api/points/soda/entries/{second}", headers=officer_headers)

    assert response.status_code == 200
    deleted = response.get_json()["deleted_points"]
    assert (deleted["id"], deleted["points"], deleted["event"]) == (second, 7, "Twice")
    assert _entry_ids("Twice") == [first]


def test_entry_of_another_org_is_not_found(client, officer_headers, remove_test_entries):
    other = _add_entry("ais", "Other org", 3)

    response = client.delete(f"/api/points/soda/entries/{other}", headers=officer_headers)

    assert response.status_code == 404
    assert response.get_json() == {"error": "Points entry not found"}
    assert _entry_ids("Other org") == [other]


def test_missing_entry_is_not_found(client, officer_headers):
    response = client.delete("/api/points/soda/entries/999999", headers=officer_headers)
    assert response.status_code == 404


def test_delete_by_id_needs_a_token(client, remove_test_entries):
    entry = _add_entry("soda", "Twice", 1)
    assert client.delete(f"/api/points/soda/entries/{entry}").status_code == 401
    assert _entry_ids("Twice") == [entry]


def test_history_has_the_entry_ids(client, officer_headers, remove_test_entries):
    entry = _add_entry("soda", "Twice", 2)
    history = client.get(f"/api/points/soda/users/{MEMBER_EMAIL}/points", headers=officer_headers).get_json()
    assert entry in [row["id"] for row in history["points_history"]]
