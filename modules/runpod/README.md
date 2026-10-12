# runpod

Deploys an org's own apps to pods on a hosting provider: register an app's manifest, deploy a new image tag from the app's CI, and roll back. A deploy ends when the app's health path answers, or fails after 15 minutes. Uptime checks the apps after that. Each app keeps its `provider`, and calls go through `core/hosting.py`: RunPod, where each org pays with its own key, or This server (`server`), capped containers on the deployment's server through the runner in `deploy/runner/`. The module name stays `runpod`.

## Files

| File | Holds |
| --- | --- |
| `api.py` | Machine routes for apps, deployments, deploy and rollback |
| `service.py` | Manifests (inline, or `platform.app.yaml` from the app's repo), deploys, the deploy check and rollback on the app's provider; declares `apps:read`, `apps:manage`, `apps:deploy` and the `runpod_api_key`, `github_token` and `app_*` secrets |
| `shared.py` | Shared apps: apps with no org that the deployment runs on This server, their deployment secrets, and org subscriptions, which invite people (Vaultwarden) |
| `templates.py` | App templates from `apps/<name>/platform.app.yaml`, and new apps made from them |
| `models.py` | Apps, with their `provider`, and deployments |
| `tools.py` | The `apps.*` tools and `hosting.providers` |
| `jobs.py` | The deploy check job |

## Surface

- Routes: `/api/apps`, and `/api/apps/templates` for app templates. Shared apps: `/api/superadmin/shared-apps` for the superadmin, `/api/dashboard/<org>/shared-apps` for officers. Machine tokens only, with `apps:read`, `apps:manage` or `apps:deploy`.
- Jobs: `runpod.check_deployments`, schedule `* * * * *`.
- Tools: `apps.list`, `apps.get`, `apps.pod`, `apps.templates`, `hosting.providers` (scope `apps:read`); `apps.register`, `apps.create_from_template`, `apps.delete` (confirm), `apps.rollback` (confirm) (scope `apps:manage`); `apps.deploy` (confirm, scope `apps:deploy`). Without `confirm=true`, deploy and rollback return their dry run. Tools marked confirm run only with `confirm=true`.
- Webhook events: `app.deployed`, when a deploy becomes healthy or fails. See [docs/webhooks.md](../../docs/webhooks.md).
- Tables: `runpod_apps`, `runpod_deployments`, `shared_app_subscriptions`.
- Limits: `runpod.apps`, checked before a new app is made; `runpod.server_apps` and `runpod.server_memory_mb`, checked when an app on This server is registered or deployed. See [docs/limits.md](../../docs/limits.md).

See [docs/modules/runpod-apps.md](../../docs/modules/runpod-apps.md).
