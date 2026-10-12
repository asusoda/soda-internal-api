"""The outside services an org connects, the keys each one needs, and the modules that use it. No Flask here.

An integration has fields, each one an org secret, so its keys are saved encrypted with core.secrets. Some
integrations have a default for the whole deployment from Doppler; the org's own keys replace it. The org's keys
replace the deployment default as a whole, never field by field. An integration with no fields is set
only in Doppler, and the dashboard shows its state. Modules call register() for the
services they own and use() for the services they read.
"""

import json
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any, cast

from core import limits, net, secrets
from core.errors import ServiceError
from core.log import get_logger

logger = get_logger("integrations")


class IntegrationError(ServiceError):
    """A test of an integration failed. The message says why, with no secret in it."""


@dataclass(frozen=True)
class Field:
    """One key of an integration, saved as the org secret name."""

    name: str
    label: str
    hint: str = ""
    # text: one line; url: an http(s) URL on a public host; json: a JSON document, such as a Google service account key
    kind: str = "text"
    # A secret field is never sent back. Other fields, such as a URL, show their saved value.
    secret: bool = True
    # The org can leave an optional field empty and still use its own keys
    optional: bool = False


@dataclass(frozen=True)
class Integration:
    key: str
    title: str
    description: str
    fields: tuple[Field, ...] = ()
    # The page of the docs site under /docs, such as modules/calendar
    docs: str | None = None
    # Whether Doppler gives a default for the whole deployment
    deployment: Callable[[], bool] | None = None
    # Connects with the org's keys, or the deployment default, and returns a short result
    test: Callable[[object, int], str] | None = None
    used_by: list[str] = field(default_factory=list)
    # Called with the session and org id after the org's keys change
    on_save: Callable[[object, int], None] | None = None


INTEGRATIONS: dict[str, Integration] = {}


def register(integration: Integration) -> None:
    """Add an integration and declare its fields as org secrets."""
    INTEGRATIONS[integration.key] = integration
    for f in integration.fields:
        secrets.declare(f.name, f"{integration.title}: {f.label}")


def use(key: str, module: str) -> None:
    """Record that module reads the integration key."""
    integration = INTEGRATIONS.get(key)
    if integration is not None and module not in integration.used_by:
        integration.used_by.append(module)


def secret_names() -> set[str]:
    """The org secrets that integrations own."""
    return {f.name for i in INTEGRATIONS.values() for f in i.fields}


def status(db, org_id: int) -> list[dict]:
    """Each integration with its fields, whether the org set them, and where the keys come from."""
    saved = {s["name"]: s for s in secrets.list_secrets(db, org_id)}
    result = []
    for i in sorted(INTEGRATIONS.values(), key=lambda x: x.title.lower()):
        fields = []
        set_names: set[str] = set()
        for f in i.fields:
            is_set = bool(saved.get(f.name, {}).get("set"))
            if is_set:
                set_names.add(f.name)
            fields.append(
                {
                    "name": f.name,
                    "label": f.label,
                    "hint": f.hint,
                    "kind": f.kind,
                    "secret": f.secret,
                    "optional": f.optional,
                    "set": is_set,
                    "value": secrets.get_secret(db, org_id, f.name) if is_set and not f.secret else None,
                    "updated_at": saved.get(f.name, {}).get("updated_at"),
                }
            )
        org_set = _org_set(i, set_names)
        deployment = bool(i.deployment and i.deployment())
        result.append(
            {
                "key": i.key,
                "title": i.title,
                "description": i.description,
                "docs": i.docs,
                "fields": fields,
                "editable": bool(fields),
                "source": "org" if org_set else "deployment" if deployment else None,
                # With the deployment's keys, the org's use counts against these limits
                "metered_by": limits.metering(i.key) if not org_set and deployment else [],
                "testable": i.test is not None,
                "used_by": sorted(i.used_by),
            }
        )
    return result


def _org_set(integration: Integration, set_names: set[str]) -> bool:
    required = {f.name for f in integration.fields if not f.optional}
    return bool(set_names) and required <= set_names


def connected(db, org_id: int, key: str) -> bool:
    """Whether the org has its own keys for the integration, or the deployment gives a default."""
    integration = INTEGRATIONS.get(key)
    if integration is None:
        return False
    if org_values(db, org_id, key) is not None:
        return True
    return bool(integration.deployment and integration.deployment())


def org_values(db, org_id: int, key: str) -> dict[str, str] | None:
    """The org's own field values when it set every required field, else None. Optional fields may be missing."""
    integration = INTEGRATIONS.get(key)
    if integration is None or not integration.fields:
        return None
    found = {f.name: v for f in integration.fields if (v := secrets.get_secret(db, org_id, f.name))}
    return found if _org_set(integration, set(found)) else None


def save(db, org_id: int, key: str, values: object, actor: str | None) -> None:
    """Set or clear the fields of an integration. A null value clears that field; a missing key leaves it."""
    integration = INTEGRATIONS.get(key)
    if integration is None or not integration.fields:
        raise IntegrationError("This integration has no keys to set")
    if not isinstance(values, dict) or not values:
        raise IntegrationError("fields must be an object of field names and values")
    names = {f.name for f in integration.fields}
    unknown = set(values) - names
    if unknown:
        raise IntegrationError(f"Unknown fields: {', '.join(sorted(unknown))}")
    changes = cast(dict[str, Any], values)
    kinds = {f.name: f.kind for f in integration.fields}
    for name, value in changes.items():
        if value is not None and kinds[name] == "json" and not _json_object(value):
            raise IntegrationError(f"{name} must be a JSON object")
        if value is not None and kinds[name] == "url":
            try:
                net.check_public(str(value))
            except ValueError as e:
                raise IntegrationError(str(e)) from e
    saved = {s["name"] for s in secrets.list_secrets(db, org_id) if s["set"]} & names
    after = (saved | {n for n, v in changes.items() if v is not None}) - {n for n, v in changes.items() if v is None}
    if after and not _org_set(integration, after):
        missing = [f.label for f in integration.fields if not f.optional and f.name not in after]
        raise IntegrationError(f"Also set: {', '.join(missing)}")
    for name, value in changes.items():
        if value is None:
            secrets.delete_secret(db, org_id, name)
        else:
            try:
                secrets.set_secret(db, org_id, name, value, actor)
            except secrets.SecretsError as e:
                raise IntegrationError(str(e)) from e
    if integration.on_save is not None:
        try:
            integration.on_save(db, org_id)
        except Exception:
            logger.exception("on_save failed integration=%s org=%s", key, org_id)


def _json_object(value: object) -> bool:
    try:
        return isinstance(value, str) and isinstance(json.loads(value), dict)
    except ValueError:
        return False


def test(db, org_id: int, key: str) -> str:
    """Run the integration's test. Raises IntegrationError when it fails."""
    integration = INTEGRATIONS.get(key)
    if integration is None or integration.test is None:
        raise IntegrationError("This integration has no test")
    return integration.test(db, org_id)
