"""Pages that need JavaScript, rendered in the deployment's shared browser. No Flask here.

BROWSER_URL names a Playwright server, the browser compose service. When a plain GET returns a page with
little text, fetch() loads it again there and keeps the rendered page. Each render opens a new browser
context, which holds its own cookies and storage, and closes it after the page. The browser loads only
http(s) URLs on public addresses and skips images, media and fonts.

An org's renders count against knowledge.renders_per_day, which is 0 by default: an org renders pages only
after the superadmin raises its limit. Pages of a shared submodule count against no org. At most
BROWSER_MAX_PAGES renders run at one time in a process; the others wait.
"""

import importlib
import os
import threading
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from typing import Any

from core import limits, net
from core.log import get_logger
from modules.knowledge import extract, fetch
from modules.knowledge.fetch import Fetched, FetchError

logger = get_logger(__name__)

RENDERS_LIMIT = "knowledge.renders_per_day"
limits.declare(RENDERS_LIMIT, "knowledge", "Pages rendered with JavaScript a day", 0, window="day", unit="pages")

NAV_MS = 30_000
CONNECT_MS = 10_000
# Requests of these types are not loaded.
SKIPPED = frozenset({"image", "media", "font"})
# Pages that tell the reader to turn on JavaScript are rendered whatever their length.
NOSCRIPT_CUES = ("enable javascript", "javascript is required", "javascript is disabled", "turn on javascript")


def _env_int(name: str, default: int) -> int:
    try:
        value = int(os.environ.get(name, default))
    except ValueError:
        return default
    return value if value > 0 else default


THIN_CHARS = _env_int("KNOWLEDGE_RENDER_THIN_CHARS", 400)
_open = threading.BoundedSemaphore(_env_int("BROWSER_MAX_PAGES", 2))


def browser_url() -> str:
    """The Playwright server of the deployment, or an empty string when there is none."""
    return os.environ.get("BROWSER_URL", "").strip()


def is_thin(page: Fetched) -> bool:
    """Whether an HTML page has too little text to keep without rendering it."""
    if page.text is not None or (page.content_type and "html" not in page.content_type.lower()):
        return False
    text = extract.extract_text(page.body)
    if len(text) < THIN_CHARS:
        return True
    lowered = page.body[:200_000].decode("utf-8", "replace").lower()
    return "<noscript" in lowered and any(cue in lowered for cue in NOSCRIPT_CUES)


def allowed_request(url: str) -> bool:
    """Whether the browser may load url: data and blob URLs, and http(s) on public addresses."""
    if url.startswith(("data:", "blob:")):
        return True
    try:
        net.check_public(url)
    except (net.NotPublic, net.NoHost):
        return False
    return True


def _guard(route: Any) -> None:
    request = route.request
    if request.resource_type in SKIPPED or not allowed_request(request.url):
        route.abort()
    else:
        route.continue_()


def render(url: str, server: str) -> Fetched:
    """url loaded in a new context of the browser at server. Raises FetchError when it does not load."""
    api = importlib.import_module("playwright.sync_api")
    Error = api.Error

    with _open, api.sync_playwright() as playwright:
        try:
            browser = playwright.chromium.connect(server, timeout=CONNECT_MS)
        except Error as e:
            raise FetchError("The browser could not be reached") from e
        try:
            context = browser.new_context(user_agent=fetch.USER_AGENT, service_workers="block", accept_downloads=False)
            try:
                context.route("**/*", _guard)
                page = context.new_page()
                response = page.goto(url, wait_until="networkidle", timeout=NAV_MS)
                status = response.status if response else 0
                if status >= 400:
                    raise FetchError(f"{url} returned {status} in the browser")
                html = page.content().encode()
                final = page.url
            finally:
                context.close()
        except Error as e:
            raise FetchError(f"{url} did not load in the browser") from e
        finally:
            browser.close()
    if len(html) > fetch.MAX_BYTES:
        raise FetchError(f"{url} is larger than {fetch.MAX_BYTES} bytes in the browser")
    return Fetched(url=final, body=html, content_type="text/html")


def hook(server: str, meter: Callable[[], bool] | None) -> fetch.Renderer:
    """The function fetch() calls after a GET: it renders a thin page, or one asked for, while meter allows it."""

    def apply(page: Fetched, wanted: bool) -> Fetched:
        if not (wanted or is_thin(page)):
            return page
        if meter is not None and not meter():
            return page
        try:
            return render(page.url, server)
        except FetchError as e:
            logger.warning("render failed url=%s error=%s", page.url, e)
            return page

    return apply


def _meter(db, org_id: int) -> Callable[[], bool]:
    def allow() -> bool:
        try:
            limits.consume(db, org_id, RENDERS_LIMIT)
        except limits.LimitError:
            return False
        return True

    return allow


@contextmanager
def scope(db, org_id: int | None) -> Iterator[None]:
    """fetch() inside the block renders thin pages in the browser, counted against org_id when it is set."""
    server = browser_url()
    if not server:
        yield
        return
    with fetch.render_scope(hook(server, _meter(db, org_id) if org_id is not None else None)):
        yield
