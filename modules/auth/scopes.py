"""Scopes a machine token can hold. Modules declare the scopes their tools and endpoints check.

A scope with an integration gives tools of that connected service, such as github:read. The Tokens page
groups those scopes under the integration. A scope with uses reaches those integrations through Platform,
such as knowledge:read, which embeds the query with the org's embeddings key. The Tokens page marks them.
"""

SCOPES: dict[str, str] = {}
INTEGRATION_SCOPES: dict[str, str] = {}
SCOPE_USES: dict[str, tuple[str, ...]] = {}


def declare(name: str, description: str, integration: str | None = None, uses: tuple[str, ...] = ()) -> None:
    SCOPES[name] = description
    if integration is not None:
        INTEGRATION_SCOPES[name] = integration
    if uses:
        SCOPE_USES[name] = uses


# The groups of the Tokens page and the MCP consent page, by the part of a scope name before the colon. A scope of an
# integration shows under its integration instead. tests/contract/test_mcp_oauth.py checks that each other scope is in
# a group.
GROUPS: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("Org", ("org", "settings", "activity", "submodules")),
    ("Members", ("members", "points", "store", "accounts", "canvas")),
    ("Content and agents", ("calendar", "knowledge", "feeds", "agents", "asu")),
    ("Hosting", ("apps", "godfather", "uptime")),
    ("Access and keys", ("tokens", "secrets", "integrations", "webhooks")),
)

# Scopes that give tokens, secrets, keys or the access tokens of members. The "Read and write" preset leaves them out.
ADMIN = frozenset({"tokens:manage", "secrets:manage", "integrations:manage", "webhooks:manage", "accounts:token"})


def is_read(name: str) -> bool:
    return name.endswith(":read")


def groups() -> list[tuple[str, list[str]]]:
    """The scopes that no integration owns, in the groups of GROUPS, read scopes first. Other has the rest."""
    order = {prefix: (n, i) for n, (_, prefixes) in enumerate(GROUPS) for i, prefix in enumerate(prefixes)}
    found: list[tuple[str, list[str]]] = [(title, []) for title, _ in GROUPS] + [("Other", [])]
    for name in SCOPES:
        if name not in INTEGRATION_SCOPES:
            found[order.get(name.split(":")[0], (len(GROUPS), 0))[0]][1].append(name)
    for _, names in found:
        names.sort(key=lambda name: (order.get(name.split(":")[0], (0, 0))[1], not is_read(name), name))
    return [(title, names) for title, names in found if names]


def presets() -> dict[str, tuple[str, list[str]]]:
    """The presets of the Tokens page and the consent page: the label of each one and the scopes it chooses."""
    return {
        "read": ("Read only", sorted(s for s in SCOPES if is_read(s))),
        "write": ("Read and write", sorted(s for s in SCOPES if s not in ADMIN)),
        "all": ("All", sorted(SCOPES)),
    }
