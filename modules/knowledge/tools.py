"""Knowledge tools."""

from functools import partial

from core.tools import tool as _tool
from modules.knowledge import crawl, documents, embedder, reembed, runs, search, service, settings
from modules.submodules import service as submodules

# Every tool here needs the knowledge module on for the caller's org
tool = partial(_tool, module="knowledge")


@tool(
    "knowledge.search",
    description=(
        "Search the organization's knowledge and public sources. Returns ranked passages with their "
        "source title, URL and fetch time."
    ),
    scope="knowledge:read",
    input_schema={
        "type": "object",
        "properties": {
            "query": {"type": "string", "minLength": 1, "maxLength": 1000},
            "category": {"type": "string", "maxLength": 100},
            "top_k": {"type": "integer", "minimum": 1, "maximum": search.MAX_TOP_K},
            "window": {"type": "integer", "minimum": 0, "maximum": search.MAX_WINDOW},
        },
        "required": ["query"],
        "additionalProperties": False,
    },
)
def knowledge_search(
    db, org, caller, query: str, category: str | None = None, top_k: int | None = None, window: int | None = None
):
    return search.search(
        db,
        int(org.id),
        query,
        category=category,
        top_k=top_k,
        window=window,
        embedder=embedder.for_org(db, int(org.id)),
    )


KEY = {"type": "string", "minLength": 1, "maxLength": 255}
NO_ARGS = {"type": "object", "properties": {}, "additionalProperties": False}


@tool(
    "knowledge.sources",
    description="The org's knowledge sources: key, title, URL, category, last fetch and last error.",
    scope="knowledge:read",
    input_schema={
        "type": "object",
        "properties": {"category": {"type": "string", "maxLength": 100}},
        "additionalProperties": False,
    },
)
def knowledge_sources(db, org, caller, category: str | None = None):
    return {"sources": service.list_sources(db, int(org.id), category)}


@tool(
    "knowledge.read_source",
    description=(
        "Read the full text of one source of the org or a public source, a page at a time. Give next_offset as "
        "offset to read the next page."
    ),
    scope="knowledge:read",
    input_schema={
        "type": "object",
        "properties": {"key": KEY, "offset": {"type": "integer", "minimum": 0}},
        "required": ["key"],
        "additionalProperties": False,
    },
)
def knowledge_read_source(db, org, caller, key: str, offset: int | None = None):
    page = service.read_source(db, int(org.id), key, offset=offset)
    return {
        "source": page["source"],
        "text": "\n".join(p["text"] for p in page["passages"]),
        "offset": page["offset"],
        "next_offset": page["next_offset"],
        "total": page["total"],
    }


@tool(
    "knowledge.add_document",
    description=(
        "Add or replace a text document as a source. name ends in .md, .txt, .csv or .html; the key is "
        "folder/name. The same key replaces the old text."
    ),
    scope="knowledge:write",
    input_schema={
        "type": "object",
        "properties": {
            "name": {"type": "string", "minLength": 1, "maxLength": 200},
            "content": {"type": "string", "minLength": 1, "maxLength": 2_000_000},
            "folder": {"type": "string", "maxLength": 41},
            "category": {"type": "string", "maxLength": 100},
            "public": {"type": "boolean"},
        },
        "required": ["name", "content"],
        "additionalProperties": False,
    },
)
def knowledge_add_document(
    db, org, caller, name: str, content: str, folder: str = "agent", category: str | None = None, public: bool = False
):
    upload = documents.Upload(name, content.encode())
    form = {"folder": folder, "category": category, "public": public}
    return documents.upload(db, int(org.id), str(org.prefix), [upload], form, embedder.for_org(db, int(org.id)))


@tool(
    "knowledge.delete_source",
    description="Delete a knowledge source and all of its passages.",
    scope="knowledge:write",
    confirm=True,
    input_schema={"type": "object", "properties": {"key": KEY}, "required": ["key"], "additionalProperties": False},
)
def knowledge_delete_source(db, org, caller, key: str):
    service.delete_source(db, int(org.id), key)
    return {"deleted": key}


@tool(
    "knowledge.set_crawl",
    description="Create or change a crawled web source. The crawl job fetches it every fetch_every_hours.",
    scope="knowledge:write",
    input_schema={
        "type": "object",
        "properties": {
            "key": KEY,
            "url": {"type": "string", "maxLength": 2000},
            "category": {"type": "string", "maxLength": 100},
            "title": {"type": "string", "maxLength": 500},
            "fetch_every_hours": {"type": "integer", "minimum": 1},
            "public": {"type": "boolean"},
            "enabled": {"type": "boolean"},
        },
        "required": ["key", "url", "category"],
        "additionalProperties": False,
    },
)
def knowledge_set_crawl(db, org, caller, key: str, **data):
    return crawl.schedule(db, int(org.id), str(org.prefix), key, data)


@tool(
    "knowledge.crawl_now",
    description="Start a crawl of one source now. force re-indexes it when the text did not change.",
    scope="knowledge:write",
    input_schema={
        "type": "object",
        "properties": {"key": KEY, "force": {"type": "boolean"}},
        "required": ["key"],
        "additionalProperties": False,
    },
)
def knowledge_crawl_now(db, org, caller, key: str, force: bool = False):
    crawl.queue(db, int(org.id), str(org.prefix), key, force=force)
    return {"queued": key}


@tool(
    "knowledge.submodules",
    description="Submodules the org can subscribe to, such as a campus submodule. Same as submodules.list.",
    scope="knowledge:read",
)
def knowledge_submodules(db, org, caller):
    return {"submodules": submodules.list_submodules(db, int(org.id))}


@tool(
    "knowledge.sync_submodule",
    description="Subscribe the org to a submodule's shared pages, then start the crawl of the pages that are due. "
    "Same as submodules.subscribe.",
    scope="knowledge:write",
    input_schema={
        "type": "object",
        "properties": {"name": {"type": "string", "minLength": 1, "maxLength": 64}},
        "required": ["name"],
        "additionalProperties": False,
    },
)
def knowledge_sync_submodule(db, org, caller, name: str):
    counts = submodules.sync(db, int(org.id), str(org.prefix), name)
    crawl.start_crawl_due()
    return counts


@tool("knowledge.settings", description="The org's chunking and search settings.", scope="knowledge:read")
def knowledge_settings(db, org, caller):
    return {"settings": settings.for_org(db, int(org.id)), "defaults": settings.defaults()}


@tool(
    "knowledge.update_settings",
    description="Change chunking and search settings. null returns a setting to its default. Run reindex after.",
    scope="knowledge:write",
    input_schema={
        "type": "object",
        "properties": {"settings": {"type": "object", "minProperties": 1}},
        "required": ["settings"],
        "additionalProperties": False,
    },
)
def knowledge_update_settings(db, org, caller, **arguments):
    return {"settings": settings.update(db, int(org.id), arguments["settings"])}


@tool(
    "knowledge.reindex",
    description="Crawl every crawled source again so new chunk settings apply.",
    scope="knowledge:write",
    confirm=True,
    input_schema=NO_ARGS,
)
def knowledge_reindex(db, org, caller):
    crawl.queue_job(db, int(org.id), "knowledge.reindex", org_id=int(org.id))
    return {"queued": True}


@tool(
    "knowledge.embeddings",
    description="Passages by embedding model, and how many are not on the org's current model.",
    scope="knowledge:read",
    input_schema=NO_ARGS,
)
def knowledge_embeddings(db, org, caller):
    return reembed.status(db, int(org.id), embedder.for_org(db, int(org.id)))


@tool(
    "knowledge.reembed",
    description="Embed every passage that is not on the org's current embedding model, from its stored text.",
    scope="knowledge:write",
    confirm=True,
    input_schema=NO_ARGS,
)
def knowledge_reembed(db, org, caller):
    return reembed.queue(db, int(org.id))


@tool(
    "knowledge.runs",
    description="Recent crawl and upload runs, newest first.",
    scope="knowledge:read",
    input_schema={
        "type": "object",
        "properties": {"limit": {"type": "integer", "minimum": 1, "maximum": 500}, "failed": {"type": "boolean"}},
        "additionalProperties": False,
    },
)
def knowledge_runs(db, org, caller, limit: int = 50, failed: bool = False):
    return {"runs": runs.recent(db, int(org.id), limit, failed_only=failed)}
