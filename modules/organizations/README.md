# organizations

Keeps the org record (Discord server, URL prefix, officer role, config) and the officer routes that set it up: module switches, calendar and LeetCode settings, org secrets, machine tokens, stats, activity and the org's audit log. It also shows the org its resource limits (`core/limits.py`), which only the superadmin changes.

## Files

| File | Holds |
| --- | --- |
| `api.py` | Officer routes under `/<org_id>` |
| `service.py` | `OPTIONAL_MODULES`, `module_enabled`, `set_modules`, `new_org_switches`, `limits` (the org's limits and use, with whether each limit's module is on), `branding`, `set_branding`, `find_by_prefix`, `create_organization`, org secrets and machine tokens; the description and points settings; declares `org:read`, `settings:write`, `secrets:manage` and `tokens:manage` |
| `config.py` | `OrganizationSettings`, the default config of a new org |
| `models.py` | Orgs, and the unused org config and officer tables |
| `tools.py` | The `org.*`, `secrets.*` and `tokens.*` tools |

## Surface

- Routes: `/api/organizations`. Each route needs an officer of the org in the URL. The list shows only the caller's orgs. `GET /<org_id>/limits` returns the limits of the modules that are on.
- Jobs: none.
- Tools: `org.info`, `org.branding`, `org.settings`, `org.limits` (scope `org:read`); `org.set_modules` (confirm), `org.set_branding`, `org.update_settings` (scope `settings:write`); `secrets.list`, `secrets.set` (confirm), `secrets.delete` (confirm) (scope `secrets:manage`; values are never returned); `tokens.list`, `tokens.create` (confirm), `tokens.revoke` (confirm) (scope `tokens:manage`). `tokens.create` gives only scopes and limits that the calling token has, and returns the new value once. Tools marked confirm run only with `confirm=true`.
- Tables: `organizations`, `organization_configs`, `officers`.

Config keys: `modules` (a module name set to false for each module that is off; a new org has an entry for each optional module, on only for `NEW_ORG_MODULES` in `modules/manifest.py`; `NEW_ORG_MODULES` is empty, so a new org starts with each optional module off; migration `c4d6e8f0a2b4` turns off the old compute and alerts modules and uptime for existing orgs that have no data for them; migration `d7f9b1c3e5a7` renames the `compute` switch and config key to `godfather`, puts `job_webhook` and `hackathon_webhook` in place of `alerts` (each on only if `alerts` was on and the org has a feed of that kind), removes the `mcp` switch, and renames the token scopes `compute:*` to `godfather:*` and `alerts:manage` to `feeds:manage`; migration `a3c5e7f9b1d3` merges `job_webhook` and `hackathon_webhook` into `feeds`, on when either was on), `branding` (`logo_url`, `accent_color` and `website_url`), `leetcode`, `dashboard`, `godfather` (pod settings).

## Known gaps

- Views in `api.py` open their own session and query the org. The settings route checks the prefix in the view, not with `PREFIX_PATTERN` in `service.py`. Both refuse two dashes in a row (`--`), which separate the org and the app in a container name on This server.
- `PUT /<id>/settings` changes `officer_role_id` and `prefix` only for the superadmin. Its `config` keeps the stored values of the keys that have their own routes. The description and points settings go through `set_settings`.
- `/stats`, `/activity` and `/roles` return fixed sample data.
