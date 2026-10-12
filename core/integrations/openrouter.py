"""The OpenRouter integration: an org API key for OpenRouter's OpenAI-compatible API. No Flask here.

The org's key replaces OPENROUTER_API_KEY from Doppler. The Embeddings integration uses this key when its base
URL is BASE_URL and it has no key of its own.
"""

import os
from urllib.parse import urlsplit

import requests

from core import secrets
from core.integrations.registry import Field, Integration, IntegrationError, register

SECRET_NAME = "openrouter_api_key"  # nosec B105 - the name of an org secret, not its value
BASE_URL = "https://openrouter.ai/api/v1"
HOST = "openrouter.ai"
TIMEOUT_SECONDS = 10


def deployment_key() -> str | None:
    """The deployment default key from Doppler, or None."""
    return os.environ.get("OPENROUTER_API_KEY", "").strip() or None


def key_for(db, org_id: int) -> str | None:
    """The org's OpenRouter key, else the deployment default, else None."""
    return secrets.get_secret(db, org_id, SECRET_NAME) or deployment_key()


def is_openrouter(url: str) -> bool:
    """Whether url is an https URL on OpenRouter's host."""
    parts = urlsplit(url.strip())
    return parts.scheme == "https" and (parts.hostname or "").lower() == HOST


def _test(db, org_id: int) -> str:
    key = key_for(db, org_id)
    if not key:
        raise IntegrationError("Set an OpenRouter API key first")
    try:
        response = requests.get(
            f"{BASE_URL}/key",
            headers={"Authorization": f"Bearer {key}"},
            timeout=TIMEOUT_SECONDS,
            allow_redirects=False,
        )
    except requests.RequestException as e:
        raise IntegrationError("OpenRouter could not be reached") from e
    if response.status_code == 401:
        raise IntegrationError("OpenRouter refused the key")
    if response.status_code != 200:
        raise IntegrationError(f"OpenRouter answered {response.status_code}")
    try:
        data = response.json().get("data") or {}
    except (ValueError, AttributeError):
        data = {}
    label = data.get("label")
    # A key with no name has a label that shows part of the key
    named = f" as {label}" if isinstance(label, str) and label and not label.startswith("sk-") else ""
    remaining = data.get("limit_remaining")
    if data.get("limit") is None:
        return f"Connected{named}. The key has no credit limit."
    if isinstance(remaining, (int, float)):
        return f"Connected{named}. {remaining:g} credits left of {data['limit']:g}."
    return f"Connected{named}."


register(
    Integration(
        key="openrouter",
        title="OpenRouter",
        description="Connect an OpenRouter account for hosted models.",
        fields=(
            Field(
                SECRET_NAME,
                "API key",
                "OpenRouter > Settings > API Keys. Embeddings uses this key when its base URL is OpenRouter.",
            ),
        ),
        docs="codebase/integrations",
        deployment=lambda: deployment_key() is not None,
        test=_test,
    )
)
