# core

Shared code that modules use: config, database, logs, HTTP hooks, Discord and RunPod clients, hosting providers, jobs, tools, audit, the error log, org secrets, outbound webhooks, per-org limits and the server's health. `core/` imports nothing from `modules/`; the import-linter contract `core imports no module` in `pyproject.toml` checks it.

## Files

| File | Holds |
| --- | --- |
| `config.py` | `Config` and the `config` instance: settings from the environment, which Doppler sets |
| `db/` | `Base` (`base.py`), `DBConnect`, the `db_connect` instance and `session()` (`session.py`) |
| `errors.py`, `time.py` | `ServiceError`, the error a service raises with an HTTP status; `utcnow()` and `iso()` for naive UTC times |
| `jobs.py` | `@job` and `defer()`: Procrastinate on Postgres, threads on SQLite (at most `JOB_THREADS` at a time). A job with `once` runs once at a time for the same arguments; a second `defer()` raises `JobBusy`. A failed job with an org argument sends the `job.failed` webhook event |
| `tools.py` | The `@tool` registry (`TOOLS`, `ToolSpec`, `ToolError`) |
| `audit.py` | The `audit_log` table, `record()` and the `audit.prune` job |
| `error_log.py` | The `error_groups` table, `ErrorLogHandler` that records log lines at ERROR and above, `capture()`, and the `error_log.prune` job |
| `webhooks.py` | The `webhooks` table, the event registry (`declare()`), `emit()` that posts an event to the org's webhooks in a thread, and the kinds (Discord). See [docs/webhooks.md](../docs/webhooks.md) |
| `limits.py` | The `org_limits` and `usage_counters` tables, `declare()`, `check()` for count limits, `consume()` for rate limits, `report()`, `set_values()` and the `limits.prune` job. See [docs/limits.md](../docs/limits.md) |
| `host.py` | `stats()`: the load, memory, disk, database size and container limits that the Superadmin page shows |
| `secrets.py` | The `org_secrets` table, `declare()`, `set_secret` and `get_secret`, encrypted with `SECRETS_KEY` |
| `log.py` | `get_logger`, JSON log lines and `init_sentry` |
| `cache.py` | `TTLCache` and the shared `cache`: values by tuple key, each with a time to live, in one process. Concurrent misses on a key compute once |
| `http/` | `responses.py` (`json_body`, `error`, `error_handler`), `request_log.py` (one line for each request, `bearer_token()`), `audit_hook.py` (writes successful changes to the audit log), `cached.py` (`cached_json`: an org read kept in `cache` with an ETag, and the hook that drops the cached org reads after a successful write) |
| `integrations/` | `discord.py` (`DiscordDirectory`, messages and reactions over Discord's REST API) and `runpod.py` (RunPod REST client and the `runpod` hosting provider) |
| `hosting.py` | Hosting providers: the `HostingProvider` and `HostingClient` protocols, the registry (`register()`, `get()`, `listing()`) and `HostingError`. See [docs/modules/godfather.md](../docs/modules/godfather.md#adding-a-hosting-provider) |

## Surface

- Jobs: `audit.prune`, schedule `30 3 * * *`, keeps `AUDIT_RETENTION_DAYS` (default 365). `error_log.prune`, schedule `40 3 * * *`, keeps groups seen in the last `ERROR_RETENTION_DAYS` (default 90). `limits.prune`, schedule `10 4 * * *`, deletes usage counters older than 8 days.
- Tables: `audit_log`, `error_groups`, `org_secrets`, `webhooks`, `org_limits`, `usage_counters`.

See [docs/architecture.md](../docs/architecture.md).
