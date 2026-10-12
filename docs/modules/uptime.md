# Uptime

Checks the org's sites and Hosting apps on a schedule. Officers manage monitors on the dashboard page Uptime. Each new Hosting app gets a monitor named after the app, and a deleted app loses its monitors.

## Monitors

| Field | Default | Does |
| --- | --- | --- |
| `name` | required | 1 to 100 characters, unique in the org |
| `target_kind` | `url` | `url`, or `app` for an app on the Hosting page |
| `target` | required | An http or https URL, or the name of the app |
| `expected_status` | `2xx` | A status class (`2xx`, `3xx`) or one status code (`204`) |
| `timeout_seconds` | `10` | 1 to 30, for all redirects together |
| `interval_minutes` | `5` | 1 to 1440 |
| `enabled` | `true` | `false` pauses the monitor |

An org has at most `uptime.monitors` monitors, 50 by default (see [Limits](../limits.md)). A change of target or expected status, and a resume, clear the state.

An `app` target on RunPod uses the health URL of the app's pod (`health.port` and `health.path` of its manifest). If the app has no pod, the check uses the `url` of its manifest. An app on This server has a private address, which the check does not read; the runner runs the app's own health check instead (an HTTP path, a TCP connect, or its running state), and the latency is the time of that check.

## Checks

- The `uptime.check_due` job runs every minute. It checks each enabled monitor whose interval has passed, in orgs that have the module on.
- A check sends a GET, follows at most 5 redirects and does not read the body. Each URL and each redirect must resolve to public addresses. `core/net.py` checks them, as for knowledge crawls.
- A check is up when the status matches `expected_status`. Else it is down, with the status or the error.
- The `uptime.prune` job removes checks older than `UPTIME_RETENTION_DAYS` (default 30).

## Events

| Event | Sent when |
| --- | --- |
| `monitor.down` | The first check is down, or a check is down after an up check |
| `monitor.up` | A check is up after a down check |

Each event shows in Activity > Notifications and goes to the webhooks that take it. See [Webhooks](../webhooks.md).

The state of a monitor changes as follows.

```mermaid
stateDiagram-v2
  state "no state" as none
  [*] --> none
  none --> up: check up, no event
  none --> down: check down, monitor.down
  up --> down: check down, monitor.down
  down --> up: check up, monitor.up
  up --> none: new target or expected status, or resume
  down --> none: new target or expected status, or resume
```

## Routes

All routes are under `/api/uptime/<org>`, for officers of the org. The `uptime` switch turns them off.

| Route | Does |
| --- | --- |
| `GET /monitors` | Each monitor with `state`, `uptime_24h`, `uptime_7d`, `last_check` and its last 30 checks in `recent` |
| `POST /monitors` | Adds a monitor. Returns 201 |
| `GET /monitors/<id>` | One monitor with its last 100 checks |
| `PUT /monitors/<id>` | Changes the fields in the body |
| `DELETE /monitors/<id>` | Deletes the monitor and its checks |
| `POST /monitors/<id>/check` | Checks the monitor now and returns `check` and `monitor` |
| `GET /targets` | The Hosting apps and the URL that a check of each reads |

The `uptime.list` tool (scope `uptime:read`) returns the monitors without `recent`. `uptime.get` and `uptime.targets` also need `uptime:read`. `uptime.save`, `uptime.check` and `uptime.delete` (confirm) need `uptime:manage`.
