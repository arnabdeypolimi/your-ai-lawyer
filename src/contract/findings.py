"""Validate findings.json and check its citations against the Chroma index."""

import json
from pathlib import Path
from typing import Protocol

import chromadb

from src.query import search

CONFIDENCE_LEVELS = ("high", "medium", "low")


class FindingsError(Exception):
    pass


class CitationIndex(Protocol):
    def has_law(self, identifier: str) -> bool: ...
    def has_article(self, identifier: str, article: str) -> bool: ...
    def has_articles(self) -> bool: ...


class ChromaCitationIndex:
    def __init__(self, chroma_dir: Path | None = None):
        chroma_dir = Path(chroma_dir) if chroma_dir is not None else search.CHROMA_DIR
        if not chroma_dir.exists():
            raise FindingsError("Index not found. Run /index first.")
        client = chromadb.PersistentClient(path=str(chroma_dir))
        self._compiled, self._raw = search._get_collections(client)

    def has_law(self, identifier: str) -> bool:
        for col in (self._compiled, self._raw):
            if col.get(where={"identifier": identifier}, limit=1, include=[])["ids"]:
                return True
        return False

    def has_article(self, identifier: str, article: str) -> bool:
        return bool(self._raw.get(ids=[f"raw:{identifier}:art{article}"], include=[])["ids"])

    def has_articles(self) -> bool:
        return self._raw.count() > 0


def load_review(path: Path) -> dict:
    path = Path(path)
    if not path.exists():
        raise FindingsError(f"No findings.json at {path}")
    try:
        return json.loads(path.read_text())
    except json.JSONDecodeError as exc:
        raise FindingsError(f"{path} is not valid JSON: {exc}")


def format_citation(citation: dict) -> str:
    if citation.get("article"):
        return f"[{citation['identifier']}, Art. {citation['article']}]"
    return f"[{citation['identifier']}]"


def _non_blank(value) -> bool:
    return isinstance(value, str) and bool(value.strip())


def _check_citation(citation, loc: str, index: CitationIndex, problems: list[str]) -> None:
    if not isinstance(citation, dict):
        problems.append(f"{loc}: must be an object")
        return
    ident = citation.get("identifier")
    if not _non_blank(ident):
        problems.append(f"{loc}: identifier must be a non-empty string")
    elif not index.has_law(ident):
        problems.append(f"{loc}: {ident} is not in the index")
    article = citation.get("article")
    if article is not None:
        if not index.has_articles():
            problems.append(
                f"{loc}: {ident} Art. {article} cannot be checked: the raw article index "
                f"is empty. Cite at law level or run /index."
            )
        elif not index.has_article(ident, article):
            problems.append(f"{loc}: {ident} Art. {article} is not in the index")


def _citation_list(item: dict, loc: str, problems: list[str]) -> list:
    citations = item.get("citations", [])
    if not isinstance(citations, list):
        problems.append(f"{loc}: citations must be a list")
        return []
    return citations


def validate(review: dict, passage_ids: set[int], index: CitationIndex) -> list[str]:
    if not isinstance(review, dict):
        return ["top-level: findings.json must be a JSON object"]
    problems = []

    for key in ("language", "contract_type", "summary"):
        if key not in review:
            problems.append(f"top-level: missing key '{key}'")
        elif not _non_blank(review[key]):
            problems.append(f"top-level: {key} must be a non-empty string")
    if "country" not in review:
        problems.append("top-level: missing key 'country'")
    elif review["country"] is not None and not isinstance(review["country"], str):
        problems.append("top-level: country must be a string or null")
    for key in ("findings", "omissions", "not_covered", "unreviewed"):
        if key not in review:
            problems.append(f"top-level: missing key '{key}'")
        elif not isinstance(review[key], list):
            problems.append(f"top-level: {key} must be a list")
        elif key in ("not_covered", "unreviewed") and not all(isinstance(v, str) for v in review[key]):
            problems.append(f"top-level: {key} must be a list of strings")

    findings = review.get("findings")
    if isinstance(findings, list):
        for i, f in enumerate(findings):
            loc = f"findings[{i}]"
            if not isinstance(f, dict):
                problems.append(f"{loc}: must be an object")
                continue
            passage = f.get("passage")
            if isinstance(passage, bool) or not isinstance(passage, int):
                problems.append(f"{loc}: passage must be an integer")
            elif passage not in passage_ids:
                problems.append(f"{loc}: passage {passage} is not in passages.json")
            confidence = f.get("confidence")
            if confidence not in CONFIDENCE_LEVELS:
                problems.append(f"{loc}: confidence must be one of high, medium, low")
            for field in ("issue", "comment"):
                if not _non_blank(f.get(field)):
                    problems.append(f"{loc}: {field} must be a non-empty string")
            if "quote" in f and f["quote"] is not None and not isinstance(f["quote"], str):
                problems.append(f"{loc}: quote must be a string or null")
            citations = _citation_list(f, loc, problems)
            if confidence in ("high", "medium") and not citations:
                problems.append(f"{loc}: needs at least one citation")
            if confidence == "high" and not any(
                isinstance(c, dict) and c.get("article") for c in citations
            ):
                problems.append(f"{loc}: a high finding needs a citation with an article")
            for j, c in enumerate(citations):
                _check_citation(c, f"{loc}.citations[{j}]", index, problems)

    omissions = review.get("omissions")
    if isinstance(omissions, list):
        for i, o in enumerate(omissions):
            loc = f"omissions[{i}]"
            if not isinstance(o, dict):
                problems.append(f"{loc}: must be an object")
                continue
            for field in ("issue", "comment"):
                if not _non_blank(o.get(field)):
                    problems.append(f"{loc}: {field} must be a non-empty string")
            citations = _citation_list(o, loc, problems)
            if not citations:
                problems.append(f"{loc}: needs at least one citation")
            for j, c in enumerate(citations):
                _check_citation(c, f"{loc}.citations[{j}]", index, problems)

    return problems
