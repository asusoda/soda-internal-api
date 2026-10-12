# Integrations

An integration is an account or a service outside Platform, such as Notion or RunPod. An officer connects it one time on the Integrations tab of the dashboard Explore page. Then each module that needs it uses it. Each card shows whether the integration is connected, the modules that use it, a Test button and a link to its docs.

The page shows the cards in two groups:

- Accounts: the org's accounts at other services. Discord, GitHub, Google, Notion and RunPod. The ASU sign-in is on the ASU submodule card (see [Sign in to ASU](#sign-in-to-asu)).
- Services: servers that Platform calls for search and page reads. Embeddings, Firecrawl, OpenRouter and SearXNG.

The description of a card says what the officer connects, not what each module does with it. The "Used by" links show the modules.

## The integrations

| Integration | Keys (optional in brackets) | Default from Doppler | Used by |
| --- | --- | --- | --- |
| Discord | none for the org | `BOT_TOKEN` | Sign-in, LeetCode |
| Embeddings | `embeddings_url`, `embeddings_model`, [`embeddings_api_key`, `embeddings_query_prefix`] | `EMBEDDINGS_URL`, `EMBEDDINGS_MODEL`, `EMBEDDINGS_API_KEY`, `EMBEDDINGS_QUERY_PREFIX` | Knowledge, MCP |
| Firecrawl | `firecrawl_url`, [`firecrawl_api_key`] | `FIRECRAWL_URL`, `FIRECRAWL_API_KEY` | Knowledge, ASU |
| GitHub | `github_token` | none | CI runs, Apps, `github.*` agent tools |
| Google | `google_service_account` (JSON key) | `GOOGLE_SERVICE_ACCOUNT` | Calendar sync |
| Notion | `notion_api_key` | `NOTION_API_KEY` | Calendar sync |
| OpenRouter | `openrouter_api_key` | `OPENROUTER_API_KEY` | Knowledge, MCP (through Embeddings) |
| RunPod | `runpod_api_key` | none | Godfather, Hosting |
| Web search (SearXNG) | `searxng_url`, [`searxng_engines`] | `SEARXNG_URL`, `SEARXNG_ENGINES` | ASU |

The keys are org secrets, encrypted with `SECRETS_KEY`. The API never returns a secret key. It returns the value of a field that is not secret, such as a URL or a model name, so the form can show it. When an org saves its own keys, they replace the deployment default for that org as a whole: Platform never mixes an org URL with a deployment key. An org must set every required field. Discord is set only in Doppler, for every org.

This diagram shows how Platform saves and reads the keys.

```mermaid
flowchart LR
  officer["Officer: Integrations tab"] --> put["PUT /api/dashboard/#lt;org#gt;/integrations/#lt;key#gt;"]
  put --> save["registry.save checks the fields"]
  save --> set["secrets.set_secret encrypts with SECRETS_KEY"]
  set --> table[("org_secrets.ciphertext")]
  module["Module, such as knowledge"] --> values["org_values(db, org_id, key)"]
  values --> get["secrets.get_secret decrypts"]
  get --> table
  module -->|"org_values returns None"| env["Doppler default"]
```

A URL that an org saves must be http or https on a host with only public addresses. Platform checks this when the org saves the URL and again before each call, and does not follow redirects. A deployment default in Doppler can be on the private network, such as `http://firecrawl:3002`.

Search compares only vectors of the same embedding model. An org with its own model searches its own vectors, and the vectors of public sources only if the publisher used the same model. Text search still covers every source. On Postgres the vector column holds 1024 numbers, so the model must return 1024. Test says so when it does not.

A card has one of three states:

- **Connected**: the org saved its own keys.
- **Deployment default**: the org has no keys, and Doppler gives a default.
- **Not connected**: neither.

Test connects with the key the module uses and shows the result. It does not change anything.

If Firecrawl is not connected, knowledge reads pages with a plain GET. If SearXNG is not connected, the ASU web live query returns 503.

## Tools for agents

An agent with a machine token can use the tools of each service the org connects, through the same MCP server and `/api/tools`. The tools show up when the org connects the service and the token has its scope. The agent never gets the keys.

Platform gives tools in two ways:

- It passes the call to the service's own MCP server with the org's saved key. Use this when the server takes an API key.
- It passes the call to the service's own MCP server as an officer who signed in with the service (OAuth). Notion and Google work this way. See [Sign in with a service](#sign-in-with-a-service).
- It calls the service's API itself with the org's saved key. Google and Notion also work this way, with no sign-in.

| Service | How | Scopes and tools |
| --- | --- | --- |
| GitHub | `GITHUB_MCP_URL`, default `https://api.githubcopilot.com/mcp/`, with the org's GitHub token | `github:read`: the tools the server marks read-only. `github:write`: the other tools |
| RunPod | `RUNPOD_MCP_URL`, default `https://mcp.getrunpod.io/`, with the org's RunPod key | `runpod:read`: the tools the server marks read-only. `runpod:write`: the other tools |
| Google | The Calendar, Drive, Sheets and Gmail APIs, with the org's service account key | `google:read`: `calendar_list`, `calendar_events`, `drive_search`, `drive_read`, `sheets_read`. `google:write`: `calendar_create_event`, `sheets_append`. `gmail:read`: `gmail_search`, `gmail_read`. `gmail:send`: `gmail_send` |
| Notion | The Notion API, with the org's integration token | `notion:read`: `search`, `read_page`, `query_database`. `notion:write`: `create_page` |
| Notion, signed in | `NOTION_MCP_URL`, default `https://mcp.notion.com/mcp`, as the officer who signed in | `notion:read`: the tools the server marks read-only, such as `notion.notion-search`. `notion:write`: the other tools |
| Google, signed in | Google's Gmail, Drive and Calendar MCP servers (`gmailmcp`, `drivemcp`, `calendarmcp.googleapis.com`), as the officer who signed in | `gmail.*`: `gmail:read` and `gmail:send`. `drive.*` and `calendar.*`: `google:read` and `google:write` |
| Web search | The org's SearXNG, or the one in Doppler | `web:read`: `search` |
| ASU, signed in | Sun Devil Central in a headless browser, with the cookies of the officer who signed in | `asu:read`: `asu.clubs`, `asu.events` |

- A tool name starts with the service key, such as `github.list_issues` or `google.drive_search`.
- A tool that changes something runs only with `confirm=true`. Without it, the call returns what it would do.
- Google and Notion tools use only the org's own keys, never a default in Doppler. So an agent reads only its own org's data.
- Google: share a calendar, Drive file or Sheet with the service account's email to let the tools see it. A service account has no mailbox, so the Gmail tools show only when the org sets **Act as Workspace user**. That works only in a Google Workspace domain whose admin allows the service account's client ID these scopes under domain-wide delegation: `calendar`, `drive.readonly`, `spreadsheets`, `gmail.readonly`, `gmail.send`.
- Notion: share each page or database with the integration in Notion.
- Token limits narrow a token further. `repos` lists the GitHub repos a call may act on, as `owner/name` or `owner/*`. With `repos`, the token sees only tools that take one repo. `tools` lists GitHub tool name patterns, such as `github.*issue*`. Set both on the Tokens page.
- Each call is in the audit log and its failures are in the error log, as for other tools.
- The list of tools of each MCP server is kept for 10 minutes per org. The key must allow what the tools do, for example write access to Issues and Pull requests for the GitHub write tools.

### Sign in with a service

Some MCP servers take no API key. The officer signs in with the service, and the agent acts as that person. On the Integrations tab of Explore, click **Sign in with Notion** or **Sign in with Google**. **Sign out** removes the saved sign-in. Platform keeps the sign-in as the org secret `oauth_<key>` and refreshes it before it expires.

- The API must have a public URL in `ACCOUNTS_BASE_URL`. The service sends the browser back to `<ACCOUNTS_BASE_URL>/api/dashboard/integrations/oauth/callback`.
- Notion: nothing to set up. Platform finds the sign-in URLs from the MCP server and registers itself as a client.
- Google: Platform uses the Google OAuth app of connected accounts, `ACCOUNTS_GOOGLE_CLIENT_ID` and `ACCOUNTS_GOOGLE_CLIENT_SECRET`. In Google Cloud, add the callback URL above to the app's redirect URIs, and turn on the Gmail, Drive and Calendar MCP APIs. Google's MCP servers are a Developer Preview, so the project must be enrolled.
- A sign-in must finish within 15 minutes.

### Sign in to ASU

Sun Devil Central, the ASU club system, needs an ASU sign-in. An officer signs in one time, and agents then search its clubs and events. Only an org that subscribes to the ASU submodule can sign in; the routes and tools refuse the others. The code is in `submodules/asu/signin/`.

1. On the Shared tab of Explore, subscribe to Arizona State University, then click **Sign in to ASU** on its card.
2. Type your NetID and password, and click **Sign in**.
3. Approve the Duo push on your phone. If Duo shows a code, the card shows the same code. Type it in the Duo app.
4. When the card shows **Signed in**, give a token the `asu:read` scope.

- Platform keeps only the browser cookies, as the org secret `asu_session`, encrypted with `SECRETS_KEY`. It does not keep, log or audit the NetID or the password.
- The tools `asu.clubs` and `asu.events` show only when the org subscribes to ASU and has a saved sign-in. They are read-only. Their results go only to the caller. Platform never adds them to knowledge.
- `asu.events` also reads the public ASU events calendar. If the sign-in expired, it returns the calendar and says that it did not read Sun Devil Central.
- When a page load ends on a sign-in page, the sign-in has expired. The tools return an error, the card shows **Sign-in expired**, and Platform sends the event `asu.session_expired` one time. The notification links to the Shared tab of Explore. Sign in again to clear it.
- **Sign out** removes the saved cookies.
- The sign-in runs in a browser on the API. The API process keeps the state of each attempt in memory, so run one API worker (the default).

The browser is optional. The default image does not have it, and the card says how to add it. To add it on the API host:

```bash
uv sync --extra browser
uv run playwright install --with-deps chromium
```

Then restart the API and the MCP server. Tests do not need the browser: they use a fake one.

To pass through another service's MCP server, add a `RemoteServer` in `modules/integrations/servers.py`: its URL, the headers that sign in with the org's keys and a read and a write scope. For a server that takes OAuth, register a `Service` in `modules/integrations/oauth.py` and use `_oauth_headers(<key>)`. To call a service's API, add a file in `modules/integrations/` with `@tool(..., integration="<key>", available=<check>)`, and import it in `modules/integrations/tools.py`.

## Routes

All routes are under `/api/dashboard/<org>`, for officers of the org.

| Route | Does |
| --- | --- |
| `GET /integrations` | Each integration, its fields, its state and the modules that use it, and the OAuth sign-ins (`oauth`) |
| `PUT /integrations/<key>` | Body `{"fields": {"<secret name>": "<value>" or null}}`. null removes that key |
| `POST /integrations/<key>/test` | `{"ok": true or false, "message": "..."}` |
| `POST /integrations/<key>/oauth` | Starts a sign-in. Returns `{"url": "..."}` to open in the browser |
| `DELETE /integrations/<key>/oauth` | Removes the saved sign-in |
| `GET /submodules/asu/signin` | The ASU sign-in: `signed_in`, `signed_in_by`, `signed_in_at`, `expired_at`, `blocked` and the latest `attempt`. The dashboard polls it during a sign-in |
| `POST /submodules/asu/signin` | Body `{"netid": "...", "password": "..."}`. Starts a sign-in and returns 202 with the state. 404 when the org does not subscribe to ASU. 409 when one is running or the API cannot sign in |
| `DELETE /submodules/asu/signin` | Removes the saved ASU sign-in. Allowed after the subscription ends |

An `attempt` has a `state`: `running`, `duo_code` (`code` has the number to type in Duo), `done` or `failed` (`reason` says why, such as a NetID or password that ASU did not accept).

`GET /api/dashboard/integrations/oauth/callback` takes no login. The service calls it with `state` and `code`; a `state` works one time. It sends the browser back to the Integrations tab of Explore.

The older routes `/api/organizations/<id>/secrets/<name>` still work and write the same secrets.

## What stays in Doppler

A setting stays in Doppler when it is the same for every org or when it is about the server itself:

- Server and security: `DATABASE_URL`, `SECRET_KEY`, `SECRETS_KEY`, `ACCESS_ENFORCE`, `DISABLED_ROUTES`, `SENTRY_DSN`, `LOG_FORMAT`, `JOBS_BACKEND`, `MCP_PORT`.
- The one Discord app and the sign-in: `BOT_TOKEN`, `CLIENT_ID`, `CLIENT_SECRET`, `REDIRECT_URI`, `SYS_ADMIN`, the Clerk keys.
- The OAuth apps of connected accounts (`ACCOUNTS_*`). Their callback URLs are on the API, so one app serves every org.
- URLs of the frontends and CORS: `CLIENT_URL`, `DASHBOARD_URL`, `CORS_EXTRA_ORIGINS`.
- Limits and schedules of jobs: `CALENDAR_SYNC_CRON`, `AUDIT_RETENTION_DAYS`, `ERROR_RETENTION_DAYS`, `ERROR_WEBHOOK_URL`, `AGENT_RETENTION_DAYS`, `UPTIME_RETENTION_DAYS`, `KNOWLEDGE_CRAWL_*`, `SUBMODULE_QUERY_MAX_CHARS`.
- `GODFATHER_CLI_NAME`: the name of the one CLI that talks to this API.

These settings moved to the dashboard, and the Doppler value is now the default for orgs that set none:

| Doppler | Dashboard |
| --- | --- |
| `EMBEDDINGS_*`, `FIRECRAWL_*`, `SEARXNG_*`, `NOTION_API_KEY`, `OPENROUTER_API_KEY` | Integrations |
| `GODFATHER_POD_IMAGE` | Godfather > Settings |
| `KNOWLEDGE_PUBLISHERS` | Superadmin > Knowledge publishers. Orgs in Doppler stay publishers |
| `KNOWLEDGE_CHUNK_CHARS`, `KNOWLEDGE_MAX_DISTANCE` | Knowledge > Search settings |
| `LEETCODE_*` | LeetCode. The Doppler post is the older post for one server |

## Add an integration

1. Write a test function `(db, org_id) -> str` that connects and returns a short result. It raises `IntegrationError` with the reason when it fails. It never puts a key in the message.
2. Call `register(Integration(...))` from `core/integrations/registry.py` in the file that owns the client: a file in `core/integrations/` for a service that core uses, or a module file. Give the key, title, description, fields, docs page and test. The description says what the officer connects, such as "Connect the org's Notion workspace." `register` declares each field as an org secret. Give a field `secret=False` when the dashboard may show its value, `optional=True` when the org may leave it empty, and `kind="url"` for a URL that must be public.
3. Read the org's values with `org_values(db, org_id, key)`. It returns None when the org did not set every required field; then use the default in Doppler.
4. In each module that reads the service, call `use("<key>", "<module>")` at the top of the file.
5. Add the module name to `MODULES` in `dashboard/src/pages/explore/integrations.tsx` if it has a dashboard page, and an icon to `ICONS`. If it is an account, add its key to the Accounts group in `GROUPS`. A key in no group shows under Services.
6. Add a row to the table on this page.
