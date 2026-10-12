# Knowledge

Sources of text that agents search, such as web pages, handbooks and FAQs. A client writes a source as chunks, an officer uploads a document, or Platform crawls a URL on a schedule.

## Access

- Writers and searchers use a machine token with `knowledge:write`, `knowledge:read` or both. The org is the org of the token.
- Search covers the caller's org and the public sources. A public source shows in the results of every org. Thus only publishers can write one. The superadmin marks publishers on the Superadmin page of the dashboard (`PUT /api/superadmin/publishers/<org_id>` with `{"publisher": true}`). Orgs in `KNOWLEDGE_PUBLISHERS` (org prefixes, comma-separated) are publishers too.
- List, read and delete cover only the caller's org.
- Officers upload documents, manage crawls, change the search settings and test search on the Knowledge page of the dashboard, with no token.

## Routes

All routes are under `/api/knowledge`.

| Route | Scope | Does |
| --- | --- | --- |
| `GET /sources?category=` | read | The org's sources and their current version |
| `GET /sources/<key>` | read | One source |
| `PUT /sources/<key>` | write | Creates or replaces a source. 201 if the content changed, 200 if not |
| `DELETE /sources/<key>` | write | Deletes the source, its versions and its chunks |
| `POST /search` | read | Ranked passages. The audit log does not record searches |
| `PUT /crawls/<key>` | write | A crawled source: `url`, `category`, `fetch_every_hours` (1 to 720, default 24), `title`, `public`, `enabled` |
| `POST /crawls/run` | write | `{"key": ..., "force": false}`. Starts a crawl now. 202 |

The key is the writer's fixed name for the source: letters, digits and `._:/-`, 255 characters or fewer.

```json
{
  "category": "library",
  "title": "Library hours",
  "url": "https://example.edu/library/hours",
  "public": false,
  "content_hash": "optional; computed from the chunks if missing",
  "embedding_model": "required if the chunks have embeddings",
  "chunks": [
    {"ordinal": 0, "content": "...", "embedding": [1024 numbers], "level": 0, "parent_ordinal": 2}
  ]
}
```

- A `PUT` replaces the whole source. If `content_hash` is the hash of the current version, only the title, URL, category and public flag change.
- `level` 0 is page text. Levels 1 and higher are summaries of the rows below them. `parent_ordinal` points from a row to its summary. A source has up to 5000 chunks of up to 20000 characters.
- All chunks have an `embedding` (1024 numbers), or none do. If none do and an embedder is set, Platform makes the embeddings. If there is no embedder, the source is text only.

The `POST /search` body has `query`, and optional `category`, `top_k` (1 to 50; the org's setting, default 8), `window` (0 to 5; the org's setting, default 0), and `embedding` with `embedding_model` to search with the caller's own vector. Each result has `chunk_id`, `source_key`, `title`, `url`, `category`, `public`, `content`, `score` and `fetched_at`. `dense` in the response shows if the vector search ran. The `knowledge.search` tool runs the same search.

## Crawls

The `knowledge.crawl_due` job runs every 10 minutes. It crawls up to `KNOWLEDGE_CRAWL_BATCH` sources that are due, with `KNOWLEDGE_CRAWL_GAP_SECONDS` between fetches to the same host. Each crawl does these steps:

1. Checks that the URL is http or https and resolves only to public addresses. It follows redirects one at a time and checks each one. Thus a source cannot point Platform at its own network.
2. Reads robots.txt with `KNOWLEDGE_USER_AGENT` and skips pages that it does not allow.
3. Gets the page through the org's Firecrawl (Integrations tab of Explore, else `FIRECRAWL_URL`), else with a GET of up to 10 MB.
4. Stops if the page hash did not change, unless `force` is set.
5. Removes navigation, headers, footers, forms and scripts. Splits the text into chunks of the org's passage size with the page title on each, makes the embeddings and replaces the source's version. The old version and its chunks are deleted.
6. Refuses the new text if it is less than half of the last version (when that was 500 characters or more), so a broken page cannot remove a good index. `force` accepts it.

```mermaid
flowchart LR
  job["knowledge.crawl_due"] --> check["Check URL and robots.txt"]
  check --> fetch["Fetch: Firecrawl or GET"]
  fetch --> same{"Same page hash?"}
  same -->|"yes, no force"| stop["Stop, keep version"]
  same -->|no| extract["Extract text"]
  extract --> chunk["Chunk with page title"]
  chunk --> embed["Embed if embedder"]
  embed --> write["New version in knowledge_versions and knowledge_chunks"]
```

A source's `crawl` field shows its schedule, `last_attempt_at` and `last_error`.

A page that starts to fail keeps its last chunks; the error shows on the source. Delete the source to remove them.

## Uploads

`POST /api/dashboard/<org>/knowledge/documents` takes a multipart form: `files` (1 to 20 files, 10 MB each, 25 MB together), `folder` (default `upload`), `category` (default `documents`) and `public`. Platform reads `.txt`, `.md`, `.markdown`, `.csv`, `.html`, `.htm`, `.pdf` and `.docx`. Each file becomes a source with the key `<folder>/<file name>`, in lower case. The same name again replaces the source; if the file and the passage size did not change, nothing is written. A file that fails does not stop the others. The response lists each file with its key, passage count and error.

A PDF must have a text layer. Platform does not read scanned pages.

## Read a source

`GET /api/dashboard/<org>/knowledge/sources/<key>` gives the full text of one source, one page at a time. An org reads its own sources and public sources. It cannot read the private sources of another org. If the org has no source with the key, the oldest public source with that key is used.

- `chunk`: a `chunk_id` from a search result. The source that holds this chunk is used. `focus` lists the page text rows the chunk covers, and the page starts near them.
- `offset`: the first page text row of the page. Give `next_offset` to read the next page.

The response has `source` (the fields of the sources list, plus `own` and `text_chars`), `passages` (`id`, `ordinal`, `text`, in order), `focus`, `offset`, `next_offset` (`null` at the end) and `total`. A page holds up to 500 rows or 200,000 characters. Summary rows are not in the text. The text that a row repeats from the end of the row before (`chunk_overlap`) is removed. The `knowledge.read_source` tool gives the same pages as one `text`.

On the Knowledge page, select a source or a search result to open its text at `/<org>/knowledge/sources/<key>`. A search result opens with its passage marked.

## Run log

Each crawl and upload adds a row to `knowledge_runs`: the source key, `crawl` or `upload`, the time, the duration, if the index changed, the passage count and the error. Platform keeps the last 500 rows of each org. `GET /api/dashboard/<org>/knowledge/runs?limit=&failed=1` reads them; the Activity page of the dashboard shows them in the Knowledge runs tab.

## Org settings

Each org sets these on the Knowledge page (`GET` and `PUT /api/dashboard/<org>/knowledge/settings`). They are kept in the org config under `knowledge`. `null` returns a setting to its default.

| Setting | Range | Default | Does |
| --- | --- | --- | --- |
| `chunk_chars` | 100 to 4000 | `KNOWLEDGE_CHUNK_CHARS`, 300 | Passage size for crawls and uploads |
| `chunk_overlap` | 0 to half of `chunk_chars` | 0 | Text repeated from the end of the passage before |
| `mode` | `hybrid`, `text`, `vector` | `hybrid` | Which searches run. Without an embedder, every mode uses text |
| `top_k` | 1 to 50 | 8 | Results when the caller sends no `top_k` |
| `window` | 0 to 5 | 0 | Neighbor rows when the caller sends no `window` |
| `max_distance` | 0.05 to 2 | `KNOWLEDGE_MAX_DISTANCE`, 0.6 | Vector results farther than this are dropped |
| `rrf_k` | 1 to 200 | 60 | The constant of reciprocal rank fusion |

A new passage size applies when a source is indexed again. `POST /api/dashboard/<org>/knowledge/reindex` starts the `knowledge.reindex` job, which crawls every crawled source of the org with `force`. Upload a document again to split it again.

## Embeddings

Platform embeds a source when it writes the source: a crawl, an upload or a `PUT`. Each version keeps the name of the model, and each passage keeps the text it was embedded from. Vector search uses only passages of the org's current model. A passage of another model, or with no vector, is found by text search only.

So when an org adds an embedding service after it has sources, or changes the model, the old passages are not in the vector search. `knowledge.reembed` embeds them again from the stored text, with no new fetch:

- Saving the Embeddings integration starts the job for the org.
- The search settings on the Knowledge page show how many passages use the current model, and **Embed** starts the job (`POST /api/dashboard/<org>/knowledge/reembed`).
- The tools `knowledge.embeddings` (counts) and `knowledge.reembed` (confirm) do the same over MCP.

```mermaid
flowchart LR
  save["Save Embeddings integration"] --> job["knowledge.reembed"]
  button["Embed on Knowledge page"] --> job
  tool["knowledge.reembed tool"] --> job
  job --> stale["Current versions on another model or none"]
  stale --> embed["Embed stored passage text"]
  embed --> commit["Commit one source at a time"]
```

The job commits one source at a time. A source that fails keeps its old vectors. A change to the deployment default in Doppler starts no job; start it from the Knowledge page. Public sources of other orgs keep the model of the org that wrote them.

## Submodules

A [submodule](./submodules.md) is a domain, such as ASU, that an org subscribes to. Its pages are shared sources with no org: the deployment crawls and embeds them once, and the search of each subscribed org reads them. An org's search reads its own sources, public sources, and the sources of the submodules it subscribes to. Shared sources do not count against the org's `knowledge.sources` and `knowledge.passages` limits, and `knowledge.reindex` skips them.

The dashboard groups sources by domain: the part of the key before the first `/`.

## Search

1. Vector search: the chunks nearest to the query vector, of the same embedding model. It drops chunks farther than the org's `max_distance` (cosine distance). Mode `text` skips it.
2. Text search: Postgres full text search (`websearch_to_tsquery`, ranked by `ts_rank_cd`). On SQLite, a count of shared words. Mode `vector` skips it when the vector search ran.
3. Reciprocal rank fusion (k is the org's `rrf_k`) merges the lists.
4. A row is dropped if its summary has a higher rank.
5. With `window`, a page text result also has that number of rows on each side.

If the embedder fails during a search, the search uses text only. If it fails during a write, the write returns 502.

On Postgres with pgvector, the embedding column is `vector(1024)` with an HNSW index, and the text has a GIN index. If pgvector is not installed, the migration keeps the column as text and the vector search runs in Python. On SQLite both searches run in Python.

## Settings

An org sets its own embeddings service and Firecrawl on the Integrations tab of the dashboard Explore page ([integrations](../integrations.md)). The variables below are the deployment defaults.

| Variable | Default | Does |
| --- | --- | --- |
| `EMBEDDINGS_URL` | not set | An OpenAI-compatible base URL (`.../v1`). If neither the org nor this sets one, there is no embedder |
| `EMBEDDINGS_MODEL` | `default` | The model name sent to the URL and kept on each version |
| `EMBEDDINGS_API_KEY` | not set | The bearer token for the URL. If it is empty and the URL is OpenRouter's, Platform sends the OpenRouter key |
| `OPENROUTER_API_KEY` | not set | The default key of the OpenRouter integration ([integrations](../integrations.md#openrouter)) |
| `EMBEDDINGS_QUERY_PREFIX` | empty | Text put before queries, for models that need it |
| `KNOWLEDGE_MAX_DISTANCE` | 0.6 | The default of the org setting `max_distance` |
| `KNOWLEDGE_PUBLISHERS` | empty | Org prefixes that can write public sources, in addition to the ones the superadmin marks |
| `KNOWLEDGE_CHUNK_CHARS` | 300 | The default of the org setting `chunk_chars` |
| `KNOWLEDGE_CRAWL_BATCH` | 20 | Sources crawled in each run of the job |
| `KNOWLEDGE_CRAWL_GAP_SECONDS` | 2 | The time between fetches to one host |
| `KNOWLEDGE_USER_AGENT` | `PlatformKnowledgeBot/1.0` | Sent with fetches and matched against robots.txt |
| `FIRECRAWL_URL`, `FIRECRAWL_API_KEY` | not set | A Firecrawl for JavaScript pages |
