# Architecture

Platform is a Flask API with a Discord bot, a job worker and an MCP server. All four use the same code in `core/` and `modules/` and the same database.

## Processes

| Process | Entry point | Port | Use |
| --- | --- | --- | --- |
| API | `main.py` under gunicorn | 8000 | Every HTTP route |
| Discord bot | `bot_main.py` | | Slash commands and Jeopardy, with the cogs in `modules/bot`, `modules/games` and `modules/leetcode` |
| Job worker | `worker_main.py` | | Runs jobs from the Procrastinate queue. Postgres only |
| MCP server | `mcp_main.py` | 8001 | Module tools for agents, over MCP |
| Dashboard | `dashboard/` | 5001 (5173 in dev) | The officer pages for each org and the member store (Vite, React) |
| Web | `web/` | 5000 | The old officer app (Create React App), kept for SoDA at admin.thesoda.io |

The database is Postgres in production, or SQLite for a small deployment. Alembic makes the schema.

This diagram shows the processes, their clients and the outside services.

```mermaid
flowchart LR
  dashboard["dashboard/"] --> api["API: main.py, port 8000"]
  web["web/"] --> api
  website["thesoda.io"] --> api
  agents["Apps and agents"] -->|"Bearer plat_..."| mcp["MCP server: mcp_main.py, port 8001"]
  agents -->|"/api/tools"| api
  api --> db[("Postgres or SQLite")]
  mcp --> db
  bot["Discord bot: bot_main.py"] --> db
  worker["Job worker: worker_main.py, Postgres only"] --> db
  api -->|"REST, BOT_TOKEN"| discord["Discord"]
  bot --> discord
  api --> outside["RunPod, Notion, Google, GitHub and other services"]
  worker --> outside
```

The API does not need the bot. It reads Discord servers, roles and members over Discord's REST API with `BOT_TOKEN` (`core/integrations/discord.py`). The Jeopardy routes under `/api/bot` are the exception: they call the bot's cogs, so they work only when the bot runs in the API process (`RUN_BOT_IN_API=true`).

## Layout

```
main.py, bot_main.py, worker_main.py, mcp_main.py   the four entry points
core/          shared code: config, database, jobs, tools, secrets, audit, logs, HTTP hooks, Discord and RunPod clients, hosting providers
modules/       one folder per module, not nested; registry.py mounts the blueprints, manifest.py lists categories, models, jobs and tools
alembic/       migrations
tests/         pytest; tests/contract/ checks every route a client uses
dashboard/, site/   the dashboard and member store, the docs and landing site
deploy/        the RunPod start script and the SQLite to Postgres copy script
```

`core/` imports nothing from `modules/`. Only the route files (`api.py`, `member_api.py`), `registry.py`, `cli.py` and the route helpers in `modules/auth/` import Flask. `make ci` checks both with import-linter.

## How a request runs

1. Flask-CORS adds the CORS headers for an allowed origin. The list is in `main.py`, plus `CORS_EXTRA_ORIGINS` and `DASHBOARD_URL`.
2. If the path starts with a `DISABLED_ROUTES` prefix, the API returns 404.
3. `modules/registry.py` sends the request to the module blueprint. If the module is turned off for the org in the URL, it returns 404.
4. A decorator from `modules/auth` checks the caller. See [Authentication](./authentication.md).
5. The view reads the request, calls the module's `service.py` and returns JSON.
6. Before the response goes out, `core/http/request_log.py` logs one line, and `core/http/audit_hook.py` writes each successful change to `audit_log`.

The org comes from the URL (`org_prefix` or `org_id`), or from the machine token. The `X-Organization-*` headers that older clients send are used only in the request log.

Views get a database session from `officer_route`, `machine_route` or `member_view` in `modules/auth/routes.py`, or from `core.db.session()`. Older views call `next(db_connect.get_db())` and close the session in a `finally` block.

## Modules

A module is a folder in `modules/` with only the files it needs: `service.py` for the logic, `api.py` for the routes, `models.py`, `jobs.py` and `tools.py`. The REST routes, jobs, tools and the bot call the same `service.py` functions. [Writing a module](./writing-a-module.md) gives the rules and the places to register a module.

Orgs can turn on and off the optional modules: `points`, `storefront`, `calendar`, `games`, `leetcode`, `godfather`, `event_webhook`, `feeds`, `uptime`, `knowledge`, `agents`, `integrations`, `accounts` and `runpod`. The list is `OPTIONAL_MODULES` in `modules/organizations/service.py`. The Core modules, `mcp` and `submodules` among them, are always on. When a module is off for an org, its routes return 404 for the org (`module=` on `officer_route`, `machine_route` or the `Mount`), its tools are not listed, and its jobs skip the org. With `integrations` off, the org has no tools of connected services. If `games` is off for each org of an officer, the `/api/bot` routes return 404 for that officer. The switches are in `Organization.config["modules"]`. A module with no entry is on, so an org made before the switch existed keeps the module. A new org gets an entry for each optional module: on for the modules in `NEW_ORG_MODULES` in `modules/manifest.py`, off for the others. `NEW_ORG_MODULES` is empty, so a new org starts with Core only. Officers add and remove modules on the dashboard Explore page, or with `flask --app main org modules <prefix> --on x --off y`.

### Categories, modules and sub-modules

A category groups modules. A module can read sub-modules.

```mermaid
flowchart LR
  category["Category: Storage"] --> module["Module: knowledge"] --> submodule["Sub-module: submodules/asu"]
```

| | Module | Sub-module |
| --- | --- | --- |
| Is | A feature with code, in `modules/<name>/` | Content or presets with no code of their own, in `submodules/<name>/` |
| Examples | `knowledge`, `feeds`, `godfather` | `submodules/asu` (campus pages and live queries for `knowledge`), `submodules/careers` (feeds for `feeds`) |
| Per org | Optional modules are switched on or off for each org | An org adds a sub-module's sources or feeds in the module that uses it |
| On the dashboard | A card on Explore | A sub-module on the card of the module that uses it |

`CATALOG` in `modules/manifest.py` gives each module a title, a description, what it needs (integration keys or settings) and the sub-modules it reads. `CATEGORIES` puts each module in one category:

| Category | Modules |
| --- | --- |
| Core | `auth`, `bot`, `dashboard`, `feeds`, `mcp`, `organizations`, `public`, `submodules`, `superadmin`, `users`. Always on and not on Explore |
| Storage | `knowledge`, `points`, `storefront`, `accounts` |
| AI and agents | `agents`, `integrations` |
| Webhooks | `event_webhook`, `feeds` |
| Automations | `calendar`, `uptime` |
| Bots | `leetcode`, `games` |
| Compute | `godfather`, `runpod` (Hosting) |

The dashboard sidebar has one section for each category except Core. The routes and tools of `submodules` need the `knowledge` module. `GET /api/dashboard/<org>/modules` returns the catalog with the org's switches and whether each need is connected.

## Jobs

A module declares a job in its `jobs.py` with `@job(name, cron=..., retry=...)` from `core/jobs.py`. Code starts a job with `jobs.defer(name, **kwargs)`. Each module README lists its jobs. `flask --app main jobs list` lists all of them.

- On Postgres, `defer` adds a row to the Procrastinate queue. The worker runs the job, tries it again if it fails, and runs the periodic jobs.
- On SQLite, there is no queue. `defer` runs the job in a thread of the calling process. A thread in the API runs the periodic jobs, and `worker_main.py` stops.

`JOBS_BACKEND=inline|procrastinate` sets the choice. The tests use `inline`. `JOBS_SCHEDULER=false` stops the thread that runs periodic jobs with the inline backend; the tests set it, so no periodic job changes rows during a test. Each run of a job with `audit=True` (the default) is written to `audit_log`.

## Tools and the MCP server

Apps and agents read and change Platform data through tools. A module declares a tool in its `tools.py` with `@tool` from `core/tools.py`. Platform serves each tool two ways:

- Over MCP (streamable HTTP) from `mcp_main.py`, at `http://<host>:8001/mcp`.
- Over HTTP from the API: `GET /api/tools` lists the tools, and `POST /api/tools/<name>` calls one with the arguments as the JSON body.

Both need a machine token: `Authorization: Bearer plat_...`. The `mcp` module is Core, so it is always on. A caller sees only the tools that its token scopes allow and whose module its org has turned on. The MCP card on the Tokens page of the dashboard shows the server and the header. An unknown tool and a refused tool both return 404, so a token cannot find tools it may not use. A tool always acts on the caller's org. It has no org argument.

| Tools | Scope | Module |
| --- | --- | --- |
| `batch`: 1 to 25 calls of other tools, each checked as a single call | the scope of each call | mcp |
| `org.info`, `org.branding`, `org.settings`, `leetcode.settings` | `org:read` | organizations, leetcode |
| `org.set_modules` (confirm), `org.set_branding`, `org.update_settings`, `leetcode.update_settings`, `ci.set_repos` | `settings:write` | organizations, leetcode, dashboard |
| `secrets.list`, `secrets.set` (confirm), `secrets.delete` (confirm) | `secrets:manage` | organizations |
| `tokens.list`, `tokens.create` (confirm), `tokens.revoke` (confirm) | `tokens:manage` | organizations |
| `org.overview`, `org.trends`, `notifications.list`, `errors.list`, `activity.log`, `ci.runs` | `activity:read` | dashboard |
| `notifications.resolve`, `notifications.reopen`, `notifications.delete` (confirm), `errors.resolve`, `errors.reopen`, `errors.delete` (confirm) | `settings:write` | dashboard |
| `integrations.list`, `integrations.save` (confirm), `integrations.test`, `integrations.disconnect` (confirm) | `integrations:manage` | dashboard |
| `webhooks.list`, `webhooks.save`, `webhooks.test`, `webhooks.delete` (confirm) | `webhooks:manage` | dashboard |
| `events.list`, `calendar.settings` | `calendar:read` | calendar |
| `calendar.update_settings`, `calendar.sync`, `calendar.setup` | `calendar:manage` | calendar |
| `points.leaderboard` | `points:read` | points |
| `points.entries`, `points.history`, `members.list`, `members.discord_roles` | `members:read` | points, users |
| `points.award`, `points.import_csv`, `points.delete` (confirm) | `points:write` | points |
| `members.add`, `members.update`, `members.discord_sync` (confirm) | `members:write` | users |
| `store.products`, `store.orders` | `store:read` | storefront |
| `store.save_product`, `store.update_orders`, `store.delete_products` (confirm), `store.delete_orders` (confirm) | `store:write` | storefront |
| `knowledge.search`, `knowledge.sources`, `knowledge.read_source`, `knowledge.submodules`, `knowledge.settings`, `knowledge.runs` | `knowledge:read` | knowledge |
| `knowledge.add_document`, `knowledge.delete_source` (confirm), `knowledge.set_crawl`, `knowledge.crawl_now`, `knowledge.sync_submodule`, `knowledge.update_settings`, `knowledge.reindex` (confirm) | `knowledge:write` | knowledge |
| `submodules.query` | `knowledge:read` | submodules |
| `apps.list`, `apps.get`, `apps.pod`, `apps.templates`, `hosting.providers` | `apps:read` | runpod |
| `apps.register`, `apps.link`, `apps.create_from_template`, `apps.delete` (confirm), `apps.rollback` (confirm) | `apps:manage` | runpod |
| `apps.deploy` (confirm) | `apps:deploy` | runpod |
| `feeds.list`, `feeds.presets`, `feeds.history`, `feeds.save`, `feeds.run`, `feeds.delete` (confirm) | `feeds:manage` | feeds |
| `godfather.pods`, `godfather.pod_members`, `godfather.connected`, `godfather.settings`, `godfather.sessions`, `godfather.list_files`, `godfather.read_file`, `godfather.update_pod`, `godfather.update_settings`, `godfather.delete_session`, `godfather.make_folder`, `godfather.move_file` | `godfather:manage` | godfather |
| `godfather.pod_action`, `godfather.create_pod`, `godfather.add_session`, `godfather.write_file`, `godfather.delete_file` (each confirm) | `godfather:manage` | godfather |
| `uptime.list`, `uptime.get`, `uptime.targets` | `uptime:read` | uptime |
| `uptime.save`, `uptime.check`, `uptime.delete` (confirm) | `uptime:manage` | uptime |
| `github.*`: the read-only tools of GitHub's MCP server | `github:read` | integrations |
| `github.*`: the other tools of GitHub's MCP server (confirm) | `github:write` | integrations |
| `runpod.*`: the read-only tools of RunPod's MCP server | `runpod:read` | integrations |
| `runpod.*`: the other tools of RunPod's MCP server (confirm) | `runpod:write` | integrations |
| `notion.*`: the tools of Notion's MCP server, after an officer signs in | `notion:read`, `notion:write` | integrations |
| `gmail.*`: the tools of Google's Gmail MCP server, after an officer signs in | `gmail:read`, `gmail:send` | integrations |
| `drive.*`, `calendar.*`: the tools of Google's Drive and Calendar MCP servers, after an officer signs in | `google:read`, `google:write` | integrations |
| `google.calendar_list`, `google.calendar_events`, `google.drive_search`, `google.drive_read`, `google.sheets_read` | `google:read` | integrations |
| `google.calendar_create_event` (confirm), `google.sheets_append` (confirm) | `google:write` | integrations |
| `google.gmail_search`, `google.gmail_read` | `gmail:read` | integrations |
| `google.gmail_send` (confirm) | `gmail:send` | integrations |
| `notion.search`, `notion.read_page`, `notion.query_database` | `notion:read` | integrations |
| `notion.create_page` (confirm) | `notion:write` | integrations |
| `web.search` | `web:read` | integrations |
| `asu.clubs`, `asu.events`, after an officer signs in to ASU | `asu:read` | `submodules/asu/signin` |
| `canvas.courses`, `canvas.assignments`, `canvas.grades`, `canvas.announcements`, `canvas.calendar`, `canvas.assignment_grades`: one member's own Canvas, after the member connects it | `canvas:read` | accounts |

A tool marked confirm changes or deletes something that is hard to undo. It runs only when the call has `confirm=true`. Without it, nothing changes and the result has `confirm_required`, the arguments, and for `apps.deploy` and `apps.rollback` the dry run. An agent shows that to a person, then calls again with `confirm=true`. Over MCP, read tools have `readOnlyHint` and confirm tools have `destructiveHint`.

No tool returns a secret value or a webhook URL. `tokens.create` returns the new token once. It gives only the scopes and limits of the calling token. A write tool that takes `ids` changes up to 100 rows in one commit; if one id is missing, nothing changes. To send many calls in one request, use `batch` with `{"calls": [{"tool", "arguments"}], "stop_on_error"}`. Its result has one entry for each call: `tool`, `ok`, `result` or `error`, and `status`.

The flows that need a browser have no tool: the OAuth sign-in to an integration, the ASU sign-in, file upload and download on a pod, and the Godfather CLI sign-in. Superadmin routes and member routes have no tool.

Each call, allowed or refused, is a row in `audit_log` with `action=tool <name>`, `source=mcp` or `api`, and the token as the actor. A call that waits for confirm has `details.confirm=pending`. The MCP server keeps no session state, so you can run more than one. Start it with `docker compose --profile mcp up -d mcp`.

## Outside services

| Service | Use | Code |
| --- | --- | --- |
| Discord | Sign-in, role and member checks, the bot | `core/integrations/discord.py`, `modules/auth`, `modules/bot` |
| Clerk | Member sign-in on the public website storefront | `modules/auth/clerk.py` |
| Notion, Google Calendar | Calendar sync | `modules/calendar/clients/` |
| RunPod | Godfather pods and app deploys, through the hosting provider registry in `core/hosting.py` | `core/integrations/runpod.py` |
| LeetCode GraphQL | The daily question and solve checks | `modules/leetcode/client.py` |
| Error log | Errors of each process and the dashboard, grouped in `error_groups`, shown on Activity, Errors | `core/error_log.py`, `modules/dashboard/errors.py` |
| Webhooks | Org events (errors, failed jobs, pods, deploys, orders, new members, failed crawls) posted to Discord webhooks | `core/webhooks.py`, `modules/event_webhook/` |
| Sentry | Optional: errors, logs and sampled traces if `SENTRY_DSN` is set | `core/log.py` |
