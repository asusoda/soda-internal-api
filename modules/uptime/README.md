# uptime

Checks public URLs and the health URLs of Hosting apps on a schedule. Keeps each result. Sends `monitor.down` and `monitor.up` when a monitor changes state. Each new Hosting app gets a monitor when the module is on, and a deleted app loses its monitors.

## Files

| File | Holds |
| --- | --- |
| `api.py` | Officer routes to list, add, change, delete and check monitors |
| `service.py` | Monitors, checks, uptime percents, state changes and events, the monitors of Hosting apps; declares `uptime:read` |
| `probe.py` | One HTTP check. Each URL and redirect must resolve to public addresses (`core/net.py`) |
| `models.py` | Monitors and their checks |
| `jobs.py` | The scheduled checks and the removal of old checks |
| `tools.py` | The `uptime.*` tools |

## Surface

- Routes: `/api/uptime/<org>/monitors` and `/api/uptime/<org>/targets`, behind the `uptime` switch. Officers of the org only.
- Jobs: `uptime.check_due`, schedule `* * * * *`; `uptime.prune`, schedule `50 3 * * *`.
- Tools: `uptime.list`, `uptime.get`, `uptime.targets` (scope `uptime:read`); `uptime.save`, `uptime.check`, `uptime.delete` (confirm) (scope `uptime:manage`). Tools marked confirm run only with `confirm=true`.
- Webhook events: `monitor.down`, `monitor.up`. See [docs/webhooks.md](../../docs/webhooks.md).
- Tables: `uptime_monitors`, `uptime_checks`.
- Limits: `uptime.monitors` (default 50). The monitor that Hosting adds for a new app is skipped when the org is at the limit. See [docs/limits.md](../../docs/limits.md).

See [docs/modules/uptime.md](../../docs/modules/uptime.md).
