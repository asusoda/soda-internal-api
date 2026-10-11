"""Job postings from the markdown table in a GitHub repository's README.

The table has the columns Company, Role, Location, Application or Link, and Date Posted, as in
the internship and new grad lists that SimplifyJobs and vanshb03 keep. A role marked with a lock
is closed. Rows that start with an arrow belong to the company in the row above.
"""

import datetime
import hashlib
import re
from urllib.parse import parse_qsl, urlencode, urlparse, urlunparse

from modules.feeds.types import Fetch, Item, SourceError

REPO_PATTERN = re.compile(r"^[A-Za-z0-9_-][A-Za-z0-9_.-]*/[A-Za-z0-9_-][A-Za-z0-9_.-]*$")
PATH_PATTERN = re.compile(r"^[A-Za-z0-9_./-]+\.md$")
HEADER = re.compile(
    r"\|\s*Company\s*\|\s*Role\s*\|\s*Location\s*\|\s*Application/?\s*Link\s*\|\s*Date Posted\s*\|", re.I
)
SEPARATOR = re.compile(r"^\|[\s\-:|]+\|$")
TRACKING_PARAMS = {"utm_source", "utm_medium", "utm_campaign", "ref", "source"}
CLOSED = "\U0001f512"
NO_SPONSORSHIP = "\U0001f6c2"
CITIZENSHIP = "\U0001f1fa\U0001f1f8"
SUBSIDIARY = "↳"


def validate(config: dict) -> dict:
    """The feed config with defaults filled in. Raises ValueError on a bad value."""
    repo = str(config.get("repo", ""))
    if not REPO_PATTERN.match(repo):
        raise ValueError("repo must be owner/name of a GitHub repository")
    path = str(config.get("path", "README.md"))
    branch = str(config.get("branch", "main"))
    if not PATH_PATTERN.match(path) or ".." in path or not re.match(r"^[A-Za-z0-9_./-]+$", branch):
        raise ValueError("path must be a .md file and branch a branch name")
    max_age_days = config.get("max_age_days", 2)
    if not isinstance(max_age_days, int) or not 0 <= max_age_days <= 365:
        raise ValueError("max_age_days must be an integer from 0 to 365")
    return {
        "repo": repo,
        "branch": branch,
        "path": path,
        "label": str(config.get("label", "Job"))[:50],
        "skip_closed": config.get("skip_closed", True) is not False,
        "max_age_days": max_age_days,
    }


def fetch(config: dict, get: Fetch, today: datetime.date) -> list[Item]:
    """Open postings in the table, newest rows as the README lists them."""
    url = f"https://raw.githubusercontent.com/{config['repo']}/{config['branch']}/{config['path']}"
    rows = parse(get(url))
    if not rows:
        raise SourceError("No job table found in the README")
    items = []
    for row in rows:
        if config["skip_closed"] and row["closed"]:
            continue
        if config["max_age_days"] and not posted_within(row["date_posted"], config["max_age_days"], today):
            continue
        items.append(_item(row, config))
    return items


def parse(markdown: str) -> list[dict]:
    """Rows of the first job table in the markdown. Rows without a company, role or link are skipped."""
    header = HEADER.search(markdown)
    if header is None:
        return []
    rows = []
    company = ""
    for line in markdown[header.end() :].splitlines():
        line = line.strip()
        if not line:
            continue
        if not line.startswith("|"):
            break
        if SEPARATOR.match(line):
            continue
        cells = [c.strip() for c in line.split("|")]
        if len(cells) < 6:
            continue
        name = clean(cells[1])
        company = company if name in ("", SUBSIDIARY) else name
        role_raw = cells[2]
        role = re.sub(f"[{CLOSED}{NO_SPONSORSHIP}]|{CITIZENSHIP}", "", clean(role_raw)).strip()
        link = first_url(cells[4])
        if not company or not role or not link:
            continue
        rows.append(
            {
                "company": company,
                "role": role,
                "location": clean(cells[3]),
                "url": link,
                "date_posted": clean(cells[5]),
                "closed": CLOSED in role_raw,
                "no_sponsorship": NO_SPONSORSHIP in role_raw,
                "requires_citizenship": CITIZENSHIP in role_raw,
            }
        )
    return rows


def clean(text: str) -> str:
    """Cell text without HTML tags, markdown emphasis and links, and extra spaces."""
    text = re.sub(r"</?br\s*/?>", " / ", text, flags=re.I)
    text = re.sub(r"<[^>]+>", "", text)
    text = re.sub(r"\*\*(.+?)\*\*", r"\1", text)
    text = re.sub(r"\[(.+?)\]\(.+?\)", r"\1", text)
    return " ".join(text.split())


def first_url(cell: str) -> str | None:
    """The application link in a cell: an anchor href, a markdown link target or a bare URL."""
    for pattern in (r"<a\s+href=[\"']([^\"']+)[\"']", r"\]\((https?://[^)\s]+)\)", r"(https?://[^\s)\"'<>]+)"):
        match = re.search(pattern, cell, re.I)
        if match and match.group(1).startswith(("https://", "http://")):
            return match.group(1)
    return None


def posted_within(date_posted: str, days: int, today: datetime.date) -> bool:
    """Whether a date like "Oct 06" is at most days before today. A date after today is last year's."""
    try:
        posted = datetime.datetime.strptime(f"{date_posted} {today.year}", "%b %d %Y").date()
    except ValueError:
        return False
    if posted > today:
        posted = posted.replace(year=today.year - 1)
    return (today - posted).days <= days


def without_tracking(url: str) -> str:
    """The URL without utm and ref query parameters."""
    parsed = urlparse(url)
    query = [(k, v) for k, v in parse_qsl(parsed.query) if k not in TRACKING_PARAMS]
    return urlunparse(parsed._replace(query=urlencode(query)))


def item_key(row: dict) -> str:
    """A stable id for a posting from its company, role, first location and link."""
    location = row["location"].split("/")[0].strip().lower()
    composite = f"{row['company'].lower()}|{row['role'].lower()}|{location}|{without_tracking(row['url'])}"
    return hashlib.sha256(composite.encode()).hexdigest()[:16]


def _item(row: dict, config: dict) -> Item:
    fields = [("Company", row["company"]), ("Role", row["role"]), ("Location", row["location"] or "Not listed")]
    notes = []
    if row["no_sponsorship"]:
        notes.append("No visa sponsorship")
    if row["requires_citizenship"]:
        notes.append("Requires U.S. citizenship")
    if notes:
        fields.append(("Requirements", "\n".join(notes)))
    return Item(
        key=item_key(row),
        title=f"New {config['label']}: {row['company']}",
        url=row["url"],
        fields=fields,
        footer=f"Source: github.com/{config['repo']}",
    )
