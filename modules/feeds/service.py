"""Feeds: read a source on a schedule and post new items to an alert destination (a Discord webhook). No Flask here.

The kinds of feed are github_jobs (github_jobs.py: the job table of a GitHub README) and hackathons
(hackathons.py: Hack Club, Euro-Hackathons and Hackalist). Every kind belongs to the feeds module; when the
org has it off, its feeds are hidden and do not run. The presets come from the submodules the org subscribes to.

A feed's first run records every current item without posting, so turning a feed on does not
flood the channel. Later runs post items not seen before. The URL is the destination's, encrypted with
SECRETS_KEY and never returned by a route. A feed made before destinations has the org secret alert_webhook_<key>.
"""

import datetime
import re
import time
from typing import cast

import requests
from sqlalchemy.exc import IntegrityError

from core import limits, secrets, webhooks
from core.errors import ServiceError
from core.log import get_logger
from core.time import utcnow
from modules.auth import scopes
from modules.feeds import github_jobs as jobs_table
from modules.feeds import hackathons
from modules.organizations import service as organizations
from modules.organizations.models import Organization

from .models import AlertFeed, AlertPost, AlertRun
from .types import Item, SourceError

logger = get_logger("feeds")

scopes.declare("feeds:manage", "List, create, change, run and delete the org's feeds")

KEY_PATTERN = re.compile(r"^[a-z0-9][a-z0-9-]{0,39}$")
WEBHOOK_PATTERN = re.compile(r"^https://(?:discord|discordapp)\.com/api/webhooks/\d+/[\w-]+$")
SECRET_PREFIX = "alert_webhook_"  # nosec B105 - a secret name prefix, not a value
KINDS = {"github_jobs": jobs_table, "hackathons": hackathons}
# The module that each kind of feed belongs to
KIND_MODULES = {"github_jobs": "feeds", "hackathons": "feeds"}
MAX_POSTS_PER_RUN = 25
POST_GAP_SECONDS = 0.5
RUNS_KEPT = 50  # runs kept per feed; older ones are deleted
HISTORY_ITEMS = 50
COLORS = {"github_jobs": 0x3447EB, "hackathons": 0x9B59B6}
USER_AGENT = "PlatformFeeds/1.0"

secrets.declare_prefix(SECRET_PREFIX, "Discord webhook URL a feed posts to")

FEEDS_LIMIT = "feeds.feeds"
limits.declare(
    FEEDS_LIMIT,
    "feeds",
    "Feeds",
    20,
    unit="feeds",
    usage=lambda db, org_id: db.query(AlertFeed).filter_by(organization_id=org_id).count(),
)


class FeedError(ServiceError, ValueError):
    pass


def http_get(url: str) -> str:
    """GET a source URL and return its text. Raises SourceError on any failure."""
    try:
        response = requests.get(url, timeout=15, headers={"User-Agent": USER_AGENT})
        response.raise_for_status()
    except requests.RequestException as e:
        raise SourceError(f"{url}: {e}") from e
    return response.text


def post_webhook(url: str, payload: dict) -> None:
    """POST one message to a Discord webhook, waiting once when Discord asks to slow down."""
    for _ in range(2):
        response = requests.post(url, json=payload, timeout=10)
        if response.status_code == 429:
            time.sleep(min(float(response.json().get("retry_after", 1)), 10))
            continue
        response.raise_for_status()
        return
    raise requests.HTTPError("Discord kept rate limiting the webhook")


def embed(item: Item, kind: str) -> dict:
    """The Discord embed for an item."""
    body: dict = {
        "title": item.title[:256],
        "color": COLORS.get(kind, 0),
        "fields": [
            {"name": name, "value": value[:1024] or "-", "inline": len(value) < 40} for name, value in item.fields
        ],
        "timestamp": utcnow().isoformat() + "Z",
    }
    if item.url:
        body["url"] = item.url
    if item.footer:
        body["footer"] = {"text": item.footer[:2048]}
    return body


def _secret_name(key: str) -> str:
    return SECRET_PREFIX + key


def _destination(db, org_id: int, destination_id: int | None) -> webhooks.Webhook | None:
    if destination_id is None:
        return None
    return db.query(webhooks.Webhook).filter_by(organization_id=org_id, id=destination_id).first()


def _webhook(db, feed: AlertFeed) -> str | None:
    """The URL the feed posts to: its alert destination's, else the older alert_webhook_<key> secret."""
    org_id = feed.organization_id
    if feed.destination_id is not None:
        row = _destination(db, org_id, feed.destination_id)
        return secrets.decrypt(str(row.url_ciphertext)) if row is not None and row.enabled else None
    return secrets.get_secret(db, org_id, _secret_name(feed.key))


def kinds_on(db, org_id: int) -> set[str]:
    """The kinds of feed whose module is on for the org."""
    org = db.get(Organization, org_id)
    if org is None:
        return set()
    return {kind for kind, module in KIND_MODULES.items() if organizations.module_enabled(org, module)}


def _find(db, org_id: int, key: str) -> AlertFeed:
    feed = db.query(AlertFeed).filter_by(organization_id=org_id, key=key).first()
    if feed is None or feed.kind not in kinds_on(db, org_id):
        raise FeedError("No feed with that key", 404)
    return feed


def describe(db, feed: AlertFeed) -> dict:
    posted = db.query(AlertPost).filter_by(feed_id=feed.id, posted=True).count()
    return {
        "key": feed.key,
        "kind": feed.kind,
        "config": feed.config,
        "every_hours": feed.every_hours,
        "enabled": feed.enabled,
        "destination_id": feed.destination_id,
        "webhook_set": _webhook(db, feed) is not None,
        "seeded_at": feed.seeded_at.isoformat() if feed.seeded_at else None,
        "last_run_at": feed.last_run_at.isoformat() if feed.last_run_at else None,
        "last_error": feed.last_error,
        "posted": posted,
    }


def list_feeds(db, org_id: int) -> list[dict]:
    on = kinds_on(db, org_id)
    feeds = db.query(AlertFeed).filter_by(organization_id=org_id).order_by(AlertFeed.key).all()
    return [describe(db, f) for f in feeds if f.kind in on]


def presets(db, org_id: int) -> list[dict]:
    """The feeds that the org's subscribed submodules offer, with the kind and config to create each, and whether the
    org has the key."""
    from modules.submodules import catalog
    from modules.submodules.service import subscribed_names

    on = kinds_on(db, org_id)
    mine = subscribed_names(db, org_id)
    have = {key for (key,) in db.query(AlertFeed.key).filter_by(organization_id=org_id)}
    return [
        {
            "module": KIND_MODULES[feed.kind],
            "submodule": submodule.name,
            "submodule_title": submodule.title,
            "key": feed.key,
            "title": feed.title,
            "description": feed.description,
            "kind": feed.kind,
            "config": KINDS[feed.kind].validate(dict(feed.config)),
            "every_hours": feed.every_hours,
            "added": feed.key in have,
        }
        for submodule in catalog.SUBMODULES.values()
        if submodule.name in mine
        for feed in submodule.feeds
        if feed.kind in on
    ]


def get_feed(db, org_id: int, key: str) -> dict:
    return describe(db, _find(db, org_id, key))


def put_feed(db, org_id: int, key: str, body: dict, actor: str | None = None) -> tuple[dict, bool]:
    """Create or update a feed. Returns (feed, created). Commits."""
    if not KEY_PATTERN.match(key):
        raise FeedError("key must be lowercase letters, digits and dashes, up to 40 characters")
    feed = db.query(AlertFeed).filter_by(organization_id=org_id, key=key).first()
    created = feed is None
    if created:
        limits.check(db, org_id, FEEDS_LIMIT)
    kind = body.get("kind", feed.kind if feed else None)
    if kind not in KINDS:
        raise FeedError(f"kind must be one of {', '.join(KINDS)}")
    if kind not in kinds_on(db, org_id):
        raise FeedError(f"The {KIND_MODULES[kind]} feature is off for this organization", 404)
    if feed is not None and kind != feed.kind:
        raise FeedError("A feed's kind cannot change; delete it and create a new one", 409)
    try:
        config = KINDS[kind].validate(body.get("config", feed.config if feed else {}) or {})
    except ValueError as e:
        raise FeedError(str(e)) from e
    every_hours = body.get("every_hours", feed.every_hours if feed else 3)
    if not isinstance(every_hours, int) or not 1 <= every_hours <= 168:
        raise FeedError("every_hours must be an integer from 1 to 168")
    enabled = body.get("enabled", feed.enabled if feed else True)
    if not isinstance(enabled, bool):
        raise FeedError("enabled must be true or false")
    webhook = body.get("webhook_url")
    if webhook is not None and not WEBHOOK_PATTERN.match(str(webhook)):
        raise FeedError("webhook_url must be a Discord webhook URL")
    destination_id = body.get("destination_id", feed.destination_id if feed else None)
    if "destination_id" in body and destination_id is not None:
        destination = (
            _destination(db, org_id, destination_id)
            if isinstance(destination_id, int) and not isinstance(destination_id, bool)
            else None
        )
        if destination is None or destination.kind != "discord":
            raise FeedError("destination_id must be the id of a Discord destination on the Alerts page")
    if (created or "destination_id" in body) and webhook is None and destination_id is None:
        raise FeedError("destination_id is required for a new feed")
    if "destination_id" in body and destination_id is not None:
        # One route per feed: the destination replaces an older webhook secret
        secrets.delete_secret(db, org_id, _secret_name(key))
    elif webhook is not None:
        destination_id = None
        try:
            secrets.set_secret(db, org_id, _secret_name(key), webhook, updated_by=actor)
        except secrets.SecretsError as e:
            raise FeedError(str(e), 503) from e
    if feed is None:
        feed = AlertFeed(organization_id=org_id, key=key, kind=kind)
        db.add(feed)
    feed.config = config
    feed.destination_id = destination_id
    feed.every_hours = every_hours
    feed.enabled = enabled
    db.commit()
    return describe(db, feed), created


def delete_feed(db, org_id: int, key: str) -> None:
    """Delete a feed, its posted items and its webhook secret. Commits."""
    feed = _find(db, org_id, key)
    db.query(AlertPost).filter_by(feed_id=feed.id).delete()
    db.query(AlertRun).filter_by(feed_id=feed.id).delete()
    db.delete(feed)
    db.commit()
    secrets.delete_secret(db, org_id, _secret_name(key))


def run(db, feed: AlertFeed, post_existing: bool = False) -> dict:
    """Read the feed's source and post new items. Commits.

    On the first run, items are recorded without posting unless post_existing is true.
    """
    started = time.monotonic()
    feed.last_run_at = utcnow()
    webhook = _webhook(db, feed)
    if webhook is None:
        return _fail(db, feed, "No destination, the destination is off, or SECRETS_KEY is missing", started)
    try:
        items = _read(feed)
    except SourceError as e:
        return _fail(db, feed, str(e), started)
    seen = {
        k
        for (k,) in db.query(AlertPost.item_key).filter(
            AlertPost.feed_id == feed.id, AlertPost.item_key.in_([i.key for i in items])
        )
    }
    new = list({i.key: i for i in items if i.key not in seen}.values())
    seeding = feed.seeded_at is None and not post_existing
    posted = 0
    error = None
    db.commit()
    for item in new:
        if not seeding and posted >= MAX_POSTS_PER_RUN:
            break
        # The row is written before the post. A run that runs at the same time gets the unique key error and skips it.
        row = AlertPost(feed_id=feed.id, item_key=item.key, title=item.title[:300], posted=not seeding)
        db.add(row)
        try:
            db.commit()
        except IntegrityError:
            db.rollback()
            continue
        if seeding:
            continue
        try:
            post_webhook(webhook, {"embeds": [embed(item, str(feed.kind))]})
        except requests.RequestException as e:
            # Unposted items stay new and go out on the next run
            db.delete(row)
            db.commit()
            error = f"Discord webhook failed: {e}"
            break
        posted += 1
        time.sleep(POST_GAP_SECONDS)
    if feed.seeded_at is None:
        feed.seeded_at = utcnow()
    feed.last_error = error
    _record(db, feed, started, found=len(items), new=len(new), posted=posted, recorded=seeding, error=error)
    db.commit()
    result = {"key": feed.key, "found": len(items), "new": len(new), "posted": posted, "recorded": seeding}
    if error:
        result["error"] = error
    logger.info("feed run org=%s %s", feed.organization_id, result)
    return result


def _read(feed: AlertFeed) -> list[Item]:
    config = cast(dict, feed.config) or {}
    if feed.kind == "github_jobs":
        return jobs_table.fetch(config, http_get, utcnow().date())
    if feed.kind == "hackathons":
        return hackathons.fetch(config, http_get, utcnow())
    raise SourceError(f"Unknown feed kind {feed.kind}")


def _fail(db, feed: AlertFeed, message: str, started: float) -> dict:
    feed.last_error = message[:1000]
    _record(db, feed, started, error=message)
    db.commit()
    logger.warning("feed failed org=%s key=%s: %s", feed.organization_id, feed.key, message)
    return {"key": feed.key, "error": message}


def _record(db, feed: AlertFeed, started: float, error: str | None = None, **counts) -> None:
    """Add a run row for the feed and delete its runs beyond RUNS_KEPT. The caller commits."""
    db.add(
        AlertRun(
            feed_id=feed.id,
            started_at=feed.last_run_at,
            duration_ms=int((time.monotonic() - started) * 1000),
            error=error[:1000] if error else None,
            **counts,
        )
    )
    db.flush()
    old = (
        db.query(AlertRun.id)
        .filter(AlertRun.feed_id == feed.id)
        .order_by(AlertRun.started_at.desc(), AlertRun.id.desc())
        .offset(RUNS_KEPT)
        .all()
    )
    if old:
        db.query(AlertRun).filter(AlertRun.id.in_([i for (i,) in old])).delete(synchronize_session=False)


def history(db, org_id: int, key: str) -> dict:
    """The feed's recent runs and the items it posted or recorded, newest first."""
    feed = _find(db, org_id, key)
    runs = (
        db.query(AlertRun)
        .filter_by(feed_id=feed.id)
        .order_by(AlertRun.started_at.desc(), AlertRun.id.desc())
        .limit(RUNS_KEPT)
        .all()
    )
    items = (
        db.query(AlertPost)
        .filter_by(feed_id=feed.id)
        .order_by(AlertPost.created_at.desc(), AlertPost.id.desc())
        .limit(HISTORY_ITEMS)
        .all()
    )
    return {
        "runs": [
            {
                "started_at": r.started_at.isoformat(),
                "duration_ms": r.duration_ms,
                "found": r.found,
                "new": r.new,
                "posted": r.posted,
                "recorded": r.recorded,
                "error": r.error,
            }
            for r in runs
        ],
        "items": [{"title": i.title, "posted": i.posted, "created_at": i.created_at.isoformat()} for i in items],
    }


def run_now(db, org_id: int, key: str, post_existing: bool = False) -> dict:
    return run(db, _find(db, org_id, key), post_existing=post_existing)


def due(db, now: datetime.datetime | None = None) -> list[AlertFeed]:
    """Enabled feeds whose every_hours has passed, in orgs that have the module of the feed on."""
    now = now or utcnow()
    feeds = []
    rows = (
        db.query(AlertFeed, Organization)
        .join(Organization, Organization.id == AlertFeed.organization_id)
        .filter(AlertFeed.enabled.is_(True), Organization.is_active.is_(True))
        .all()
    )
    for feed, org in rows:
        if not organizations.module_enabled(org, KIND_MODULES[str(feed.kind)]):
            continue
        if feed.last_run_at is None or feed.last_run_at <= now - datetime.timedelta(hours=int(feed.every_hours)):
            feeds.append(feed)
    return feeds


def run_due(db, now: datetime.datetime | None = None) -> dict:
    """Run every due feed. One failing feed does not stop the others. Commits."""
    results = []
    for feed in due(db, now):
        try:
            results.append(run(db, feed))
        except Exception:
            db.rollback()
            logger.exception("feed crashed key=%s", feed.key)
            results.append({"key": feed.key, "error": "crashed"})
    return {"ran": len(results), "failed": sum(1 for r in results if r.get("error"))}
