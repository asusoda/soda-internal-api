# Limits

All orgs on a deployment share the same processes, containers and database. Limits stop one org from using up the server, the disk or the shared keys for the other orgs. Each module declares its limits, and the superadmin can change them for each org.

## Kinds of limit

| Kind | Caps | Example | Over the limit |
| --- | --- | --- | --- |
| Count | How many of a thing the org keeps | `knowledge.sources`, `godfather.pods` | 409, nothing is added |
| Rate | How much the org uses in a minute, an hour or a day | `knowledge.embeddings_per_day`, `mcp.calls_per_minute` | 429, nothing is counted |

A rate counter starts again at the start of each window, in UTC. The `usage_counters` table keeps the counters, and the `limits.prune` job deletes counters older than 8 days.

## Limits and defaults

| Key | Module | Limit | Default |
| --- | --- | --- | --- |
| `knowledge.sources` | knowledge | Sources, crawled, uploaded or written by a client | 1,000 |
| `knowledge.passages` | knowledge | Passages of the current versions of all sources | 250,000 |
| `knowledge.embeddings_per_day` | knowledge | Texts embedded a day, for knowledge and agent memory | 500,000 |
| `knowledge.uploads_per_day` | knowledge | Files uploaded a day | 500 |
| `knowledge.jobs_per_day` | knowledge | Crawls, re-indexes and re-embeds that an officer or a token starts | 200 |
| `agents.conversations` | agents | Agent conversations, for Agent memory | 5,000 |
| `agents.memories` | agents | Agent memories, for Agent memory | 20,000 |
| `godfather.pods` | godfather | Pods | 10 |
| `runpod.apps` | runpod | Hosting apps | 25 |
| `runpod.server_apps` | runpod | Apps on This server | 2 |
| `runpod.server_memory_mb` | runpod | Memory of the apps on This server, from their manifests, in MB | 1,024 |
| `uptime.monitors` | uptime | Uptime monitors | 50 |
| `alerts.destinations` | alerts | Alert destinations | 20 |
| `submodules.subscriptions` | submodules | Shared content the org subscribes to. Its pages count against no org | 20 |
| `mcp.calls_per_minute` | mcp | Tool calls a minute, over MCP and `/api/tools`. Each call in a batch counts | 300 |

Each embedding counts, whichever service the org uses. A search over the embedding limit searches on text only and does not fail. A crawl or an upload over a limit records the error on the source or the file, and the other sources and files go on.

## Who pays

Each limit says who pays for what it counts (`paid_by`), so an officer sees what uses the org's budget.

| `paid_by` | Means | Example | Counts against the org |
| --- | --- | --- | --- |
| `org` | The org's own data and apps | Its own knowledge sources, its pods and apps | Yes, as counts. The default for a count limit |
| `metered` | A shared service the org uses | The deployment's embedder, the shared MCP server, the job worker | Yes, as rates. The default for a rate limit |
| `shared` | Content the deployment makes once for every org | A submodule's pages | No. It has no limit of an org |

A limit can name the integrations whose deployment default it meters (`integrations=("embeddings",)`). When an org uses the deployment's key for such an integration, the Integrations tab says which limits its use counts against.

The dashboard shows who pays:

- Settings > Limits puts the org's own limits and the metered ones in two groups.
- A module card on Explore lists the limits that its use counts against.
- The Shared tab of Explore marks each part of shared content: its pages are shared, its live query results and feeds are the org's own.
- The Integrations tab shows "Platform's key" and the limits it counts against, or the org's own key.

## The value of a limit

The value for an org is the first of these that is set:

1. The org's override. The superadmin sets it on the Superadmin page or with `PUT /api/superadmin/limits/<org_id>`. The `org_limits` table keeps it.
2. `LIMIT_<KEY>` in Doppler: the key in upper case, with `_` for `.`. For example, `LIMIT_KNOWLEDGE_SOURCES=200`. The value `unlimited` removes the limit.
3. The default in the table above.

An override can be a whole number, `null` (no limit) or `"default"` (remove the override).

## Where to see them

- Officers see the limits of the modules that are on, and what the org uses, on Settings. `GET /api/organizations/<org_id>/limits` returns the same list.
- Agents call the `org.limits` tool (scope `org:read`).
- The superadmin sees each org, its use and its overrides on the Superadmin page, with `GET /api/superadmin/limits`. A limit that the org uses 80% of or more is marked.

## Other protections

| Protection | Setting | Default |
| --- | --- | --- |
| One run at a time of `knowledge.reindex` and `knowledge.reembed` for each org, and of `knowledge.crawl_source` for each source. A second request gets 409 | `once` on the job in `core/jobs.py` | on |
| Jobs that run at the same time in a process with the inline (SQLite) backend | `JOB_THREADS` | 4 |
| The crawl of due sources takes one source of each org in turn. Orgs that are inactive or have knowledge off are left out | `KNOWLEDGE_CRAWL_BATCH` | 20 |
| The largest request body, in MB. A bigger body gets 413 | `MAX_REQUEST_MB` | 110 |
| Memory and CPU of each container | `*_MEM_LIMIT`, `*_CPUS`. See [Operations](./operations.md#container-limits) | see Operations |

## Add a limit to a module

1. Declare the limit at the top of the module's `service.py` with `limits.declare(...)` from `core/limits.py`. A count limit needs a `usage` function that counts what the org has. A rate limit needs a `window`. Set `paid_by` when the default (`org` for a count, `metered` for a rate) is not right, and `integrations` when the limit meters an integration's deployment default.
2. Before the module adds a thing, call `limits.check(db, org_id, KEY)`. For a rate, call `limits.consume(db, org_id, KEY, amount)` before the work.
3. Add the limit to the table on this page and to the module's `README.md`.

`consume()` flushes and does not commit. If the request fails and rolls back, the use is not counted. A read route that consumes must commit.

## Not limited yet

- Container limits cap each service, not each org. One org can still use all of the API's memory.
- Data is kept apart by `organization_id` in the code. The database does not enforce it.
- Agent conversations and memories have no count limit, only `AGENT_RETENTION_DAYS`.
- Points, store, calendar and LeetCode data have no limits. They are small.
