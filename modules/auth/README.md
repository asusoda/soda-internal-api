# auth

Signs officers and members in with Discord and decides who can call a route: platform tokens, app tokens, machine tokens, and the decorators that all modules use.

## Files

| File | Holds |
| --- | --- |
| `api.py` | Discord sign-in and callback, code exchange, refresh, revoke, logout, app tokens, `/machine/whoami` |
| `decorators.py` | `auth_required`, `dual_auth_required`, `member_required`, `org_officer_required`, `superadmin_required`, `machine_scope_required` |
| `routes.py` | `officer_route`, `machine_route`, `member_view` and `token_org` |
| `access.py` | The caller of a request and the officer and superadmin checks; logs officer refusals until `ACCESS_ENFORCE=true`, and always refuses a caller who is not a superadmin on superadmin routes |
| `tokens.py` | `TokenManager`: RS256 keys in `./data`, access, refresh and app tokens, revocation |
| `machine_tokens.py`, `scopes.py` | Machine tokens (stored as a hash); the scopes that modules declare |
| `clerk.py` | `verify_clerk_token` |
| `models.py`, `jobs.py` | Token tables; the refresh token cleanup job |

## Surface

- Routes: `/api/auth`. Sign-in, callback, exchange, refresh and logout are open. `/validToken`, `/revoke`, `/name` and the app token routes need a platform token. `/machine/whoami` needs a machine token.
- Jobs: `auth.cleanup_tokens`, schedule `0 * * * *`.
- Tools: none.
- Tables: `refresh_tokens`, `revoked_tokens`, `app_tokens`, `machine_tokens`, `sessions` (not used).

See [docs/authentication.md](../../docs/authentication.md).

## Known gaps

- No `service.py`. The app token routes in `api.py` query and commit `app_tokens` in the view.
