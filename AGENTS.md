# AGENTS.md

Instructions for AI agents in this repo. `CLAUDE.md` is a link to this file, and `.claude/` is a link to `.agents/`.

Platform is shared infrastructure for student orgs: a Flask API, a Discord bot, a job worker and an MCP server on one database. Each org is a Discord server and turns modules on or off. In prose, call the project "Platform" and use the terms in the `technical-writing` skill.

## Skills

The procedures are in `.agents/skills/` and listed in `.agents/README.md`. The Claude Code settings are in `.agents/settings.json`.

- `check`: before each commit.
- `new-module`: to add a module.
- `migration`: after a model change.
- `api-contract`: to change a route that thesoda.io or `dashboard/` calls.
- `technical-writing`: for all prose, comments and messages.
- `pr-ready`: before you open a PR.

## Commands

```bash
uv sync                          # install dependencies
doppler setup                    # select the Doppler config; make up and make dev need a service token (docs/getting-started.md)
make dev                         # start the containers with logs and the reloader
make up | down | logs | status | shell | build
make check                       # fix lint and format, then ty, pytest, alembic check
make ci                          # the same checks with no changes to files; CI runs this
uv run bandit -q -c pyproject.toml -r .
uv run pytest tests/contract/test_godfather.py -v
uv run alembic upgrade head      # make migrate
make deploy | health | rollback  # on the server
flask --app main org|jobs|config ...
```

## Layout

| Path | Holds |
| --- | --- |
| `main.py`, `bot_main.py`, `worker_main.py`, `mcp_main.py` | API, Discord bot, job worker (Postgres only), MCP server on port 8001 |
| `core/` | Config, database (`core/db/`), jobs, tools, secrets, audit, logs, the in-process cache, HTTP hooks, Discord and RunPod clients, hosting providers (`core/hosting.py`: RunPod and This server), per-org limits (`core/limits.py`), server health and the host agent's file (`core/host.py`) |
| `modules/<name>/` | One module: `README.md`, `service.py`, `api.py`, `models.py`, `jobs.py`, `tools.py`, only the files it needs |
| `modules/registry.py`, `modules/manifest.py` | Blueprint mounts and module switches; categories, the module catalog, the modules of a new org, and model, job and tool modules |
| `apps/` | App templates that officers create apps from on the Hosting page. No Platform code |
| `deploy/` | The SQLite to Postgres copy script, the API image entrypoint (`doppler run`), the Doppler CLI installer, the RunPod start script, the `config.js` writer and the `serve` config of the dashboard image (`deploy/frontend-config.mjs`, `deploy/dashboard-serve.json`), the read-only host agent (`deploy/host-agent/`) and the This server runner (`deploy/runner/`) |
| `alembic/` | Migrations. Nothing creates tables at startup |
| `tests/contract/` | Route tests, `snapshots.json`, and `routes.txt`, the list of every route |
| `tests/test_module_layout.py` | Checks that each module is registered and documented in every place |
| `dashboard/`, `site/` | Dashboard and member store (Vite), docs and landing site. SoDA serves the dashboard at admin.thesoda.io |
| `docs/` | Guides, indexed in `docs/README.md` |

Modules: accounts, agents, alerts, auth, bot, calendar, dashboard, feeds, games, godfather, integrations, knowledge, leetcode, mcp, organizations, points, public, runpod, storefront, submodules, superadmin, uptime, users.

## Rules

- `core/` imports nothing from `modules/`. Only the route files (`api.py`, `member_api.py`), `registry.py`, `cli.py` and the route helpers in `modules/auth/` import Flask. `make ci` checks both with import-linter.
- A new module is registered in each place that `docs/writing-a-module.md` lists. `tests/test_module_layout.py` checks them.
- A service takes a database session and plain values and raises a `core.errors.ServiceError` subclass.
- Use `officer_route`, `machine_route` and `member_view` from `modules/auth/routes.py` for new routes.
- A module that stores data or calls a paid service declares its limits with `limits.declare(...)` and checks them. See `docs/limits.md`.
- A model change needs an Alembic migration. `make ci` runs `alembic check`.
- A route change updates `tests/contract/routes.txt` (`UPDATE_ROUTES=1`). A change to a route that a client uses follows the `api-contract` skill.
- Use `get_logger(__name__)` from `core/log.py`. Do not use `print()`.
- Do not add `# noqa`, `# type: ignore` or `# nosec` to get a green run. `# nosec` is only for a false positive, with the reason.
- Settings come from Doppler through the environment, and `core/config.py` reads them. Platform reads no `.env` file. A new setting goes in `.env.template` and in Doppler. Never write a secret in code, docs or commits.
- ruff (line length 120) and ty check the code. Comments are plain ASCII and say what the code does.
- Commit subjects are imperative and 72 characters or fewer. The body says why.

## Cloud Agent

Cloud Agents do not use Docker. `uv` and Node 26 are on `PATH`. `uv sync --frozen` installs the Python dependencies. `npm ci` in `dashboard/` and in `site/` installs those apps.

Amp orbs run `.agents/setup` once and keep the result in a snapshot. It installs the Node version in `.nvmrc`, Python 3.12, the uv environment, the Doppler CLI and the npm dependencies of `dashboard/` and `site/`. Login shells in the repo put that Node first on `PATH`. A second run takes less than a second. Change it when you add a toolchain or a dependency manager.

On boot, the API listens on port 8000 and the dashboard listens on port 5173. The database is SQLite at `data/user.db`. `RUN_BOT_IN_API` is `false`. The boot script creates an org with prefix `robotics` when that prefix is missing.

Discord sign-in needs `BOT_TOKEN`, `CLIENT_ID` and `CLIENT_SECRET` in the environment, from Doppler or the orb settings. `make ci` does not need them.

## Docs

When you change what a doc describes, change the doc in the same commit: the module `README.md`, the page in `docs/`, and this file. `site/scripts/sync-docs.ts` copies `docs/` to the site; a new or renamed page goes there too.
