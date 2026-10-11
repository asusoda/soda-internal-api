# submodules

Loads the sub-modules in the `submodules/` folder. Adds a sub-module's pages to an org's knowledge as crawled sources and runs the sub-module's live queries. The [feeds](../feeds/README.md) module reads sub-module feeds and the accounts module reads `canvas_url`. A sub-module is content for one campus or topic, not a feature. See [submodules/README.md](../../submodules/README.md) to write one.

## Files

| File | Holds |
| --- | --- |
| `catalog.py` | Loads each folder in `submodules/` once per process and registers its extractors with knowledge |
| `service.py` | `list_submodules()`, `sync()`, `query()` and the indexing of query results |
| `api.py`, `tools.py` | Machine routes to list sub-modules, list and run live queries and sync pages; the old `/api/asu` routes; the `submodules.query` tool |
| `types.py` | `Submodule`, `Source`, `QuerySource`, `QueryParam`, `Feed`, `QueryError` |
| `queries.py`, `params.py` | Parameter checks and the run of one live query; helpers that map parameters to URL values |
| `http.py`, `text.py` | Page, JSON and feed fetches; text and Markdown helpers for extractors |
| `search.py`, `web.py` | `SUBMODULE_QUERY_MAX_CHARS`; the SearXNG integration; `query_scope()` sets the org's SearXNG and Firecrawl; the `web` live query that a sub-module can add |
| `jobs.py` | The indexing job |

## Surface

- Routes: `/api/submodules`, and `/api/asu` for clients of the old asu module. Machine tokens only: `knowledge:read` to list and query, `knowledge:write` to sync.
- Jobs: `submodules.index_result`, started after a live query.
- Tools: `submodules.query` (scope `knowledge:read`). `knowledge.submodules` and `knowledge.sync_submodule` are in the knowledge module.
- Tables: none. It writes to the knowledge tables.

See [docs/modules/submodules.md](../../docs/modules/submodules.md).
