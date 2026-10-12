# mcp

Serves the tools of other modules to apps and agents with a machine token: over MCP streamable HTTP at `/mcp`, and over HTTP at `/api/tools`. The module is Core and always on. A caller sees only the tools that its token scopes and its org's module switches allow. An OAuth token also sees the module tools that need a scope it does not have, and a call to one gets 403 `insufficient_scope` (step-up). The Tokens page of the dashboard shows how to connect.

## Files

| File | Holds |
| --- | --- |
| `server.py` | The MCP server app (`build_app`), run by `mcp_main.py`. With a public URL, it adds OAuth under that URL's path |
| `oauth.py` | OAuth for MCP clients: the public URL and discovery documents, registered clients and Client ID Metadata Documents (fetch, checks, cache), authorization requests, codes, grants, refresh with the officer check, the rate limit of each IP, and the provider of the mcp SDK |
| `oauth_pages.py` | The Discord sign-in and the consent page of the OAuth flow (`/mcp/oauth/login`, `/mcp/oauth/callback`, `/mcp/oauth/consent`) |
| `client_auth.py` | Client keys: `private_key_jwt` client assertions (RFC 7523), the keys of a client, and the authenticator of `/mcp/token` and `/mcp/revoke` |
| `edges.py` | HTTP rules in front of the SDK: the `Origin` check, the scope hint and step-up (403 `insufficient_scope`), `iss` on error redirects, the log of refused registrations, token requests and token revocations, and `client_id` from the Basic header |
| `models.py`, `jobs.py` | The OAuth tables; the job that deletes old OAuth rows |
| `runtime.py` | Lists and calls tools for a machine caller: scope, module switch and input checks; writes each call to the audit log; runs the `batch` tool |
| `api.py` | `GET /api/tools` lists tools; `POST /api/tools/<name>` calls one. The OAuth discovery documents at `/.well-known/` on the API host |

## Surface

- Routes: `/api/tools`, machine token required. `/.well-known/oauth-protected-resource/<path>` and `/.well-known/oauth-authorization-server[/<path>]`, open, 404 when OAuth is off. The MCP server (not the API) serves `/mcp` and, when OAuth is on, `/mcp/register`, `/mcp/authorize`, `/mcp/token`, `/mcp/revoke`, `/mcp/oauth/*` and the same discovery documents.
- Jobs: `mcp.cleanup_oauth`, schedule `15 * * * *`. It deletes expired requests, grants whose token is revoked or whose refresh token expired, registered clients with no grant that were not used for 7 days, cached metadata documents with no grant and no open request, and the `jti` of expired client assertions.
- Tools: `batch`, which runs 1 to 25 calls of other tools in order. Each call has its own scope check, module switch, confirm step and audit entry. A token sees `batch` when it can call one or more other tools. The other tools are `core.tools.TOOLS`, which the modules in `TOOL_MODULES` in `modules/manifest.py` fill.
- Tables: `oauth_clients`, `oauth_requests`, `oauth_grants`, `oauth_assertions`.
- Limits: `RATE_LIMITS` (`oauth.py`) for the OAuth routes, by client IP, in each process. `mcp.calls_per_minute` (`runtime.py`). Each tool call, also each call in a batch, counts. Over the limit the call returns 429. See [docs/limits.md](../../docs/limits.md).

See [docs/authentication.md](../../docs/authentication.md#oauth-for-mcp-clients) for OAuth and [docs/architecture.md](../../docs/architecture.md#tools-and-the-mcp-server).
