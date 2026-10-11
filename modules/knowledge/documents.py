"""Uploaded documents: text, Markdown, HTML, PDF and Word files indexed as sources. No Flask here.

Each file becomes one source under the key <folder>/<file name>. Uploading a file with the same name
again replaces its passages. Uploaded sources are not crawled; delete them like any other source.
"""

import hashlib
import io
import re
import zipfile
from dataclasses import dataclass

from defusedxml import ElementTree
from pypdf import PdfReader
from pypdf.errors import PdfReadError

from core import limits
from core.time import utcnow
from modules.knowledge import extract, runs, settings
from modules.knowledge.crawl import index_text
from modules.knowledge.embedder import Embedder
from modules.knowledge.models import KnowledgeChunk, KnowledgeSource, KnowledgeVersion
from modules.knowledge.service import KEY_PATTERN, UPLOADS_LIMIT, KnowledgeError, _text, can_publish, new_source

MAX_FILES = 20
MAX_FILE_BYTES = 10_000_000
MAX_TOTAL_BYTES = 25_000_000
MAX_PDF_PAGES = 500
MAX_DOCX_XML_BYTES = 50_000_000
FOLDER_PATTERN = re.compile(r"^[a-z0-9][a-z0-9_-]{0,40}$")
EXTENSIONS = (".txt", ".md", ".markdown", ".csv", ".html", ".htm", ".pdf", ".docx")
_WORD = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"


@dataclass(frozen=True)
class Upload:
    """One file from the request: its name and bytes."""

    name: str
    data: bytes


def _key_name(filename: str) -> str:
    """The file name as the last part of a source key: lower case, unsafe characters as -."""
    base = filename.replace("\\", "/").rsplit("/", 1)[-1].lower()
    return re.sub(r"[^a-z0-9._-]+", "-", base).strip("-.")[:200] or "document"


def _pdf_text(data: bytes) -> str:
    try:
        reader = PdfReader(io.BytesIO(data))
        if reader.is_encrypted:
            raise KnowledgeError("The PDF is encrypted")
        pages = reader.pages
        if len(pages) > MAX_PDF_PAGES:
            raise KnowledgeError(f"The PDF has more than {MAX_PDF_PAGES} pages")
        return "\n\n".join(page.extract_text() or "" for page in pages)
    except (PdfReadError, ValueError, KeyError, TypeError) as e:
        raise KnowledgeError("The PDF could not be read") from e


def _docx_text(data: bytes) -> str:
    try:
        with zipfile.ZipFile(io.BytesIO(data)) as archive:
            info = archive.getinfo("word/document.xml")
            if info.file_size > MAX_DOCX_XML_BYTES:
                raise KnowledgeError("The Word file is too large")
            root = ElementTree.fromstring(archive.read(info))
    except (zipfile.BadZipFile, KeyError, ElementTree.ParseError) as e:
        raise KnowledgeError("The Word file could not be read") from e
    paragraphs = ("".join(node.text or "" for node in p.iter(f"{_WORD}t")) for p in root.iter(f"{_WORD}p"))
    return "\n".join(line for line in paragraphs if line.strip())


def text_of(upload: Upload) -> tuple[str, str | None]:
    """The text of a file and its title, if the file has one. Raises KnowledgeError for a file it cannot read."""
    name = upload.name.lower()
    if name.endswith(".pdf"):
        return _pdf_text(upload.data), None
    if name.endswith(".docx"):
        return _docx_text(upload.data), None
    if name.endswith((".html", ".htm")):
        return extract.extract_text(upload.data, main_only=False), extract.title_of(upload.data)
    if name.endswith(EXTENSIONS):
        return upload.data.decode("utf-8", errors="replace"), None
    raise KnowledgeError(f"Send one of these file types: {', '.join(EXTENSIONS)}", 415)


def check(uploads: list[Upload]) -> None:
    """Refuse an upload with no files, too many files, or files that are too large."""
    if not uploads:
        raise KnowledgeError("Send one or more files")
    if len(uploads) > MAX_FILES:
        raise KnowledgeError(f"Send at most {MAX_FILES} files at a time")
    if sum(len(u.data) for u in uploads) > MAX_TOTAL_BYTES:
        raise KnowledgeError(f"The files together must be at most {MAX_TOTAL_BYTES // 1_000_000} MB", 413)


def upload(
    db,
    org_id: int,
    org_prefix: str,
    uploads: list[Upload],
    data: dict,
    embedder: Embedder | None,
) -> dict:
    """Index each file as a source. A file that fails does not stop the others. Commits after each file.

    The files count against the org's knowledge.uploads_per_day limit, also the ones that fail.
    """
    check(uploads)
    limits.consume(db, org_id, UPLOADS_LIMIT, len(uploads))
    db.commit()
    category = _text(data.get("category") or "documents", "category", 100) or "documents"
    folder = data.get("folder") or "upload"
    if not isinstance(folder, str) or not FOLDER_PATTERN.match(folder):
        raise KnowledgeError(
            "folder must be 1 to 41 lower case letters, digits, _ or - and start with a letter or digit"
        )
    public = data.get("public") is True
    if public and not can_publish(db, org_prefix):
        raise KnowledgeError("This organization may not write public sources", 403)

    results = []
    for item in uploads:
        key = f"{folder}/{_key_name(item.name)}"
        results.append(_index_one(db, org_id, key, item, category, public, embedder))
    return {
        "files": results,
        "indexed": sum(1 for r in results if r["changed"]),
        "unchanged": sum(1 for r in results if not r["changed"] and not r["error"]),
        "failed": sum(1 for r in results if r["error"]),
    }


def _index_one(db, org_id: int, key: str, item: Upload, category: str, public: bool, embedder: Embedder | None) -> dict:
    started = runs.Timer()
    result = {"file": item.name, "key": key, "changed": False, "chunks": 0, "error": None}
    error = _refusal(db, org_id, key, item)
    outcome: dict = {}
    if error is None:
        try:
            outcome = _index(db, org_id, key, item, category, public, embedder)
        except (KnowledgeError, limits.LimitError) as e:
            db.rollback()
            error = e.message
    if error is not None:
        runs.record(db, org_id, key, "upload", started, error=error)
        db.commit()
        return result | {"error": error}
    runs.record(db, org_id, key, "upload", started, changed=outcome["changed"], chunks=outcome["chunks"])
    db.commit()
    return result | {"changed": outcome["changed"], "chunks": outcome["chunks"]}


def _refusal(db, org_id: int, key: str, item: Upload) -> str | None:
    """Why the file cannot be indexed under key, or None."""
    if not KEY_PATTERN.match(key):
        return "The file name makes no valid key"
    if len(item.data) > MAX_FILE_BYTES:
        return f"The file is larger than {MAX_FILE_BYTES // 1_000_000} MB"
    crawled = (
        db.query(KnowledgeSource.id)
        .filter(KnowledgeSource.organization_id == org_id, KnowledgeSource.key == key)
        .filter(KnowledgeSource.fetch_every_hours.isnot(None))
        .first()
    )
    if crawled is not None:
        return "A crawled source has this key. Rename the file or delete that source"
    return None


def _index(db, org_id: int, key: str, item: Upload, category: str, public: bool, embedder: Embedder | None) -> dict:
    """Index the file as the source key. The content hash covers the bytes and the chunk settings."""
    tuning = settings.for_org(db, org_id)
    digest = hashlib.sha256(item.data)
    digest.update(f"\0{tuning['chunk_chars']}:{tuning['chunk_overlap']}".encode())
    content_hash = digest.hexdigest()

    source = db.query(KnowledgeSource).filter_by(organization_id=org_id, key=key).first()
    if source is None:
        source = new_source(db, org_id, key=key, category=category, public=public)
    source.category, source.public, source.updated_at = category, public, utcnow()
    current = db.query(KnowledgeVersion).filter_by(id=source.current_version_id).first()
    if current is not None and current.content_hash == content_hash:
        db.query(KnowledgeChunk).filter_by(version_id=current.id).update(
            {"category": category, "public": public}, synchronize_session=False
        )
        return {"changed": False, "chunks": int(current.chunk_count or 0)}
    text, title = text_of(item)
    if not text.strip() and item.name.lower().endswith(".pdf"):
        raise KnowledgeError("The PDF has no text layer. A scanned PDF needs text recognition first")
    return index_text(db, source, text, title or item.name, content_hash, embedder, force=True)
