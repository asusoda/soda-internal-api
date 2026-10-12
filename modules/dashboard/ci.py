"""Recent GitHub Actions runs for the repositories an organization lists. No Flask here.

The list is the org config key dashboard.repos. Private repositories need the org secret
github_token. Responses are cached per repository for CACHE_SECONDS.
"""

import re
import time
from typing import cast

import requests
from sqlalchemy.orm.attributes import flag_modified

from core import secrets
from core.errors import ServiceError
from core.integrations import github, registry
from modules.organizations.models import Organization

REPO_PATTERN = re.compile(r"^[A-Za-z0-9_-][A-Za-z0-9_.-]*/[A-Za-z0-9_-][A-Za-z0-9_.-]*$")
MAX_REPOS = 20
RUNS_PER_REPO = 5
CACHE_SECONDS = 120
GITHUB_SECRET = github.SECRET_NAME
registry.use("github", "dashboard")

_cache: dict[tuple[int, str], tuple[float, dict]] = {}


class DashboardError(ServiceError, ValueError):
    pass


def repos(org: Organization) -> list[str]:
    config = cast(dict, org.config) or {}
    return list((config.get("dashboard") or {}).get("repos") or [])


def set_repos(db, org: Organization, value: object) -> list[str]:
    """Replace the org's repository list. Commits."""
    if not isinstance(value, list) or len(value) > MAX_REPOS:
        raise DashboardError(f"repos must be a list of up to {MAX_REPOS} owner/name strings")
    cleaned = []
    for repo in value:
        if not isinstance(repo, str) or not REPO_PATTERN.match(repo):
            raise DashboardError(f"Not an owner/name repository: {repo}")
        if repo not in cleaned:
            cleaned.append(repo)
    config = dict(cast(dict, org.config) or {})
    config["dashboard"] = {**(config.get("dashboard") or {}), "repos": cleaned}
    org.config = config
    flag_modified(org, "config")
    db.commit()
    return cleaned


def fetch_runs(repo: str, token: str | None) -> dict:
    """The latest workflow runs of one repository, or an error message."""
    headers = {"Accept": "application/vnd.github+json", "X-GitHub-Api-Version": "2022-11-28"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    try:
        response = requests.get(
            f"https://api.github.com/repos/{repo}/actions/runs",
            params={"per_page": RUNS_PER_REPO},
            headers=headers,
            timeout=10,
        )
    except requests.RequestException as e:
        return {"repo": repo, "runs": [], "error": f"GitHub unreachable: {e}"}
    if response.status_code == 404:
        return {"repo": repo, "runs": [], "error": "Not found; private repositories need the github_token secret"}
    if response.status_code != 200:
        return {"repo": repo, "runs": [], "error": f"GitHub answered {response.status_code}"}
    runs = [
        {
            "workflow": run.get("name"),
            "branch": run.get("head_branch"),
            "event": run.get("event"),
            "status": run.get("status"),
            "conclusion": run.get("conclusion"),
            "title": run.get("display_title"),
            "url": run.get("html_url"),
            "started_at": run.get("run_started_at") or run.get("created_at"),
        }
        for run in response.json().get("workflow_runs", [])
    ]
    return {"repo": repo, "runs": runs, "error": None}


def runs(db, org: Organization) -> dict:
    """Latest runs for every listed repository."""
    org_id = org.id
    token = secrets.get_secret(db, org_id, GITHUB_SECRET)
    now = time.monotonic()
    result = []
    for repo in repos(org):
        cached = _cache.get((org_id, repo))
        if cached and cached[0] > now:
            result.append(cached[1])
            continue
        entry = fetch_runs(repo, token)
        _cache[(org_id, repo)] = (now + CACHE_SECONDS, entry)
        result.append(entry)
    return {"repos": result}


def clear_cache() -> None:
    _cache.clear()
