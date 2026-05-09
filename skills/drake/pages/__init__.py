from __future__ import annotations

import re
from pathlib import Path

from skills.drake.models import PageSpec


PAGES_DIR = Path(__file__).resolve().parent


def load_pages() -> list[PageSpec]:
    """Load Drake input pages from one markdown file per page key."""

    pages = [_load_page(path) for path in sorted(PAGES_DIR.glob("*.md"))]
    return pages


def find_pages(query: str) -> list[PageSpec]:
    normalized_query = _normalize(query)
    pages = load_pages()
    exact = [page for page in pages if _normalize(page.key) == normalized_query]
    if exact:
        return _expand_related(exact, pages)

    matches = [
        page
        for page in pages
        if normalized_query in _normalize(page.key)
        or normalized_query in _normalize(page.title)
        or normalized_query in _normalize(page.instructions)
    ]
    return _expand_related(matches, pages)


def get_page(page_key: str) -> PageSpec:
    matches = find_pages(page_key)
    for page in matches:
        if _normalize(page.key) == _normalize(page_key):
            return page
    if len(matches) == 1:
        return matches[0]
    available = ", ".join(page.key for page in load_pages())
    raise ValueError(f"Unknown Drake input page {page_key!r}. Available pages: {available}")


def render_search_results(query: str) -> str:
    matches = find_pages(query)
    if not matches:
        return f"No Drake input pages matched {query!r}."

    return "\n\n".join(f"## {page.key}\n\n{page.instructions.strip()}" for page in matches)


def _load_page(path: Path) -> PageSpec:
    text = path.read_text(encoding="utf-8")
    metadata, instructions = _split_frontmatter(text, path)
    key = path.stem
    title = metadata.get("title", key)
    columns = tuple(_parse_list(metadata.get("columns", ""), "columns", path))
    if not columns:
        raise ValueError(f"{path}: columns metadata is required.")
    related = tuple(_parse_list(metadata.get("related", ""), "related", path))
    return PageSpec(
        key=key,
        title=title,
        source_path=str(path),
        instructions=instructions.strip(),
        columns=columns,
        row_advance=metadata.get("row_advance", "Tab"),
        related=related,
    )


def _split_frontmatter(text: str, path: Path) -> tuple[dict[str, str], str]:
    if not text.startswith("---\n"):
        raise ValueError(f"{path}: markdown page must start with frontmatter.")
    end = text.find("\n---\n", 4)
    if end == -1:
        raise ValueError(f"{path}: markdown page frontmatter is not closed.")
    raw_metadata = text[4:end]
    body = text[end + 5 :]
    metadata: dict[str, str] = {}
    for line in raw_metadata.splitlines():
        if not line.strip():
            continue
        key, separator, value = line.partition(":")
        if not separator:
            raise ValueError(f"{path}: invalid frontmatter line: {line}")
        metadata[key.strip()] = value.strip()
    return metadata, body


def _parse_list(value: str, field_name: str, path: Path) -> list[str]:
    if not value:
        return []
    if not (value.startswith("[") and value.endswith("]")):
        raise ValueError(f"{path}: {field_name} must be a bracketed list.")
    return re.findall(r'"([^"]*)"', value)


def _expand_related(matches: list[PageSpec], pages: list[PageSpec]) -> list[PageSpec]:
    by_key = {page.key: page for page in pages}
    ordered: list[PageSpec] = []
    for page in matches:
        _append_unique(ordered, page)
        for related in page.related:
            if related in by_key:
                _append_unique(ordered, by_key[related])
    return ordered


def _append_unique(pages: list[PageSpec], page: PageSpec) -> None:
    if all(existing.key != page.key for existing in pages):
        pages.append(page)


def _normalize(value: str) -> str:
    return re.sub(r"\s+", " ", value).strip().casefold()

