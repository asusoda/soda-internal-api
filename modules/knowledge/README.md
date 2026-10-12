# knowledge

Keeps an org's knowledge sources and searches them. Writers send a source as chunks, officers upload documents, or Platform crawls a URL on a schedule. Search merges a vector ranking and a text ranking over the org's sources and the public ones.

## Files

| File | Holds |
| --- | --- |
| `api.py`, `tools.py` | Machine routes for sources, search and crawls; the `knowledge.search` tool |
| `service.py` | Sources, versions and chunks; declares `knowledge:read` and `knowledge:write`; checks publishers (superadmin flag or `KNOWLEDGE_PUBLISHERS`) |
| `search.py` | Hybrid search with reciprocal rank fusion |
| `crawl.py` | Crawls: fetch, extract, chunk, embed, index; `queue` starts the crawl job for one source |
| `fetch.py` | Fetches with robots.txt, per-host pauses and public addresses only; registers the Firecrawl integration and uses the org's Firecrawl |
| `extract.py` | HTML to text, text to chunks, and the extractors that other modules register |
| `documents.py` | Uploaded files (text, Markdown, HTML, PDF, Word) indexed as sources |
| `settings.py` | Per-org passage size and search settings, kept in the org config |
| `runs.py` | The log of crawls and uploads |
| `reembed.py` | Passage counts by embedding model; embeds passages of another model again from their stored text |
| `embedder.py` | The OpenAI-compatible embeddings client; registers the Embeddings integration; `for_org()` picks the org's service or the default in Doppler, and the OpenRouter key for an OpenRouter URL with no key |
| `models.py`, `jobs.py` | Sources, versions, chunks (pgvector on Postgres), runs; the crawl and reindex jobs |

## Surface

- Routes: `/api/knowledge`. Machine tokens only, with `knowledge:read` or `knowledge:write`. The officer routes for sources, source text, crawls, uploads, settings, runs, submodules and reindex are in `modules/dashboard/api.py`.
- Jobs: `knowledge.crawl_due`, schedule `*/10 * * * *`; `knowledge.crawl_source`, `knowledge.reindex` and `knowledge.reembed`, on request. Saving the Embeddings integration starts `knowledge.reembed`.
- Tools: `knowledge.search`, `knowledge.sources`, `knowledge.read_source`, `knowledge.submodules`, `knowledge.settings`, `knowledge.embeddings`, `knowledge.runs` (scope `knowledge:read`); `knowledge.add_document`, `knowledge.delete_source` (confirm), `knowledge.set_crawl`, `knowledge.crawl_now`, `knowledge.sync_submodule`, `knowledge.update_settings`, `knowledge.reindex` (confirm), `knowledge.reembed` (confirm) (scope `knowledge:write`). Tools marked confirm run only with `confirm=true`.
- Webhook events: `knowledge.crawl_failed`, from `runs.record()`. See [docs/webhooks.md](../../docs/webhooks.md).
- Tables: `knowledge_sources`, `knowledge_versions`, `knowledge_chunks`, `knowledge_runs`.
- Search reads the org's own sources, public sources, and the shared sources of the submodules it subscribes to (`submodule_id`, no org; see the submodules module). Shared sources are crawled with the deployment's embedder, Firecrawl and chunk settings, and are not in an org's run log.
- Limits: `knowledge.sources` and `knowledge.passages` (`service.py`, shared sources not counted), `knowledge.uploads_per_day` and `knowledge.jobs_per_day` (`service.py`), `knowledge.embeddings_per_day` (`embedder.py`, each text that an org's embedder embeds). `knowledge.reindex` and `knowledge.reembed` run once at a time for each org, `knowledge.crawl_source` once for each source. The crawl of due sources takes one source of each org in turn. See [docs/limits.md](../../docs/limits.md).

See [docs/modules/knowledge.md](../../docs/modules/knowledge.md).
