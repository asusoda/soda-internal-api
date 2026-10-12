# Authentication

This page tells you how callers sign in and how a route decides who may call it. The code is in `modules/auth/`.

## Credentials

| Credential | Who uses it | Made by |
| --- | --- | --- |
| Platform access token and refresh token | Officers in `dashboard/` | Discord sign-in at `/api/auth/login` |
| Session cookie | The same officers, and members who signed in with Discord | Flask, signed with `SECRET_KEY` |
| Clerk session token | Members on the public website storefront | Clerk |
| Machine token (`plat_...`) | Apps, agents and CLIs | An officer, or the Godfather CLI sign-in |
| App token | Older integrations | `GET /api/auth/appToken`. Use a machine token for new work |

## Officer sign-in

1. The browser opens `GET /api/auth/login`. The API stores a random `state` in the session and sends the browser to Discord.
2. Discord sends the browser to `REDIRECT_URI` (`/api/auth/callback`) with a code.
3. The API checks the `state`, gets the Discord user, and finds the orgs where the user has the officer role. It reads the roles over Discord's REST API with `BOT_TOKEN`.
4. If the user is an officer of one or more orgs, the API makes a token pair. It sends the browser to `<CLIENT_URL>/auth/?code=...` with a one-time code that is valid for 60 seconds. If the user is not an officer, the URL has `error=Unauthorized Access`.
5. The client sends the code to `POST /api/auth/exchange` and gets `access_token` and `refresh_token`.

This diagram shows the same steps.

```mermaid
sequenceDiagram
  participant B as Browser
  participant A as API
  participant D as Discord
  B->>A: GET /api/auth/login
  A-->>B: Redirect to Discord with state
  B->>D: Sign in and approve
  D-->>B: Redirect to REDIRECT_URI with code
  B->>A: GET /api/auth/callback with code and state
  A->>D: Get the Discord user
  A->>D: Read roles with BOT_TOKEN
  A-->>B: Redirect to CLIENT_URL/auth/ with a one-time code
  B->>A: POST /api/auth/exchange with the code
  A-->>B: access_token and refresh_token
```

With `?client=dashboard`, step 4 uses `DASHBOARD_URL` in place of `CLIENT_URL`. If `BOT_TOKEN` is not set or Discord does not answer, the callback returns 503.

The API keeps the one-time codes in process memory. Thus the API runs one gunicorn worker.

## Platform tokens

`modules/auth/tokens.py` signs tokens with RS256. The key pair is in `./data/jwt_private.pem` and `./data/jwt_public.pem`. The API makes the pair at the first start.

Caution: do not delete the key files. If you delete them, all tokens become invalid and every officer must sign in again.

- An access token is valid for 30 minutes. It has `username` and `discord_id`.
- A refresh token is valid for 7 days. The database keeps only its SHA-256 hash.
- `POST /api/auth/revoke` and `POST /api/auth/logout` delete the refresh token and write the access token to `revoked_tokens`. A revoked token stays revoked after a restart and in every process.
- An app token is valid for 120 days and has `type: "app"` and the `discord_id` of the officer who made it. Officers list and revoke their app tokens at `/api/auth/appTokens`.

Clients use the status code to decide what to do:

- 401: the token is missing or invalid. Sign out.
- 403 on a token in the `Authorization` header: the token is expired. Call `POST /api/auth/refresh`, then send the request again.

A bad or expired token in the session cookie always gets 401.

## Machine tokens

An officer makes a machine token with `POST /api/organizations/<id>/tokens` (`name`, `kind` of `app`, `agent` or `cli`, `scopes`, optional `expires_days`, optional `limits`). `limits` narrows the tools of a connected service, such as `{"github": {"repos": ["my-org/*"], "tools": ["github.*issue*"]}}` ([integrations](./integrations.md#tools-for-agents)). The response shows the token once. The database keeps its SHA-256 hash and its first characters. `DELETE .../tokens/<id>` revokes it. A machine token with `tokens:manage` can do the same with the `tokens.*` tools. A token that it makes gets only its scopes and its limits.

- A machine token belongs to one org. A route for a different org refuses it with 403.
- A module declares its scopes with `scopes.declare(name, description, integration=None, uses=())` from `modules/auth/scopes.py`. `integration` names the service whose own tools the scope gives. `uses` names the services that the scope calls with the org's keys, such as `knowledge:read` and `embeddings`.
- `GET .../tokens` lists all scopes and, under `uses`, the services each scope calls. Under `integrations` it lists every integration: whether the org connected it, its own scopes, the tools each scope gives (`tools`), whether the tools come from the service's MCP server (`remote`), the Platform scopes that call it (`through`), the modules that use it (`used_by`), and its limits. The Tokens page shows each integration's scopes with their tools, and marks a Platform scope that calls a service with the service icon.
- Officer routes do not accept a machine token. It is not a JWT, so they return 401.
- `GET /api/auth/machine/whoami` returns the org, name, kind and scopes of a token.

`machine_scope_required` checks a machine token in this order.

```mermaid
flowchart TD
  token["Authorization: Bearer plat_..."] --> known{"SHA-256 hash in machine_tokens, not revoked or expired?"}
  known -->|no| r401["401"]
  known -->|yes| scope{"Token has the scope of the route?"}
  scope -->|no| r403a["403"]
  scope -->|yes| org{"Org in the URL is the token's org?"}
  org -->|no| r403b["403"]
  org -->|yes| view["View runs with g.machine_caller"]
```

## Decorators

The decorators are in `modules/auth/decorators.py`. `officer_route`, `machine_route` and `member_view` in `modules/auth/routes.py` add the decorator, a database session and the org to a view.

| Decorator | The caller must have |
| --- | --- |
| `auth_required` | A platform token, from an officer of the org in the URL (`org_prefix` or `org_id`) |
| `dual_auth_required` | A Clerk token, or a platform token. It sets `request.clerk_user_email` to the Clerk email or to the token's `username` |
| `org_officer_required` | After `dual_auth_required`: an officer of the org in the URL |
| `superadmin_required` | A platform token whose `discord_id` is in `SYS_ADMIN` |
| `member_required` | A Discord session (`session["discord_id"]`) of a member of the org's server |
| `machine_scope_required(scope)` | A machine token with the scope. It sets `g.machine_caller` |

`error_handler` from `core/http/responses.py` changes an unhandled error into `{"error": str(e)}` with status 500. Put the auth decorator above it. If you do not, an auth refusal becomes a 500.

## Access checks

`modules/auth/access.py` decides whether a caller may act on the org in the URL. A caller may act on an org if they have its officer role in Discord, or if they are the superadmin. The result for a Discord id stays in a cache for 60 seconds.

The checks have two modes:

- `ACCESS_ENFORCE=false` (default): the request goes through. The API logs one line for each request that it would refuse: `access decision=would_deny reason=... route=... org=... credential=...`.
- `ACCESS_ENFORCE=true`: the API refuses the same requests with 403 (503 for `bot_unavailable`) and logs `decision=deny`.

Superadmin routes do not follow the setting: they always refuse a caller who is not in `SYS_ADMIN` (`not_superadmin`, 403), because they add and remove orgs and set their limits.

The reasons are `not_org_officer`, `not_officer`, `not_superadmin`, `no_discord_id`, `no_platform_credential`, `bot_unavailable`, `oauth_state_mismatch`, `member_login_unverified`, `checkout_price_mismatch` (409) and `member_details_hidden`. For `member_details_hidden`, public member lists remove emails and student ids. They do not refuse the request.

Turn on enforcement when the log shows no `would_deny` lines from real callers.

## Members

- Clerk: `modules/auth/clerk.py` checks the token against `CLERK_SECRET_KEY` and `CLERK_AUTHORIZED_PARTIES` and gets the primary email. The email is the identity: the API finds the member by `users.email`.
- `POST /api/points/<org>/member_login` needs a Clerk token with the same email as the body. In report mode it logs `member_login_unverified` and goes through.
- Store sign-in: `GET /api/auth/store_login?org=<prefix>` sends the member to Discord with the `identify` scope. The callback at `REDIRECT_URI` writes `session["discord_id"]`, which `member_required` reads, and sends the browser to `<CLIENT_URL>/store/<prefix>`. With `?client=dashboard`, it uses `DASHBOARD_URL`. If the `state` does not match, the callback refuses the sign-in in report mode too, and adds `?error=` to the store URL.
- `/api/accounts/discord/callback` also writes `session["discord_id"]`.
- `GET /api/points/<org>/member_profile` finds the member by the Discord session, else by the session of `member_login`.
