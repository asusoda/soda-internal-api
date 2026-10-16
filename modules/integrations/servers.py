"""The MCP servers of connected services that Platform passes tools through to. No Flask here.

A server entry says where the service's MCP server is, how to sign in with the org's saved keys, the scopes
that give its read-only and its other tools, and how to find the repo or page a call acts on. The keys stay
on the server; an agent sees only the tools.
"""

import os
import re
from collections.abc import Callable
from dataclasses import dataclass

from core import secrets
from core.integrations import github, runpod
from modules.auth import machine_tokens, scopes
from modules.integrations import oauth


@dataclass(frozen=True)
class RemoteServer:
    # The integration key; tool names start with it, as github.list_issues
    key: str
    url: Callable[[], str]
    # The headers that sign in with the org's keys, or None when the org has none
    headers: Callable[[object, int], dict[str, str] | None]
    read_scope: str
    write_scope: str
    # The target a call acts on, as owner/name, or None when the arguments name no single target
    target: Callable[[dict], str | None] = lambda arguments: None
    # The name of the token limit that lists the allowed targets, or None when the server has no target limit
    target_limit: str | None = None
    # The integration the server belongs to, when it differs from key, such as google for gmail
    of: str | None = None

    @property
    def integration(self) -> str:
        return self.of or self.key


SERVERS: dict[str, RemoteServer] = {}


def register(server: RemoteServer) -> None:
    SERVERS[server.key] = server


# GitHub

REPO_PATTERN = re.compile(r"^[A-Za-z0-9_.-]+/(?:[A-Za-z0-9_.-]+|\*)$")
TOOL_PATTERN = re.compile(r"^[a-z0-9_.*?-]{1,100}$")
# A GitHub account name and a repo name: one path segment each, never . or ..
OWNER_NAME = re.compile(r"^[A-Za-z0-9_-]{1,100}$")
REPO_NAME = re.compile(r"^[A-Za-z0-9_.-]{1,100}$")
MAX_ITEMS = 50

scopes.declare("github:read", "Read the org's GitHub repos, issues, pull requests and Actions runs", "github")
scopes.declare(
    "github:write", "Create and change issues, pull requests, comments and files on GitHub (with confirm)", "github"
)


def _github_headers(db, org_id: int) -> dict[str, str] | None:
    token = secrets.get_secret(db, org_id, github.SECRET_NAME)
    return {"Authorization": f"Bearer {token}"} if token else None


def _github_target(arguments: dict) -> str | None:
    """owner/repo in lowercase, or None when either is missing or is not one valid name."""
    owner, repo = arguments.get("owner"), arguments.get("repo")
    if not isinstance(owner, str) or not isinstance(repo, str):
        return None
    if not OWNER_NAME.fullmatch(owner) or not REPO_NAME.fullmatch(repo) or repo in (".", ".."):
        return None
    return f"{owner}/{repo}".lower()


def _check_list(value: object, name: str, pattern: re.Pattern, example: str) -> list[str]:
    if not isinstance(value, list) or not value or len(value) > MAX_ITEMS:
        raise machine_tokens.TokenError(f"{name} must be a list of 1 to {MAX_ITEMS} items")
    cleaned = []
    for item in value:
        if not isinstance(item, str) or not pattern.match(item.strip().lower()):
            raise machine_tokens.TokenError(f"Not a valid {name} item: {item}. Example: {example}")
        if item.strip().lower() not in cleaned:
            cleaned.append(item.strip().lower())
    return cleaned


def _github_limits(value: object) -> dict:
    if not isinstance(value, dict) or set(value) - {"repos", "tools"}:
        raise machine_tokens.TokenError("github limits take repos and tools")
    given: dict[str, object] = {str(k): v for k, v in value.items()}
    cleaned = {}
    if given.get("repos") is not None:
        cleaned["repos"] = _check_list(
            given["repos"], "repos", REPO_PATTERN, "theaisocietyasu/bedrock or theaisocietyasu/*"
        )
    if given.get("tools") is not None:
        cleaned["tools"] = _check_list(given["tools"], "tools", TOOL_PATTERN, "github.*issue*")
    return cleaned


machine_tokens.declare_limits("github", ("repos", "tools"), _github_limits)

register(
    RemoteServer(
        key="github",
        url=lambda: os.environ.get("GITHUB_MCP_URL", "https://api.githubcopilot.com/mcp/"),
        headers=_github_headers,
        read_scope="github:read",
        write_scope="github:write",
        target=_github_target,
        target_limit="repos",
    )
)


# RunPod

scopes.declare("runpod:read", "Read the org's RunPod pods, endpoints, templates, volumes and billing", "runpod")
scopes.declare(
    "runpod:write", "Create, change, start, stop and delete pods and endpoints on RunPod (with confirm)", "runpod"
)


def _runpod_headers(db, org_id: int) -> dict[str, str] | None:
    key = secrets.get_secret(db, org_id, runpod.SECRET_NAME)
    return {"Authorization": f"Bearer {key}"} if key else None


register(
    RemoteServer(
        key="runpod",
        url=lambda: os.environ.get("RUNPOD_MCP_URL", "https://mcp.getrunpod.io/"),
        headers=_runpod_headers,
        read_scope="runpod:read",
        write_scope="runpod:write",
    )
)


# Services that take an OAuth sign-in instead of a key. modules/integrations/oauth.py keeps the tokens.


def _oauth_headers(key: str) -> Callable[[object, int], dict[str, str] | None]:
    def headers(db, org_id: int) -> dict[str, str] | None:
        token = oauth.access_token(db, org_id, key)
        return {"Authorization": f"Bearer {token}"} if token else None

    return headers


register(
    RemoteServer(
        key="notion",
        url=lambda: os.environ.get("NOTION_MCP_URL", "https://mcp.notion.com/mcp"),
        headers=_oauth_headers("notion"),
        read_scope="notion:read",
        write_scope="notion:write",
    )
)
for _key, _url, _read, _write in (
    ("gmail", "https://gmailmcp.googleapis.com/mcp/v1", "gmail:read", "gmail:send"),
    ("drive", "https://drivemcp.googleapis.com/mcp/v1", "google:read", "google:write"),
    ("calendar", "https://calendarmcp.googleapis.com/mcp/v1", "google:read", "google:write"),
):
    register(
        RemoteServer(
            key=_key,
            url=lambda url=_url: url,
            headers=_oauth_headers("google"),
            read_scope=_read,
            write_scope=_write,
            of="google",
        )
    )
