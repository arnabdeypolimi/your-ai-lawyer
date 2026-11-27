"""Tests for src/contract/findings.py."""

import chromadb
import pytest

from conftest import StubIndex, make_review
from src.query import search
from src.contract.findings import (
    ChromaCitationIndex, FindingsError, format_citation, load_review, validate,
)

IDS = {1, 2, 3, 4, 5, 6}


def test_valid_review_has_no_problems():
    assert validate(make_review(), IDS, StubIndex()) == []


@pytest.mark.parametrize("mutate, fragments", [
    (lambda r: r.pop("summary"), ["top-level", "summary"]),
    (lambda r: r.update(summary="  "), ["top-level", "summary"]),
    (lambda r: r.update(findings={}), ["top-level", "findings", "list"]),
    (lambda r: r.update(unreviewed=None), ["top-level", "unreviewed", "list"]),
    (lambda r: r.update(not_covered=[1]), ["top-level", "not_covered"]),
    (lambda r: r["findings"][0].update(passage=99), ["findings[0]", "passage 99"]),
    (lambda r: r["findings"][0].update(passage="3"), ["findings[0]", "passage", "integer"]),
    (lambda r: r["findings"][1].update(confidence="certain"), ["findings[1]", "high, medium, low"]),
    (lambda r: r["findings"][0].update(issue=""), ["findings[0]", "issue"]),
    (lambda r: r["findings"][0].update(comment=None), ["findings[0]", "comment"]),
    (lambda r: r["findings"][0].update(quote=5), ["findings[0]", "quote"]),
    (lambda r: r["findings"][1].update(citations=[]), ["findings[1]", "at least one citation"]),
    (lambda r: r["findings"][0]["citations"][0].pop("article"), ["findings[0]", "high", "article"]),
    (lambda r: r["findings"][1]["citations"][0].update(identifier="BOE-X"), ["findings[1].citations[0]", "BOE-X", "not in the index"]),
    (lambda r: r["findings"][0]["citations"][0].update(article="99"), ["findings[0].citations[0]", "Art. 99", "not in the index"]),
    (lambda r: r["omissions"][0].update(citations=[]), ["omissions[0]", "at least one citation"]),
    (lambda r: r["omissions"][0].update(issue=""), ["omissions[0]", "issue"]),
])
def test_validate_reports_each_rule(mutate, fragments):
    review = make_review()
    mutate(review)
    problems = validate(review, IDS, StubIndex())
    assert any(all(f in p for f in fragments) for p in problems), problems


def test_validate_reports_all_problems_at_once():
    review = make_review()
    review["findings"][0]["passage"] = 99
    review["findings"][1]["confidence"] = "certain"
    review["omissions"][0]["citations"] = []
    assert len(validate(review, IDS, StubIndex())) == 3


def test_validate_reports_wrong_types():
    assert validate([], IDS, StubIndex()) == ["top-level: findings.json must be a JSON object"]
    review = make_review()
    review["findings"] = ["oops"]
    assert any("findings[0]" in p and "object" in p for p in validate(review, IDS, StubIndex()))


def test_article_citation_with_empty_article_index_explains_itself():
    problems = validate(make_review(), IDS, StubIndex(articles=()))
    assert any("raw article index is empty" in p and "/index" in p for p in problems)


def test_low_finding_needs_no_citation_and_missing_quote_is_fine():
    review = make_review()
    del review["findings"][2]["quote"]
    assert validate(review, IDS, StubIndex()) == []


def test_format_citation():
    assert format_citation({"identifier": "BOE-A-1994-26003", "article": "36"}) == "[BOE-A-1994-26003, Art. 36]"
    assert format_citation({"identifier": "BOE-A-1994-26003", "article": None}) == "[BOE-A-1994-26003]"
    assert format_citation({"identifier": "BOE-A-1994-26003"}) == "[BOE-A-1994-26003]"


def test_load_review_rejects_bad_json(tmp_path):
    with pytest.raises(FindingsError, match="No findings.json"):
        load_review(tmp_path / "findings.json")
    (tmp_path / "findings.json").write_text("{not json")
    with pytest.raises(FindingsError, match="not valid JSON"):
        load_review(tmp_path / "findings.json")


def test_chroma_citation_index(tmp_path):
    client = chromadb.PersistentClient(path=str(tmp_path / "chroma"))
    compiled = client.get_or_create_collection("compiled", metadata={"hnsw:space": "cosine"})
    raw = client.get_or_create_collection("raw_chunks", metadata={"hnsw:space": "cosine"})
    compiled.add(ids=["compiled:BOE-A-1"], embeddings=[[0.1, 0.2, 0.3]], documents=["x"], metadatas=[{"identifier": "BOE-A-1"}])
    index = ChromaCitationIndex(tmp_path / "chroma")
    assert index.has_law("BOE-A-1") and not index.has_law("BOE-A-2")
    assert not index.has_articles()
    raw.add(ids=["raw:BOE-A-2:art9 bis"], embeddings=[[0.1, 0.2, 0.3]], documents=["x"], metadatas=[{"identifier": "BOE-A-2"}])
    index = ChromaCitationIndex(tmp_path / "chroma")
    assert index.has_law("BOE-A-2") and index.has_articles()
    assert index.has_article("BOE-A-2", "9 bis") and not index.has_article("BOE-A-2", "9")


def test_chroma_citation_index_without_an_index(tmp_path):
    with pytest.raises(FindingsError, match="Index not found. Run /index first."):
        ChromaCitationIndex(tmp_path / "nope")


def test_citation_without_identifier_reports_one_problem():
    review = make_review()
    review["findings"][1]["citations"] = [{"identifier": "", "article": "5"}]
    problems = validate(review, IDS, StubIndex())
    assert problems == ["findings[1].citations[0]: identifier must be a non-empty string"]


def test_chroma_citation_index_finds_articles_written_as_plain_lines(tmp_path, monkeypatch):
    law = tmp_path / "legalize-es" / "es-ct" / "BOE-A-3.md"
    law.parent.mkdir(parents=True)
    law.write_text(
        "# Ley\n\nArtículo 1.\n\nUno, según el\nartículo 7 de otra ley.\n\nArtículo 15 bis.\n\nQuince bis.\n\n"
        "##### Artículo 20.\n\nVeinte.\n\nArtículo 3.º\n\nTres.\n\n**Artículo 4.**\n\nCuatro.\n"
    )
    monkeypatch.setattr(search, "ROOT", tmp_path)
    client = chromadb.PersistentClient(path=str(tmp_path / "chroma"))
    raw = client.get_or_create_collection("raw_chunks", metadata={"hnsw:space": "cosine"})
    raw.add(ids=["raw:BOE-A-3:chunk0"], embeddings=[[0.1, 0.2, 0.3]], documents=["x"],
            metadatas=[{"identifier": "BOE-A-3", "source_path": "legalize-es/es-ct/BOE-A-3.md"}])
    raw.add(ids=["raw:BOE-A-4:chunk0"], embeddings=[[0.1, 0.2, 0.3]], documents=["x"],
            metadatas=[{"identifier": "BOE-A-4", "source_path": "legalize-es/es-ct/missing.md"}])
    index = ChromaCitationIndex(tmp_path / "chroma")
    for article in ("1", "15 bis", "15", "20", "3", "4"):
        assert index.has_article("BOE-A-3", article), article
    for article in ("2", "5", "7", "150"):
        assert not index.has_article("BOE-A-3", article), article
    assert not index.has_article("BOE-A-4", "1")       # source file missing
    assert not index.has_article("BOE-A-9", "1")       # law not indexed
