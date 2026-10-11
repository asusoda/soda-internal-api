# event_webhook

Sends events of the org, such as a failed job or a site that is down, to the webhooks that officers add. Each webhook has a name, a Discord URL and the events it takes. With the module off, no event goes to a webhook and the routes and tools return 404. Activity still saves each event as a notification.

## Files

| File | Holds |
| --- | --- |
| `api.py` | Officer routes to list, add, change, delete and test webhooks |
| `service.py` | Checks of the name, events and URL; the encrypted URL and its hint; the test message |
| `tools.py` | The `webhooks.*` tools; declares `webhooks:manage` |

`core/webhooks.py` has the `webhooks` table, the events that modules declare, and the delivery.

## Surface

- Routes: `/api/dashboard/<org>/webhooks`, `/webhooks/<id>` and `/webhooks/<id>/test`, behind the `event_webhook` switch. Officers of the org only.
- Jobs: none.
- Tools: `webhooks.list`, `webhooks.save`, `webhooks.test`, `webhooks.delete` (confirm) (scope `webhooks:manage`). Webhook URLs are never returned. Tools marked confirm run only with `confirm=true`.
- Tables: none here. The webhooks are in `webhooks` (`core/webhooks.py`).
- Limits: `event_webhook.webhooks` (default 20). See [docs/limits.md](../../docs/limits.md).

See [docs/webhooks.md](../../docs/webhooks.md).
