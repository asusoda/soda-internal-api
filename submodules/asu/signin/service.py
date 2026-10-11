"""The org's ASU sign-in: one attempt at a time, the saved session, and page loads with it. No Flask here.

An officer sends a NetID and a password. A thread signs in with the browser and reports progress,
such as the Duo code, to the attempt that the dashboard polls. The NetID and the password stay in that
thread only: they are not saved, logged or put in an error. On success the session (the browser
cookies) is saved as the org secret asu_session. The attempts are in the memory of the API process.

When a page load ends on a sign-in page, the session has expired. The saved session is marked
expired, and the event asu.session_expired is sent one time for that expiry.
"""

from __future__ import annotations

import json
import threading
import time
from collections.abc import Callable
from dataclasses import asdict, dataclass

from core import secrets, webhooks
from core.config import config
from core.db import session
from core.errors import ServiceError
from core.log import get_logger
from modules.submodules.types import Fetched
from submodules.asu.signin import browser as browsers
from submodules.asu.signin import sso
from submodules.asu.signin.browser import Browser, LoadFailed
from submodules.asu.signin.sso import BadPassword, SignInFailed

logger = get_logger("asu.signin")

SECRET = "asu_session"  # nosec B105 - the name of an org secret, not its value
MAX_NETID = 64
MAX_PASSWORD = 256
EXPIRED = "The ASU sign-in has expired. An officer must sign in again on the ASU card of Explore, Submodules"
NOT_SIGNED_IN = "No ASU sign-in. An officer must sign in on the ASU card of Explore, Submodules"
NOT_SUBSCRIBED = "The org does not subscribe to the ASU submodule. Subscribe on Explore, Submodules"
SUBMODULE = "asu"

secrets.declare(SECRET, "ASU: the browser cookies of the officer who signed in to ASU")
webhooks.declare(
    "asu.session_expired",
    "ASU sign-in expired",
    "The saved ASU sign-in expired. An officer signs in again on the Integrations tab of Explore.",
)


class AsuError(ServiceError):
    """A refused or failed ASU request. The message has no NetID, password or cookie in it."""


class SessionExpired(AsuError):
    """The saved session no longer opens Sun Devil Central."""


@dataclass
class Attempt:
    # running, duo_code, done or failed
    state: str
    message: str
    started_at: str
    code: str | None = None
    reason: str | None = None
    finished_at: str | None = None


# Makes the browser that sign-ins and page loads use. Tests replace it.
browser: Callable[[], Browser] = browsers.Chromium

_attempts: dict[int, Attempt] = {}
_lock = threading.Lock()
_expiry = threading.Lock()


def _thread(target: Callable, *args) -> None:
    threading.Thread(target=target, args=args, name="asu-signin", daemon=True).start()


# Starts a sign-in attempt. Tests replace it to run the attempt in the test thread.
spawn: Callable[..., object] = _thread


def _now() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def blocked() -> str | None:
    """Why a sign-in cannot start on this API, or None when it can."""
    if not secrets.configured():
        return "Set SECRETS_KEY on the API to save the ASU sign-in"
    return browsers.missing()


def _saved(db, org_id: int) -> dict | None:
    raw = secrets.get_secret(db, org_id, SECRET)
    if not raw:
        return None
    try:
        value = json.loads(raw)
    except ValueError:
        return None
    return value if isinstance(value, dict) and isinstance(value.get("state"), dict) else None


def _save(db, org_id: int, value: dict, actor: str | None) -> None:
    try:
        secrets.set_secret(db, org_id, SECRET, json.dumps(value), actor)
    except secrets.SecretsError as e:
        raise AsuError(str(e), 409) from e


def subscribed(db, org_id: int) -> bool:
    """Whether the org subscribes to the ASU submodule. Only those orgs can sign in to ASU."""
    from modules.submodules.service import subscribed_names

    return SUBMODULE in subscribed_names(db, org_id)


def require_subscribed(db, org_id: int) -> None:
    if not subscribed(db, org_id):
        raise AsuError(NOT_SUBSCRIBED, 404)


def usable(db, org_id: int) -> bool:
    """Whether the API has the browser, the org subscribes to ASU and saved an ASU session. The session can be
    expired."""
    return browsers.missing() is None and subscribed(db, org_id) and _saved(db, org_id) is not None


def status(db, org_id: int) -> dict:
    """The org's ASU sign-in: whether it is signed in, who signed in and when, and the latest attempt."""
    saved = _saved(db, org_id) or {}
    with _lock:
        attempt = _attempts.get(org_id)
        current = asdict(attempt) if attempt else None
    return {
        "title": "ASU",
        "signed_in": bool(saved) and not saved.get("expired_at"),
        "signed_in_by": saved.get("signed_in_by"),
        "signed_in_at": saved.get("signed_in_at"),
        "expired_at": saved.get("expired_at"),
        "blocked": blocked(),
        "attempt": current,
    }


def start(db, org_id: int, netid: object, password: object, actor: str | None) -> dict:
    """Starts a sign-in attempt in a thread and returns the status. Raises AsuError when it cannot start."""
    require_subscribed(db, org_id)
    if not isinstance(netid, str) or not netid.strip() or len(netid) > MAX_NETID:
        raise AsuError("Send netid, your ASU NetID")
    if not isinstance(password, str) or not password or len(password) > MAX_PASSWORD:
        raise AsuError("Send password, your ASU password")
    reason = blocked()
    if reason:
        raise AsuError(reason, 409)
    with _lock:
        current = _attempts.get(org_id)
        if current is not None and current.state in ("running", "duo_code"):
            raise AsuError("A sign-in is already running. Wait for it to finish", 409)
        _attempts[org_id] = Attempt(state="running", message="Opening the ASU sign-in page.", started_at=_now())
    spawn(_run, org_id, netid.strip(), password, actor)
    return status(db, org_id)


def _update(org_id: int, **changes) -> None:
    with _lock:
        attempt = _attempts.get(org_id)
        if attempt is None:
            return
        for name, value in changes.items():
            setattr(attempt, name, value)


def _scrub(text: str, *values: str) -> str:
    for value in values:
        if value:
            text = text.replace(value, "***")
    return text


def _run(org_id: int, netid: str, password: str, actor: str | None) -> None:
    """One sign-in attempt. Saves the session on success. Never raises."""

    def report(message: str, code: str | None) -> None:
        if code:
            _update(org_id, state="duo_code", code=code, message=_scrub(message, netid, password))
        else:
            _update(org_id, message=_scrub(message, netid, password))

    try:
        state = browser().sign_in(netid, password, report)
        value = {"state": state, "signed_in_by": actor, "signed_in_at": _now(), "expired_at": None}
        with session() as db:
            _save(db, org_id, value, actor)
    except BadPassword:
        _fail(org_id, "ASU did not accept the NetID or the password")
        return
    except (SignInFailed, AsuError) as e:
        _fail(org_id, _scrub(str(e), netid, password))
        return
    except Exception as e:
        logger.warning("asu sign-in failed org=%s error=%s", org_id, type(e).__name__)
        _fail(org_id, "The sign-in failed on the API. See the error log")
        return
    _update(org_id, state="done", code=None, message="Signed in to ASU.", finished_at=_now())
    logger.info("asu sign-in saved org=%s", org_id)


def _fail(org_id: int, reason: str) -> None:
    _update(org_id, state="failed", code=None, reason=reason, message=reason, finished_at=_now())
    logger.info("asu sign-in failed org=%s", org_id)


def sign_out(db, org_id: int) -> dict:
    """Removes the saved session and the latest attempt."""
    secrets.delete_secret(db, org_id, SECRET)
    with _lock:
        attempt = _attempts.get(org_id)
        if attempt is not None and attempt.state not in ("running", "duo_code"):
            del _attempts[org_id]
    return status(db, org_id)


def _expire(db, org_id: int, org_prefix: str) -> None:
    """Marks the saved session expired and sends asu.session_expired, one time for each expiry."""
    with _expiry:
        saved = _saved(db, org_id)
        if saved is None or saved.get("expired_at"):
            return
        saved["expired_at"] = _now()
        _save(db, org_id, saved, saved.get("signed_in_by"))
    link = (
        f"{config.DASHBOARD_URL}/{org_prefix}/explore?tab=submodules" if config.DASHBOARD_URL and org_prefix else None
    )
    message = webhooks.Message(
        title="ASU sign-in expired",
        text="Agents cannot read Sun Devil Central. Sign in again on the ASU card of Explore, Submodules.",
        url=link,
        color=webhooks.AMBER,
        footer="Submodules",
    )
    webhooks.emit(org_id, "asu.session_expired", message)
    logger.info("asu session expired org=%s", org_id)


def read(db, org_id: int, org_prefix: str, url: str) -> Fetched:
    """The page at url, loaded with the org's ASU session. Raises SessionExpired when the session has expired."""
    require_subscribed(db, org_id)
    saved = _saved(db, org_id)
    if saved is None:
        raise AsuError(NOT_SIGNED_IN, 409)
    if saved.get("expired_at"):
        raise SessionExpired(EXPIRED, 409)
    try:
        loaded = browser().load(saved["state"], url)
    except LoadFailed as e:
        raise AsuError(f"Sun Devil Central did not load: {e}", 502) from e
    if sso.is_login_url(loaded.url):
        _expire(db, org_id, org_prefix)
        raise SessionExpired(EXPIRED, 409)
    if loaded.state is not None:
        _save(db, org_id, {**saved, "state": loaded.state}, saved.get("signed_in_by"))
    if loaded.status == 0 or loaded.status >= 400:
        raise AsuError(f"Sun Devil Central answered {loaded.status or 'nothing'} for {url}", 502)
    return Fetched(url=loaded.url, body=loaded.html.encode("utf-8"), content_type="text/html")
