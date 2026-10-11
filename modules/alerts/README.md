# alerts

Sends the org's events, such as a failed job or a site that is down, to its destinations. A destination is a Discord webhook with a name and the events it gets: its routes. Feeds post to a destination too. Alerts is a Core module, so it is always on. Activity saves each event as a notification, also when no destination gets it.

## Files

| File | Holds |
| --- | --- |
| `api.py` | Officer routes to list, add, change, delete and test destinations |
| `service.py` | Checks of the name, events and URL; the encrypted URL and its hint; the test message; a delete refused while a feed posts to the destination |
| `tools.py` | The `webhooks.*` tools; declares `webhooks:manage` |

`core/webhooks.py` has the `webhooks` table (one row for each destination), the events that modules declare, and the delivery.

## Surface

- Routes: `/api/dashboard/<org>/webhooks`, `/webhooks/<id>` and `/webhooks/<id>/test`. Officers of the org only.
- Jobs: none.
- Tools: `webhooks.list`, `webhooks.save`, `webhooks.test`, `webhooks.delete` (confirm) (scope `webhooks:manage`). URLs are never returned. Tools marked confirm run only with `confirm=true`.
- Tables: none here. The destinations are in `webhooks` (`core/webhooks.py`).
- Limits: `alerts.destinations` (default 20). See [docs/limits.md](../../docs/limits.md).
- Migration `c6e8a0b2d4f6` made it from the `event_webhook` module. An org that had that switch off got its destinations turned off.

See [docs/webhooks.md](../../docs/webhooks.md).
