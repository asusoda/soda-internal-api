"""Module categories, and the modules that hold models, jobs and tools.

Flask-free, so alembic, the worker and MCP can load it.
"""

import importlib
from dataclasses import dataclass

# Each module and its category. modules/ stays flat; the categories group modules in modules/README.md and on the
# Explore page of the dashboard. Core modules are always on and do not show on Explore.
CATEGORIES = {
    "Core": [
        "alerts",
        "auth",
        "bot",
        "dashboard",
        "mcp",
        "organizations",
        "public",
        "submodules",
        "superadmin",
        "users",
    ],
    "Storage": ["knowledge", "points", "storefront", "accounts"],
    "AI and agents": ["agents", "integrations"],
    "Automations": ["feeds", "calendar", "uptime"],
    "Bots": ["leetcode", "games"],
    "Compute": ["godfather", "runpod"],
}

CORE = "Core"


@dataclass(frozen=True)
class Need:
    """An integration or a setting that a module needs."""

    # The key of an integration in core.integrations.registry, or the name of a setting in Doppler
    key: str
    # The name the dashboard shows, such as "Google service account"
    label: str
    # integration or setting
    kind: str = "integration"
    # The module works without it, with fewer functions
    optional: bool = False


@dataclass(frozen=True)
class ModuleInfo:
    """How the Explore page of the dashboard shows a module."""

    title: str
    description: str
    needs: tuple[Need, ...] = ()
    # The submodules in submodules/ that the module reads
    submodules: tuple[str, ...] = ()


DISCORD_BOT = Need("discord", "Discord bot")
RUNPOD = Need("runpod", "RunPod")

# Each module as the dashboard shows it. tests/test_module_layout.py checks that each module has an entry.
CATALOG = {
    "accounts": ModuleInfo(
        "Member accounts",
        "Members connect Canvas, Google and Outlook, and agents read them for the member.",
        needs=(Need("ACCOUNTS_BASE_URL", "ACCOUNTS_BASE_URL setting", kind="setting"),),
    ),
    "agents": ModuleInfo(
        "Agent memory",
        "Conversations, memories and pending actions that the org's agents keep for each member, through the API.",
        needs=(Need("openrouter", "OpenRouter", optional=True),),
    ),
    "auth": ModuleInfo(
        "Sign-in", "Discord sign-in for officers and members, tokens and access checks.", (DISCORD_BOT,)
    ),
    "bot": ModuleInfo("Discord bot", "The Discord bot that runs the commands of other modules.", (DISCORD_BOT,)),
    "calendar": ModuleInfo(
        "Calendar sync",
        "Copies Notion events to Google Calendar and the public events feed.",
        needs=(Need("notion", "Notion"), Need("google", "Google service account")),
    ),
    "godfather": ModuleInfo("Godfather", "GPU and CPU pods that members connect to with the Godfather CLI.", (RUNPOD,)),
    "dashboard": ModuleInfo("Dashboard", "This dashboard: overview, activity, errors and branding."),
    "alerts": ModuleInfo(
        "Alerts", "Sends events of the org, such as a failed job or a site that is down, to its Discord channels."
    ),
    "feeds": ModuleInfo(
        "Feeds",
        "Posts new internship and new grad roles from GitHub job lists, and upcoming hackathons, to Discord channels.",
        submodules=("careers",),
    ),
    "games": ModuleInfo("Games", "Jeopardy games in the org's Discord server.", (DISCORD_BOT,)),
    "integrations": ModuleInfo("Integration tools", "Gives agents the tools of the services that the org connects."),
    "knowledge": ModuleInfo(
        "Knowledge",
        "Pages and documents that agents search, with crawls on a schedule.",
        needs=(
            Need("embeddings", "Embeddings service", optional=True),
            Need("firecrawl", "Firecrawl", optional=True),
        ),
        submodules=("asu",),
    ),
    "leetcode": ModuleInfo(
        "LeetCode", "Posts the daily LeetCode question in a Discord channel and checks who solved it.", (DISCORD_BOT,)
    ),
    "mcp": ModuleInfo("MCP", "The MCP server that gives agents and apps the tools of each module."),
    "organizations": ModuleInfo("Organizations", "The org record, module switches, secrets and machine tokens."),
    "submodules": ModuleInfo(
        "Shared content",
        "Content made once for every org: campus pages and live queries for Knowledge, and job and hackathon sources "
        "for Feeds. The code name is submodules.",
        needs=(Need("searxng", "Web search (SearXNG)", optional=True),),
        submodules=("asu", "careers"),
    ),
    "points": ModuleInfo("Points", "Points, leaderboards and event check-ins."),
    "public": ModuleInfo("Public pages", "Open routes for the leaderboard, the member list and stats."),
    "runpod": ModuleInfo(
        "Hosting",
        "Deploys the org's apps to a hosting provider, and rolls back to an earlier tag.",
        needs=(RUNPOD, Need("github", "GitHub", optional=True)),
    ),
    "storefront": ModuleInfo("Store", "A merch store that members pay for with points."),
    "superadmin": ModuleInfo("Superadmin", "Orgs for the whole deployment. Only the superadmin uses it."),
    "uptime": ModuleInfo(
        "Uptime", "Checks the org's sites and Hosting apps, with an event when one goes down or comes back."
    ),
    "users": ModuleInfo("Member list", "The members of the org and their profile fields."),
}

# The modules that a new org starts with, in addition to Core. Each other module that an org can switch off starts off.
NEW_ORG_MODULES: tuple[str, ...] = ()


# Importing these puts every table in Base.metadata (alembic/env.py, tests/conftest.py)
MODEL_MODULES = [
    "core.audit",
    "core.error_log",
    "core.limits",
    "core.secrets",
    "core.webhooks",
    "modules.accounts.models",
    "modules.feeds.models",
    "modules.agents.models",
    "modules.auth.models",
    "modules.games.models",
    "modules.knowledge.models",
    "modules.leetcode.models",
    "modules.mcp.models",
    "modules.calendar.models",
    "modules.godfather.models",
    "modules.organizations.models",
    "modules.points.models",
    "modules.runpod.models",
    "modules.storefront.models",
    "modules.submodules.models",
    "modules.superadmin.models",
    "modules.uptime.models",
    "modules.users.models",
]

# Importing a jobs module registers its jobs with core.jobs
JOB_MODULES = [
    "core.audit",
    "core.error_log",
    "core.limits",
    "modules.auth.jobs",
    "modules.points.jobs",
    "modules.calendar.jobs",
    "modules.agents.jobs",
    "modules.accounts.jobs",
    "modules.runpod.jobs",
    "modules.knowledge.jobs",
    "modules.submodules.jobs",
    "modules.leetcode.jobs",
    "modules.godfather.jobs",
    "modules.feeds.jobs",
    "modules.uptime.jobs",
    "modules.mcp.jobs",
]

# Importing a tools module registers its tools with core.tools
TOOL_MODULES = [
    "modules.organizations.tools",
    "modules.calendar.tools",
    "modules.points.tools",
    "modules.knowledge.tools",
    "modules.runpod.tools",
    "modules.submodules.tools",
    "modules.dashboard.tools",
    "modules.alerts.tools",
    "modules.feeds.tools",
    "modules.godfather.tools",
    "modules.integrations.tools",
    "modules.accounts.tools",
    "modules.uptime.tools",
    "modules.users.tools",
    "modules.storefront.tools",
    "modules.leetcode.tools",
    "submodules.asu.signin.tools",
]


def _load(names: list[str]) -> None:
    for name in names:
        importlib.import_module(name)


def load_models() -> None:
    _load(MODEL_MODULES)


def load_jobs() -> None:
    """Every model, then every job. A job can query any table."""
    load_models()
    _load(JOB_MODULES)


def load_tools() -> None:
    """Every model, then every tool. A tool can query any table."""
    load_models()
    _load(TOOL_MODULES)
