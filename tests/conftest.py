import sys

import pytest

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
