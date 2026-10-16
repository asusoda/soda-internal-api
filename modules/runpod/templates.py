"""App templates: ready-made manifests in apps/<name>/platform.app.yaml. No Flask here.

A template file is a manifest with a template block: a title, a summary, a suggested tag and the inputs an
officer fills in. Creating an app from a template fills the inputs, saves secret inputs as org secrets,
and registers the manifest inline through service.put_app.
"""

import copy
import functools
import re
from pathlib import Path
from typing import Any

import jsonschema
import yaml

from core import secrets
from core.log import get_logger

from . import service
from .service import AppError

logger = get_logger(__name__)

ROOT = Path(__file__).resolve().parents[2] / "apps"
FILE = "platform.app.yaml"
INPUT_KINDS = ("image", "env", "secret", "volume", "data_center")
# Kinds that set one field each, so a template has at most one input of each
SINGLE_KINDS = ("image", "volume", "data_center")
MAX_VALUE = 2000

TEMPLATE_SCHEMA: dict = {
    "type": "object",
    "properties": {
        "title": {"type": "string", "minLength": 1, "maxLength": 60},
        "summary": {"type": "string", "minLength": 1, "maxLength": 120},
        "tag": {"type": "string", "pattern": service.TAG_PATTERN.pattern},
        "inputs": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "kind": {"enum": list(INPUT_KINDS)},
                    "key": {"type": "string", "pattern": r"^[A-Z][A-Z0-9_]{0,31}$"},
                    "label": {"type": "string", "minLength": 1, "maxLength": 60},
                    "required": {"type": "boolean"},
                },
                "required": ["kind", "label"],
                "additionalProperties": False,
            },
        },
    },
    "required": ["title", "summary", "inputs"],
    "additionalProperties": False,
}

# Values that stand in for inputs when a template is checked on load
_SAMPLES = {"image": "ghcr.io/example/app", "env": "x", "volume": "vol_example", "data_center": "US-KS-2"}


def _input_key(item: dict) -> str:
    """The key of an input in a create request: the env var name, or the kind for the other kinds."""
    return item["key"] if item["kind"] in ("env", "secret") else item["kind"]


def _secret_name(app: str, key: str) -> str:
    return f"{service.SECRET_PREFIX}{app.replace('-', '_')}_{key.lower()}"


def _fill(name: str, manifest: dict, inputs: list[dict], values: dict[str, str]) -> dict:
    """The manifest with each input that has a value set in it. Secret inputs map to org secret names."""
    filled = copy.deepcopy(manifest)
    for item in inputs:
        key = _input_key(item)
        value = values.get(key)
        if item["kind"] == "secret":
            filled.setdefault("secret_env", {})[key] = _secret_name(name, key)
        elif not value:
            continue
        elif item["kind"] == "image":
            filled["image"] = value
        elif item["kind"] == "env":
            filled.setdefault("env", {})[key] = value
        elif item["kind"] == "volume":
            for mount in (filled.get("mounts") or {}).get("network") or []:
                mount["volumeId"] = value
        elif item["kind"] == "data_center":
            filled["dataCenterIds"] = [value]
    return filled


def _check(name: str, data: Any) -> dict:
    """The template in a loaded file, checked. Raises ValueError when the file is not a valid template."""
    if not isinstance(data, dict) or not isinstance(data.get("template"), dict):
        raise ValueError(f"{name}: no template block")
    manifest = {k: v for k, v in data.items() if k != "template"}
    meta = data["template"]
    try:
        jsonschema.validate(meta, TEMPLATE_SCHEMA)
    except jsonschema.ValidationError as e:
        raise ValueError(f"{name}: template: {e.message}") from e
    inputs = meta["inputs"]
    for item in inputs:
        if item["kind"] in ("env", "secret") and "key" not in item:
            raise ValueError(f"{name}: an {item['kind']} input needs a key")
        if item["kind"] == "volume" and not (manifest.get("mounts") or {}).get("network"):
            raise ValueError(f"{name}: a volume input needs mounts.network in the manifest")
    keys = [_input_key(item) for item in inputs]
    if len(keys) != len(set(keys)):
        raise ValueError(f"{name}: two inputs have the same key")
    sample = _fill(name, manifest, inputs, {_input_key(i): _SAMPLES.get(i["kind"], "x") for i in inputs})
    try:
        service._validated(sample)
    except AppError as e:
        raise ValueError(f"{name}: {e.message}") from e
    return {
        "name": name,
        "title": meta["title"],
        "summary": meta["summary"],
        "kind": manifest.get("kind", "service"),
        "tag": meta.get("tag"),
        "inputs": [
            {"key": _input_key(i), "kind": i["kind"], "label": i["label"], "required": i.get("required", True)}
            for i in inputs
        ],
        "manifest": manifest,
    }


@functools.cache
def _load(root: Path = ROOT) -> dict[str, dict]:
    found = {}
    for path in sorted(root.glob(f"*/{FILE}")):
        name = path.parent.name
        if not service.NAME_PATTERN.match(name):
            raise ValueError(f"{name}: a template folder name is lowercase letters, digits and dashes")
        found[name] = _check(name, yaml.safe_load(path.read_text()))
    return found


def list_templates() -> list[dict]:
    """Every template, by name."""
    return [copy.deepcopy(t) for t in _load().values()]


def get_template(name: str) -> dict:
    found = _load().get(name)
    if found is None:
        raise AppError("No app template with this name", 404)
    return copy.deepcopy(found)


def _text(value: Any, label: str) -> str:
    if value is None:
        return ""
    if not isinstance(value, str) or len(value) > MAX_VALUE:
        raise AppError(f"{label} must be text of {MAX_VALUE} characters or fewer")
    return value.strip()


def create(
    db,
    org_id: int,
    template: str,
    name: Any,
    values: Any = None,
    secret_values: Any = None,
    provider: Any = None,
    actor: str | None = None,
) -> dict:
    """Register a new app from a template. Saves the secret inputs as org secrets, then calls put_app. Commits.

    values maps input keys to text. secret_values maps secret keys to values. A secret that the org
    already saved can be left out.
    """
    found = get_template(template)
    if not isinstance(name, str) or not service.NAME_PATTERN.match(name) or name == service.RESERVED_NAME:
        raise AppError("name must be lowercase letters, digits and single dashes, up to 63")
    if db.query(service.App).filter_by(organization_id=org_id, name=name).first():
        raise AppError("An app with this name exists", 409)
    if provider is not None:
        service._provider(provider)
    values = values if isinstance(values, dict) else {}
    secret_values = secret_values if isinstance(secret_values, dict) else {}
    filled: dict[str, str] = {}
    saved: dict[str, str] = {}
    for item in found["inputs"]:
        key, label = item["key"], item["label"]
        if item["kind"] == "secret":
            value = _text(secret_values.get(key), label)
            secret = _secret_name(name, key)
            if not re.match(r"^app_[a-z0-9_]{1,96}$", secret):
                raise AppError("name is too long for the secret names of this template")
            if value:
                saved[secret] = value
            elif secrets.get_secret(db, org_id, secret) is None:
                raise AppError(f"{label} is required", 400)
            continue
        value = _text(values.get(key), label)
        if not value and item["required"]:
            raise AppError(f"{label} is required", 400)
        filled[key] = value
    manifest = service._validated(_fill(name, found["manifest"], found["inputs"], filled))
    for secret, value in saved.items():
        try:
            secrets.set_secret(db, org_id, secret, value, actor)
        except secrets.SecretsError as e:
            raise AppError(str(e), 503 if "SECRETS_KEY" in str(e) else 400) from e
    app = service.put_app(db, org_id, name, manifest=manifest, provider=provider)
    logger.info("app created from template app=%s template=%s", name, template)
    return app | {"template": template, "suggested_tag": found["tag"]}
