"""HTML to text, text to chunks, and the named extractors of crawled sources.

A module registers an extractor under a name and sets that name on its sources. Extractors are
registered when the module is imported; modules/manifest.py lists every job module, so a worker
has them before any crawl runs.
"""

import re
from collections.abc import Callable

from bs4 import BeautifulSoup

from modules.knowledge.fetch import Fetched

_DROP_TAGS = ("script", "style", "noscript", "svg", "nav", "footer", "header", "form", "iframe")
_BLOCK_TAGS = ("p", "li", "h1", "h2", "h3", "h4", "h5", "h6", "tr", "br", "div", "section", "article")
_WS = re.compile(r"[ \t\r\f\v]+")
_BLANKS = re.compile(r"\n{3,}")

EXTRACTORS: dict[str, Callable[[Fetched], str]] = {}


def register(name: str, func: Callable[[Fetched], str]) -> None:
    EXTRACTORS[name] = func


def extractor(name: str | None) -> Callable[[Fetched], str] | None:
    """The extractor registered under name, or None."""
    return EXTRACTORS.get(name) if name else None


def extract_text(html: bytes | str, *, main_only: bool = True, keep_forms: bool = False) -> str:
    """Visible text, one block per line, with navigation and boilerplate removed.

    keep_forms keeps form elements, for pages that render their results inside a form.
    """
    soup = BeautifulSoup(html, "lxml")
    dropped = tuple(t for t in _DROP_TAGS if not (keep_forms and t == "form"))
    for tag in soup(dropped):
        tag.decompose()
    root = soup
    if main_only:
        main = soup.find("main") or soup.select_one('[role="main"]') or soup.find("article")
        if main is not None:
            root = main
    for tag in root.find_all(_BLOCK_TAGS):
        tag.insert_before("\n")
        tag.insert_after("\n")
    lines = [_WS.sub(" ", line).strip() for line in root.get_text(" ").split("\n")]
    return _BLANKS.sub("\n\n", "\n".join(line for line in lines if line)).strip()


def title_of(html: bytes | str) -> str | None:
    """The page title, else the first h1, else None."""
    soup = BeautifulSoup(html, "lxml")
    if soup.title and soup.title.string:
        return soup.title.string.strip()
    h1 = soup.find("h1")
    return h1.get_text(" ", strip=True) if h1 else None


def chunk_text(text: str, *, max_chars: int = 1200, overlap_chars: int = 200) -> list[str]:
    """Packs paragraphs into chunks up to max_chars, split at sentence or clause breaks."""
    if max_chars <= 0:
        raise ValueError("max_chars must be positive")
    overlap_chars = max(0, min(overlap_chars, max_chars // 2))
    pieces: list[str] = []
    for paragraph in (p.strip() for p in text.split("\n")):
        if paragraph:
            pieces.extend(_split_long(paragraph, max_chars))

    chunks: list[str] = []
    current = ""
    for piece in pieces:
        candidate = piece if not current else f"{current}\n{piece}"
        if len(candidate) <= max_chars:
            current = candidate
            continue
        if current:
            chunks.append(current)
            tail = _tail(current, overlap_chars)
            current = f"{tail}\n{piece}".strip() if tail else piece
            if len(current) > max_chars:
                chunks.append(current[:max_chars])
                current = current[max_chars - overlap_chars :] if overlap_chars else ""
        else:
            current = piece
    if current:
        chunks.append(current)
    return chunks


def _split_long(paragraph: str, max_chars: int) -> list[str]:
    if len(paragraph) <= max_chars:
        return [paragraph]
    out: list[str] = []
    start = 0
    while start < len(paragraph):
        end = min(start + max_chars, len(paragraph))
        if end < len(paragraph):
            cut = max(
                paragraph.rfind(". ", start, end),
                paragraph.rfind("; ", start, end),
                paragraph.rfind(", ", start, end),
            )
            if cut > start + max_chars // 2:
                end = cut + 1
        out.append(paragraph[start:end].strip())
        start = end
    return [o for o in out if o]


def _tail(chunk: str, overlap_chars: int) -> str:
    """The newest whole lines of chunk that fit in overlap_chars."""
    if overlap_chars <= 0:
        return ""
    kept: list[str] = []
    total = 0
    for line in reversed(chunk.split("\n")):
        total += len(line) + (1 if kept else 0)
        if total > overlap_chars:
            break
        kept.append(line)
    return "\n".join(reversed(kept))
