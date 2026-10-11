"""Per-org knowledge settings: how text is split into passages and how search ranks them. No Flask here.

The settings live in the org config under "knowledge". A missing key takes its default. The defaults of
chunk_chars and max_distance come from KNOWLEDGE_CHUNK_CHARS and KNOWLEDGE_MAX_DISTANCE.
"""

import os
from typing import Any, cast

from sqlalchemy.orm.attributes import flag_modified

from modules.knowledge.service import KnowledgeError
from modules.organizations.models import Organization

MODES = ("hybrid", "text", "vector")
CONFIG_KEY = "knowledge"


def _env_int(name: str, default: int) -> int:
    try:
        value = int(os.environ.get(name, default))
    except ValueError:
        return default
    return value if value > 0 else default


def _env_distance() -> float:
    try:
        value = float(os.environ.get("KNOWLEDGE_MAX_DISTANCE", "0.6"))
    except ValueError:
        return 0.6
    return value if 0 < value <= 2 else 0.6


def defaults() -> dict:
    """The settings an org gets when it sets none."""
    return {
        "chunk_chars": _env_int("KNOWLEDGE_CHUNK_CHARS", 300),
        "chunk_overlap": 0,
        "mode": "hybrid",
        "top_k": 8,
        "window": 0,
        "max_distance": _env_distance(),
        "rrf_k": 60,
    }


# Integer settings: (low, high)
_INTS = {"chunk_chars": (100, 4000), "chunk_overlap": (0, 2000), "top_k": (1, 50), "window": (0, 5), "rrf_k": (1, 200)}


def _org(db, org_id: int) -> Organization:
    org = db.query(Organization).filter_by(id=org_id).first()
    if org is None:
        raise KnowledgeError("No such organization", 404)
    return org


def for_org(db, org_id: int | None) -> dict:
    """The org's settings with defaults filled in. None (a shared submodule's source) gives the defaults."""
    org = db.query(Organization).filter_by(id=org_id).first()
    saved = ((cast(dict, org.config) or {}).get(CONFIG_KEY) or {}) if org is not None else {}
    base = defaults()
    return base | {key: value for key, value in saved.items() if key in base}


def _check(key: str, value: Any) -> Any:
    if key in _INTS:
        low, high = _INTS[key]
        if not isinstance(value, int) or isinstance(value, bool) or not low <= value <= high:
            raise KnowledgeError(f"{key} must be an integer from {low} to {high}")
        return value
    if key == "mode":
        if value not in MODES:
            raise KnowledgeError(f"mode must be one of {', '.join(MODES)}")
        return value
    if key == "max_distance":
        if not isinstance(value, int | float) or isinstance(value, bool) or not 0.05 <= value <= 2:
            raise KnowledgeError("max_distance must be a number from 0.05 to 2")
        return float(value)
    raise KnowledgeError(f"Unknown knowledge setting: {key}")


def update(db, org_id: int, changes: object) -> dict:
    """Set the given settings. A null value returns a setting to its default. Commits."""
    if not isinstance(changes, dict) or not changes:
        raise KnowledgeError("Send an object with one or more knowledge settings")
    org = _org(db, org_id)
    config = dict(cast(dict, org.config) or {})
    saved = dict(config.get(CONFIG_KEY) or {})
    for key, value in cast(dict[str, Any], changes).items():
        if value is None:
            if key not in defaults():
                raise KnowledgeError(f"Unknown knowledge setting: {key}")
            saved.pop(key, None)
        else:
            saved[key] = _check(key, value)
    merged = defaults() | saved
    if merged["chunk_overlap"] > merged["chunk_chars"] // 2:
        raise KnowledgeError("chunk_overlap must be at most half of chunk_chars")
    config[CONFIG_KEY] = saved
    org.config = config
    flag_modified(org, "config")
    db.commit()
    return merged
