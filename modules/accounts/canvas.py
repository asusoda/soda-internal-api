"""Canvas reads for one member with that member's own Canvas grant. Read-only. No Flask here.

Each read takes the member's access token and returns plain dicts. Lists follow the Link header only to
the same Canvas host and stop at MAX_PAGES pages. No read logs a token, a grade or course content.
"""

import datetime
import re
from collections.abc import Callable, Iterator
from typing import Any

import requests

from core.errors import ServiceError
from core.log import get_logger
from modules.accounts import providers, service

logger = get_logger("accounts.canvas")

PROVIDER = "canvas"
TIMEOUT_SECONDS = 30
MAX_ITEMS = 20  # items in a result, and the per_page of each request
MAX_PAGES = 5  # pages followed for one list
BODY_CHARS = 240  # longest announcement body kept

NEXT_LINK = re.compile(r'<([^>]+)>\s*;\s*rel="next"')
TAG = re.compile(r"<[^>]*>")
SPACE = re.compile(r"\s+")

CONNECT_HINT = (
    "Start a Canvas login for the member with POST /api/accounts/members/<discord_id>/canvas/login "
    "(scope accounts:link) and send them the link in a direct message."
)


class CanvasError(ServiceError):
    pass


def configured() -> bool:
    """The deployment has the Canvas provider on, with a Canvas URL."""
    return providers.get(PROVIDER) is not None and providers.canvas_url() is not None


def available(db, org_id: int) -> bool:
    """The Canvas tools show to every org when the deployment has Canvas on."""
    return configured()


def member_token(db, org_id: int, discord_id: str) -> str:
    """The member's own Canvas access token in the org, refreshed by the accounts service when near expiry."""
    try:
        return str(service.access_token(db, org_id, discord_id, PROVIDER)["access_token"])
    except service.AccountError as e:
        if e.status == 404:
            raise CanvasError(f"The member has not connected Canvas. {CONNECT_HINT}", 409) from e
        if e.status == 409:
            raise CanvasError(f"The member's Canvas connection expired. {CONNECT_HINT}", 409) from e
        if e.status == 502:
            raise CanvasError("Canvas could not refresh the member's token. Try again later.", 502) from e
        raise CanvasError(e.message, e.status) from e


class Client:
    """One member's view of a Canvas instance."""

    def __init__(self, base_url: str, token: str):
        self.base = base_url.rstrip("/") + "/api/v1/"
        self.token = token

    def _get(self, url: str, params: list[tuple[str, str]] | None) -> requests.Response:
        try:
            response = requests.get(
                url, params=params, headers={"Authorization": f"Bearer {self.token}"}, timeout=TIMEOUT_SECONDS
            )
        except requests.RequestException as e:
            raise CanvasError("Canvas could not be reached", 502) from e
        if response.status_code in (401, 403):
            raise CanvasError(f"Canvas rejected the member's token. {CONNECT_HINT}", 409)
        if response.status_code >= 400:
            logger.warning("canvas request failed status=%s", response.status_code)
            raise CanvasError(f"Canvas returned {response.status_code}", 502)
        return response

    def _json(self, response: requests.Response) -> Any:
        try:
            return response.json()
        except ValueError as e:
            raise CanvasError("Canvas returned an unexpected response", 502) from e

    def items(self, path: str, params: list[tuple[str, str]] | None = None) -> Iterator[dict]:
        """The objects of a list, page by page, for at most MAX_PAGES pages on this Canvas host."""
        url: str | None = self.base + path
        query = params
        for _ in range(MAX_PAGES):
            if url is None:
                return
            response = self._get(url, query)
            body = self._json(response)
            if not isinstance(body, list):
                raise CanvasError("Canvas returned an unexpected response", 502)
            yield from (item for item in body if isinstance(item, dict))
            url = _next(response.headers.get("Link", ""), self.base)
            query = None  # the next link carries the query


def _next(link: str, base: str) -> str | None:
    """The rel=next URL of a Link header when it is on the same Canvas API, else None."""
    found = NEXT_LINK.search(link)
    if found is None or not found.group(1).startswith(base):
        return None
    return found.group(1)


def _when(value: Any) -> datetime.datetime | None:
    if not isinstance(value, str) or not value:
        return None
    try:
        parsed = datetime.datetime.fromisoformat(value)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=datetime.UTC)
    return parsed.astimezone(datetime.UTC)


def _iso(value: datetime.datetime | None) -> str | None:
    return value.strftime("%Y-%m-%dT%H:%M:%SZ") if value else None


def _shown(value: datetime.datetime | None, missing: str) -> str:
    return value.strftime("%b %d, %Y %H:%M UTC") if value else missing


def _number(value: Any) -> float | None:
    if isinstance(value, bool) or not isinstance(value, int | float):
        return None
    return float(value)


def _num(value: float) -> str:
    return str(int(value)) if value.is_integer() else str(value)


def _text(value: Any) -> str:
    return value if isinstance(value, str) else ""


def _optional(value: Any) -> str | None:
    return value if isinstance(value, str) and value else None


def plain(html: str) -> str:
    """html with tags removed, whitespace collapsed, and held to BODY_CHARS."""
    text = SPACE.sub(" ", TAG.sub("", html)).strip()
    return text[:BODY_CHARS] + "..." if len(text) > BODY_CHARS else text


def _per_page() -> tuple[str, str]:
    return ("per_page", str(MAX_ITEMS))


# Reads. Each returns the items and the text the agent reads.


def _course_list(client: Client) -> list[dict]:
    courses = []
    for c in client.items("courses", [("enrollment_state", "active"), _per_page()]):
        if isinstance(c.get("id"), int):
            courses.append({"id": c["id"], "name": _text(c.get("name")), "code": _text(c.get("course_code"))})
        if len(courses) >= MAX_ITEMS:
            break
    return courses


def courses(client: Client) -> dict:
    shown = _course_list(client)
    if not shown:
        text = "No active Canvas courses."
    else:
        text = f"{len(shown)} active courses:" + "".join(f"\n- {c['name']} ({c['code']})" for c in shown)
    return {"courses": shown, "text": text}


def assignments(client: Client) -> dict:
    found: list[tuple[datetime.datetime | None, dict]] = []
    for todo in client.items("users/self/todo", [_per_page()]):
        a = todo.get("assignment")
        if todo.get("type") != "submitting" or not isinstance(a, dict):
            continue
        due = _when(a.get("due_at"))
        item = {
            "name": _text(a.get("name")),
            "course": _text(todo.get("context_name")),
            "due_at": _iso(due),
            "points": _number(a.get("points_possible")),
            "url": _optional(a.get("html_url")),
        }
        found.append((due, item))
    far = datetime.datetime.max.replace(tzinfo=datetime.UTC)
    found.sort(key=lambda pair: (pair[0] is None, pair[0] or far))
    shown = found[:MAX_ITEMS]
    if not shown:
        text = "No upcoming assignments to submit."
    else:
        lines = [f"{len(shown)} upcoming assignments:"]
        for due, a in shown:
            points = f", {_num(a['points'])} pts" if a["points"] is not None else ""
            link = f" {a['url']}" if a["url"] else ""
            lines.append(f"- {a['name']} ({a['course']}) due {_shown(due, 'no due date')}{points}{link}")
        text = "\n".join(lines)
    return {"assignments": [a for _, a in shown], "text": text}


def grades(client: Client) -> dict:
    shown: list[dict[str, Any]] = []
    params = [("enrollment_state", "active"), ("include[]", "total_scores"), _per_page()]
    for c in client.items("courses", params):
        found = c.get("enrollments")
        enrollments: list = found if isinstance(found, list) else []
        student = next(
            (e for e in enrollments if isinstance(e, dict) and e.get("type") in ("student", "StudentEnrollment")),
            {},
        )
        shown.append(
            {
                "course": _text(c.get("name")),
                "score": _number(student.get("computed_current_score")),
                "grade": _optional(student.get("computed_current_grade")),
            }
        )
        if len(shown) >= MAX_ITEMS:
            break
    if not shown:
        return {"grades": [], "text": "No grades available."}
    lines = ["Current grades:"]
    for g in shown:
        if g["grade"] and g["score"] is not None:
            standing = f"{g['grade']} ({_num(g['score'])})"
        elif g["grade"]:
            standing = g["grade"]
        elif g["score"] is not None:
            standing = _num(g["score"])
        else:
            standing = "not graded yet"
        lines.append(f"- {g['course']}: {standing}")
    return {"grades": shown, "text": "\n".join(lines)}


def announcements(client: Client) -> dict:
    course_list = _course_list(client)
    shown: list[tuple[datetime.datetime | None, dict]] = []
    if course_list:
        names = {f"course_{c['id']}": c["name"] for c in course_list}
        params = [_per_page(), ("active_only", "true")] + [("context_codes[]", code) for code in names]
        for a in client.items("announcements", params):
            posted = _when(a.get("posted_at"))
            message = _text(a.get("message"))
            item = {
                "title": _text(a.get("title")),
                "course": names.get(_text(a.get("context_code")), ""),
                "posted_at": _iso(posted),
                "body": plain(message) if message.strip() else None,
                "url": _optional(a.get("html_url")),
            }
            shown.append((posted, item))
            if len(shown) >= MAX_ITEMS:
                break
    if not shown:
        return {"announcements": [], "text": "No recent announcements."}
    lines = [f"{len(shown)} recent announcements:"]
    for posted, a in shown:
        body = f" - {a['body']}" if a["body"] else ""
        link = f" {a['url']}" if a["url"] else ""
        lines.append(f"- {a['title']} ({a['course']}) {_shown(posted, 'no date')}{body}{link}")
    return {"announcements": [a for _, a in shown], "text": "\n".join(lines)}


def calendar(client: Client) -> dict:
    shown: list[tuple[datetime.datetime | None, dict]] = []
    for e in client.items("users/self/upcoming_events"):
        start = _when(e.get("start_at"))
        item = {
            "title": _text(e.get("title")),
            "start_at": _iso(start),
            "location": _optional(e.get("location_name")),
            "url": _optional(e.get("html_url")),
        }
        shown.append((start, item))
        if len(shown) >= MAX_ITEMS:
            break
    if not shown:
        return {"events": [], "text": "No upcoming calendar events."}
    lines = [f"{len(shown)} upcoming events:"]
    for start, e in shown:
        place = f" at {e['location']}" if e["location"] else ""
        link = f" {e['url']}" if e["url"] else ""
        lines.append(f"- {e['title']} {_shown(start, 'no date')}{place}{link}")
    return {"events": [e for _, e in shown], "text": "\n".join(lines)}


def assignment_grades(client: Client) -> dict:
    shown: list[dict] = []
    for course in _course_list(client):
        params = [("include[]", "submission"), _per_page()]
        for a in client.items(f"courses/{course['id']}/assignments", params):
            sub = a.get("submission")
            if not isinstance(sub, dict):
                continue
            score, grade = _number(sub.get("score")), _optional(sub.get("grade"))
            if score is None and grade is None:
                continue
            shown.append(
                {
                    "course": course["name"],
                    "name": _text(a.get("name")),
                    "score": score,
                    "points": _number(a.get("points_possible")),
                    "grade": grade,
                }
            )
            if len(shown) >= MAX_ITEMS:
                break
        if len(shown) >= MAX_ITEMS:
            break
    if not shown:
        return {"grades": [], "text": "No graded assignments yet."}
    lines = ["Assignment grades:"]
    for g in shown:
        score, points, grade = g["score"], g["points"], g["grade"]
        if grade and score is not None and points is not None:
            mark = f"{grade} ({_num(score)}/{_num(points)})"
        elif score is not None and points is not None:
            mark = f"{_num(score)}/{_num(points)}"
        elif grade:
            mark = grade
        elif score is not None:
            mark = _num(score)
        else:
            mark = "graded"
        lines.append(f"- {g['name']} ({g['course']}): {mark}")
    return {"grades": shown, "text": "\n".join(lines)}


def read(db, org_id: int, discord_id: str, query: Callable[[Client], dict]) -> dict:
    """Run one read for the member with the member's own grant in the org."""
    base = providers.canvas_url()
    if base is None or not configured():
        raise CanvasError("Canvas is not set up on this platform", 404)
    return query(Client(base, member_token(db, org_id, service.member(discord_id))))
