import sys

import pytest

from pdf_factory import make_pdf
from src.compiler import lint, tracker

RAW = "legalize-es/es-ct/BOE-A-TEST-1.md"
NOTE = "knowledge/laws/es/BOE-A-TEST-1.md"
ID = "BOE-A-TEST-1"

RAW_CONTENT = """---
identifier: BOE-A-TEST-1
title: Test Law
country: es
jurisdiction: es-ct
rank: ley
---

### Artículo 1

Body text.
"""


@pytest.fixture
def repo(tmp_path, monkeypatch):
    (tmp_path / "data").mkdir()
    (tmp_path / "knowledge" / "laws" / "es").mkdir(parents=True)
    raw = tmp_path / RAW
    raw.parent.mkdir(parents=True)
    raw.write_text(RAW_CONTENT)

    data_dir = tmp_path / "data"
    monkeypatch.setattr(tracker, "ROOT", tmp_path)
    monkeypatch.setattr(tracker, "DATA_DIR", data_dir)
    monkeypatch.setattr(tracker, "MANIFEST_PATH", data_dir / "manifest.json")
    monkeypatch.setattr(tracker, "INDEX_PATH", data_dir / "index.json")
    monkeypatch.setattr(tracker, "LOG_PATH", data_dir / "compile.log")

    monkeypatch.setattr(lint, "ROOT", tmp_path)
    monkeypatch.setattr(lint, "KNOWLEDGE_DIR", tmp_path / "knowledge")
    monkeypatch.setattr(lint, "DATA_DIR", data_dir)
    monkeypatch.setattr(lint, "MANIFEST_PATH", data_dir / "manifest.json")
    monkeypatch.setattr(lint, "INDEX_PATH", data_dir / "index.json")

    return tmp_path


def run_tracker(monkeypatch, *args):
    monkeypatch.setattr(sys, "argv", ["tracker", *args])
    tracker.main()


CONTRACT_PAGES = [
    [
        (72, 770, "CONTRATO DE ARRENDAMIENTO"),
        (72, 740, "PRIMERA. Objeto. El arrendador cede al arrendatario"),
        (72, 726, "la vivienda situada en Barcelona."),
        (72, 696, "SEGUNDA. Fianza. El arrendatario entrega una fian-"),
        (72, 682, "za de tres mensualidades de renta."),
        (72, 652, "1. El pago se hará por meses anticipados."),
        (72, 638, "2. La renta se actualizará cada año."),
    ],
    [(72, 770, "TERCERA. Duración: un año.")],
    [],
]


@pytest.fixture
def contract_pdf(tmp_path):
    return make_pdf(tmp_path / "lease.pdf", CONTRACT_PAGES)


class StubIndex:
    def __init__(self, laws=("BOE-A-1994-26003", "BOE-A-2013-3904"), articles=(("BOE-A-1994-26003", "36"),)):
        self.laws, self.articles = set(laws), set(articles)

    def has_law(self, identifier):
        return identifier in self.laws

    def has_article(self, identifier, article):
        return (identifier, article) in self.articles

    def has_articles(self):
        return bool(self.articles)


def make_review():
    return {
        "language": "en",
        "country": "es",
        "contract_type": "residential lease",
        "summary": "One clause conflicts with the law.",
        "findings": [
            {"passage": 3, "quote": "fianza de tres mensualidades", "confidence": "high",
             "issue": "Deposit exceeds the legal maximum", "comment": "Tres meses > un mes. ñ €",
             "citations": [{"identifier": "BOE-A-1994-26003", "article": "36", "title": "Ley 29/1994"}]},
            {"passage": 2, "quote": None, "confidence": "medium",
             "issue": "Unclear object", "comment": "The dwelling is not identified.",
             "citations": [{"identifier": "BOE-A-1994-26003"}]},
            {"passage": 6, "quote": "words that are not in the passage", "confidence": "low",
             "issue": "Short term", "comment": "Check the minimum term.", "citations": []},
        ],
        "omissions": [{"issue": "No energy certificate", "comment": "It must be attached.",
                       "citations": [{"identifier": "BOE-A-2013-3904"}]}],
        "not_covered": ["Pets clause (passage 5): no relevant law in the knowledge base"],
        "unreviewed": [],
    }
