# superadmin

Routes for the superadmins of the deployment (the Discord user ids in `SYS_ADMIN`, comma-separated): add and remove orgs for Discord servers, set an org's officer role, list a server's roles, read the audit log and errors of all orgs, see the server's health, and set each org's limits.

## Files

| File | Holds |
| --- | --- |
| `api.py` | `/check`, `/dashboard`, `/guild_roles/<guild_id>`, `/add_org/<guild_id>`, `/remove_org/<org_id>`, `/update_officer_role/<org_id>`, `/audit`, `/publishers`, `/errors`, `/server`, `/limits`, `/limits/<org_id>` (GET, PUT) |
| `service.py` | The superadmin check, servers with no org, an officer's orgs, server roles, role checks, new orgs, `server()` (the server's health, the bot and the job queue) and each org's limits (`all_limits`, `org_limits`, `set_org_limits`) |

## Surface

- Routes: `/api/superadmin`. Each route except `/check` needs a superadmin, also when `ACCESS_ENFORCE` is false. `/check` answers for the caller's own token. `PUT /limits/<org_id>` takes `{"limits": {key: number | null | "default"}}`; see [docs/limits.md](../../docs/limits.md).
- Jobs: none.
- Tools: none.
- Tables: none.

## Known gaps

- `/add_org` makes the org with `service.new_organization`, not with `organizations.service.create_organization`. A taken prefix is not checked.
- `/remove_org` deletes the org row with no cascade.
