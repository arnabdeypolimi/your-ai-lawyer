"""Parse raw law markdown files from legalize-* submodules."""

import re
from dataclasses import dataclass, field
from pathlib import Path

import frontmatter


@dataclass
class Article:
    number: str
    title: str
    text: str


@dataclass
class LawDocument:
    identifier: str
    title: str
    country: str
    rank: str
    publication_date: str
    last_updated: str
    status: str
    source: str
    department: str
    jurisdiction: str  # e.g. "es" or "es-ct"
    scope: str
    raw_path: Path
    body: str
    articles: list[Article] = field(default_factory=list)


_ARTICLE_RE = re.compile(
    r"#{3,6}\s+Art[ií]culo\s+(\d+[a-zA-Z]?(?:\s+bis)?)\s*\n(.*?)(?=#{3,6}\s+Art[ií]culo\s+\d|$)",
    re.DOTALL | re.IGNORECASE,
)


def parse_law(path: Path) -> LawDocument:
    post = frontmatter.load(str(path))
    meta = post.metadata
    body = post.content

    # Derive jurisdiction: prefer explicit field, else infer from path parent dir name
    jurisdiction = meta.get("jurisdiction") or meta.get("country", "")
    parent = path.parent.name
    if parent and parent != path.parent.parent.name:
        jurisdiction = parent  # e.g. "es-ct"

    doc = LawDocument(
        identifier=meta.get("identifier", path.stem),
        title=meta.get("title", ""),
        country=meta.get("country", ""),
        rank=meta.get("rank", ""),
        publication_date=str(meta.get("publication_date", "")),
        last_updated=str(meta.get("last_updated", "")),
        status=meta.get("status", ""),
        source=meta.get("source", ""),
        department=meta.get("department", ""),
        jurisdiction=jurisdiction,
        scope=meta.get("scope", ""),
        raw_path=path,
        body=body,
    )

    doc.articles = _extract_articles(body)
    return doc


def _extract_articles(body: str) -> list[Article]:
    articles = []
    for m in _ARTICLE_RE.finditer(body):
        number = m.group(1).strip()
        raw = m.group(2).strip()
        # First line of the match may be a title before the content
        lines = raw.splitlines()
        title = ""
        if lines and not lines[0].startswith(("1.", "2.", "3.", "a)", "b)")):
            # heuristic: short first line with no period = title
            if len(lines[0]) < 120 and not lines[0].endswith("."):
                title = lines[0].strip()
                raw = "\n".join(lines[1:]).strip()
        articles.append(Article(number=number, title=title, text=raw))
    return articles


def iter_laws(submodule_dir: Path, country: str | None = None) -> list[Path]:
    """Return all .md law files under submodule_dir, optionally filtered by country dir."""
    root = Path(submodule_dir)
    if country:
        dirs = [root / country]
        # also include regional dirs like es-ct, es-md
        dirs += sorted(root.glob(f"{country}-*"))
    else:
        dirs = [d for d in root.iterdir() if d.is_dir() and not d.name.startswith(".")]

    paths = []
    for d in dirs:
        if d.exists():
            paths.extend(sorted(d.glob("*.md")))
    return paths
