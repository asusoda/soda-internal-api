# superadmin

Routes for the superadmins of the deployment (the Discord user ids in `SYS_ADMIN`, comma-separated): add and remove orgs for Discord servers, set an org's officer role, list a server's roles, read the audit log and errors of all orgs, see the server's health and services, and set each org's limits.

## Files

| File | Holds |
| --- | --- |
| `api.py` | `/check`, `/dashboard`, `/guild_roles/<guild_id>`, `/add_org/<guild_id>`, `/remove_org/<org_id>`, `/update_officer_role/<org_id>`, `/audit`, `/publishers`, `/errors`, `/server`, `/server/services`, `/server/services/<name>` (PUT), `/limits`, `/limits/<org_id>` (GET, PUT), `/shared-apps` and `/shared-apps/<name>` (GET, PUT, DELETE), `/shared-apps/<name>/deploy`, `/rollback`, `/pod`, `/secrets` (PUT), `/action`, `/logs`; `/server/services/<name>/action` and `/logs` |
| `models.py` | `ServiceOwner`: the owner the superadmin set for a service |
| `service.py` | The superadmin check, servers with no org, an officer's orgs, server roles, role checks, new orgs, `server()` (the server's health, the bot and the job queue), `server_services()` and `set_service_owner()` (the host agent's services and their owners) and each org's limits (`all_limits`, `org_limits`, `set_org_limits`) |

## Surface

- Routes: `/api/superadmin`. Each route except `/check` needs a superadmin, also when `ACCESS_ENFORCE` is false. `/check` answers for the caller's own token. `PUT /limits/<org_id>` takes `{"limits": {key: number | null | "default"}}`; see [docs/limits.md](../../docs/limits.md). `PUT /server/services/<name>` takes `{"owner": "platform" | "infrastructure" | "org" | null, "organization_id": 1}`; see [docs/operations.md](../../docs/operations.md#host-agent).
- Jobs: none.
- Tools: none.
- Tables: `server_service_owners`.

## Known gaps

- `/add_org` makes the org with `service.new_organization`, not with `organizations.service.create_organization`. A taken prefix is not checked.
- `/remove_org` deletes the org row with no cascade.
