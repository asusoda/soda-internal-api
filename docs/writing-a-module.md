# Writing a module

This page lists the files a module can have, the places to register it, and the rules that `make ci` checks. The `new-module` skill in `.agents/skills/` has the full procedure. Content for one campus or topic, such as pages to crawl and live queries, is a submodule: see [submodules/README.md](../submodules/README.md).

## Files

| File | Holds | Add it when |
| --- | --- | --- |
| `README.md` | What the module does, a Files table and a Surface list (routes, jobs, tools, tables). A Known gaps list if the module breaks a rule on this page | always |
| `service.py` | The logic. It takes a database session and plain values, returns plain values and raises a `ServiceError`. It does not import Flask | the module does more than read a table |
| `api.py` | A Flask blueprint. Each route reads the request, calls `service.py` and returns JSON | the module has routes |
| `models.py` | SQLAlchemy tables that use `Base` from `core/db/base.py` | the module keeps data |
| `jobs.py` | Background work with `@job` from `core/jobs.py` | the module runs on a schedule or in the background |
| `tools.py` | Tools for agents with `@tool` from `core/tools.py` | agents call the module |

If `service.py` has more than one concern, split it into more Flask-free files. For example, `godfather/` has `ssh.py`, `files.py` and `schedule.py`.

## Register it

| What | Where |
| --- | --- |
| Category | `CATEGORIES` in `modules/manifest.py`. Put the module in one category. Core modules are always on and are not on Explore |
| Catalog entry | `CATALOG` in `modules/manifest.py`: the title and one-line description that Explore shows, each integration key or setting the module needs (`Need`), and the submodules it reads |
| Blueprint and URL prefix | `MOUNTS` in `modules/registry.py`, and the import at the top of that file |
| Tables | `MODEL_MODULES` in `modules/manifest.py`, then `uv run alembic revision --autogenerate -m "..."` |
| Jobs | `JOB_MODULES` in `modules/manifest.py` |
| Tools | `TOOL_MODULES` in `modules/manifest.py` |
| Machine token scopes | `scopes.declare(...)` from `modules/auth/scopes.py`, at the top of `service.py` |
| Org secrets | `secrets.declare(...)` or `secrets.declare_prefix(...)` from `core/secrets.py`, at the top of `service.py` |
| Limits | `limits.declare(...)` from `core/limits.py`, at the top of `service.py`, for each thing that can grow or cost money. See [limits.md](./limits.md) |
| Outside services | `register(...)` and `use(...)` from `core/integrations/registry.py`. See [integrations.md](./integrations.md) |
| Flask-free files | `service.py`, `models.py`, `jobs.py` and `tools.py` are in the "service modules do not import Flask" contract in `pyproject.toml` by wildcard. Add each other Flask-free file, such as `crawl.py`, to that list |
| Dashboard page | An entry in `PAGES` in `dashboard/src/pages/registry.tsx`, with `module` and the sidebar section of the module's category |
| Routes | `tests/contract/routes.txt`: run `UPDATE_ROUTES=1 uv run pytest tests/contract/test_routes.py` |
| Docs | The module `README.md`, a row under its category in `modules/README.md` and in the module table of `README.md`, the `Modules:` line in `AGENTS.md` and `CLAUDE.md`, and each table in `docs/data-model.md` |

If the module needs more than its README, add `docs/modules/<name>.md`, a row in `docs/README.md`, and the page in `site/scripts/sync-docs.ts`.

`tests/test_module_layout.py` checks the categories, the catalog entries, the manifest lists, `MOUNTS`, the Flask-free contract, the module switches, the docs rows, and that each README and `docs/data-model.md` name the module's jobs, tools and tables. If you forget a place, the test names the file to change.

This diagram shows the places to register a module and the places that the test checks.

```mermaid
flowchart LR
  module["modules/#lt;name#gt;/"] --> manifest["modules/manifest.py: CATEGORIES, CATALOG, MODEL_MODULES, JOB_MODULES, TOOL_MODULES"]
  module --> registry["modules/registry.py: MOUNTS"]
  module --> optional["modules/organizations/service.py: OPTIONAL_MODULES"]
  module --> pyproject["pyproject.toml: Flask-free contract"]
  module --> pages["dashboard/src/pages/registry.tsx: PAGES"]
  module --> routes["tests/contract/routes.txt"]
  module --> docs["README files, AGENTS.md, CLAUDE.md, docs/data-model.md"]
  layout["tests/test_module_layout.py"] -.->|checks| manifest
  layout -.->|checks| registry
  layout -.->|checks| optional
  layout -.->|checks| pyproject
  layout -.->|checks| docs
```

### Org switch

If orgs can turn the module off:

1. Add the name and a one-line description to `OPTIONAL_MODULES` in `modules/organizations/service.py`.
2. Set `module="<name>"` on the `Mount`. Its org routes then return 404 when the module is off. For one route in a shared blueprint, use `endpoint_modules`.
3. Set `module="<name>"` on each `@tool`. The tool then does not show for an org that turned it off.
4. In a job that runs for all orgs, skip an org when `organizations.module_enabled(org, "<name>")` is false.
5. Add the name to the expected dict in `tests/contract/test_modules.py`.
6. A new org starts with the module off. To start new orgs with it on, add it to `NEW_ORG_MODULES` in `modules/manifest.py`.

## Routes

Use the helpers in `modules/auth/routes.py`. Each one checks the caller, opens a database session, finds the org and changes a `ServiceError` into `{"error": message}` with its status.

| Helper | Use it for | The view gets |
| --- | --- | --- |
| `officer_route(blueprint, rule, methods)` | Officer routes under `/<org_prefix>` | `db, org, **path args` |
| `machine_route(blueprint, rule, scope, methods)` | Routes for apps and agents with a machine token | `db, org, **path args` |
| `member_view(view)` | Routes for members signed in with Discord | `db, org, discord_id, **path args` |

```python
from functools import partial

from flask import Blueprint

from core.http.responses import json_body
from modules.auth.routes import machine_route

from . import service

things_blueprint = Blueprint("things", __name__)
_route = partial(machine_route, things_blueprint)


@_route("/things/<string:key>", "things:write", ["PUT"])
def put_thing(db, org, key):
    return service.put_thing(db, int(org.id), key, json_body()), 201
```

A view returns a dict, or a `(dict, status)` tuple. For other routes, use the decorators in `modules/auth/decorators.py`. See [Authentication](./authentication.md).

## Errors

A module has one error class, a subclass of `core.errors.ServiceError`:

```python
class ThingError(ServiceError):
    pass


raise ThingError("No thing with that key", 404)
```

The route helpers and the tool runner return its message and status. A tool function thus calls the service and needs no `try`.

## Rules that `make ci` checks

- `core/` imports nothing from `modules/` (import-linter).
- The files in the Flask-free contract do not import Flask (import-linter).
- ruff lint and format, and the ty type check. CI also runs bandit.
- `tests/contract/routes.txt` agrees with the routes of the app.
- `tests/contract/` checks each route that a client uses. Add a test there for a new route.
- `alembic check` finds no model change without a migration.
- `tests/test_module_layout.py` finds each module in every place listed in [Register it](#register-it).

## Example

`modules/runpod/` is a small module with every file: `service.py`, `api.py` on `machine_route`, `models.py`, `jobs.py` and `tools.py`. `modules/feeds/` is the example for `officer_route`.
