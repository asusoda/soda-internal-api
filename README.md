# Platform

Platform is shared infrastructure for student orgs. One deployment serves many orgs. Each org is a Discord server and turns on only the modules it uses.

Each org route checks access. The audit log records each change that an officer or a token makes. Org secrets are encrypted in the database.

## Modules

| Module | Does |
| --- | --- |
| `points`, `users` | Members, event points, leaderboards, CSV imports |
| `storefront` | A merch store paid in points, with prices checked on the server |
| `calendar` | Notion events synced to Google Calendar, with the credentials of each org |
| `leetcode`, `games` | The daily LeetCode post and Jeopardy in Discord |
| `organizations`, `superadmin` | Orgs, officers, module switches, secrets and machine tokens; for the superadmin, the server's services and the shared apps |
| `godfather` | GPU and CPU pods on the org's RunPod account. Members connect over SSH with 12-hour certificates |
| `agents` | Conversations, memories and a profile graph for each member, for agents that talk to members |
| `knowledge` | Hybrid search (pgvector and full text) over documents and crawled public pages |
| `submodules` | Shared content from `submodules/`: content made once for every org, such as the ASU campus pages and live queries for knowledge, and the job and hackathon feeds for Feeds |
| `alerts` | Org events, such as a failed job or a site that is down, sent to the org's Discord destinations |
| `accounts` | Canvas, Google and Outlook sign-in for a member, so that agents can act for them |
| `feeds` | New job listings and hackathons posted to an alert destination |
| `runpod` | Hosting: deploys of an org's apps to RunPod or This server (capped containers on the deployment's server), with health checks and rollback; shared apps such as the vault |
| `uptime` | Checks of sites and Hosting apps on a schedule, with events when one goes down or up |
| `dashboard` | One page for each org with problems, activity, jobs, CI runs and module state |
| `mcp` | An MCP server and `/api/tools` that give agents the module tools through scoped machine tokens |
| `auth`, `public`, `bot` | Discord sign-in, tokens and access checks; open reads for public pages; the Discord bot |

The dashboard calls modules features and submodules shared content. Each module is in one category: Core, Storage, AI and agents, Automations, Bots or Compute. Core modules are always on. A new org starts with each other module off. A module can read submodules from `submodules/`: content made once for every org. See [Architecture](docs/architecture.md#categories-modules-and-submodules).

## Processes

| Process | Entry point | Port |
| --- | --- | --- |
| API | `main.py` (gunicorn) | 8000 |
| Discord bot | `bot_main.py` | |
| Job worker | `worker_main.py` (Postgres only) | |
| MCP server | `mcp_main.py` | 8001 |
| Dashboard and member store | `dashboard/` | 5001 (5173 in dev) |

The database is Postgres, or SQLite for a small deployment. Alembic makes the schema.

## Start

You need Podman with podman-compose (or Docker), make, uv and the Doppler CLI. `deploy/install-doppler.sh` installs the Doppler CLI.

```bash
git clone https://github.com/asusoda/platform.git
cd platform
uv sync
uv run pre-commit install
deploy/install-doppler.sh ~/.local/bin   # the Doppler CLI, if you do not have it
export PATH="$HOME/.local/bin:$PATH"
doppler login && doppler setup   # the settings: Discord app, bot token, secrets
doppler configs tokens create local --plain | doppler configure set token --scope "$PWD"
make dev
```

The API is at http://localhost:8000 and the dashboard at http://localhost:5001. Create an org with `doppler run -- uv run flask --app main org create`. [Getting started](docs/getting-started.md) has the settings and the steps to run Platform on one RunPod pod.

## Commands

```bash
make dev       # start with logs
make up        # start in the background
make down      # stop
make check     # fix lint and format, then type check, tests, migrations
make ci        # the checks that CI runs, with no changes to files
make shell     # shell in the API container, with the settings from Doppler
make deploy    # deploy on the server
```

## Documentation

[docs/](docs/README.md) has the guides. Each module folder has a `README.md`. [docs/roadmap.md](docs/roadmap.md) has the plan.

## Deployments

The Software Developers Association (SoDA) at ASU and AI Society at ASU run Platform. Their servers are the examples in these docs.

## License

BSD 3-Clause (modified for web attribution). Copyright The Software Developers Association at ASU. See [LICENSE](LICENSE).
