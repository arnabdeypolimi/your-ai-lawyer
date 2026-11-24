from src.compiler import lint, tracker

from conftest import ID, NOTE, RAW, RAW_CONTENT, run_tracker


def test_never_compiled_excludes_files_in_manifest(repo, monkeypatch):
    run_tracker(monkeypatch, "mark", ID, RAW, NOTE, "es-ct", "ley")
    assert lint.check_never_compiled(tracker.load_manifest(), None) == []


def test_never_compiled_reports_untracked_files(repo, monkeypatch):
    second = repo / "legalize-es/es-ct/BOE-A-TEST-2.md"
    second.write_text(RAW_CONTENT)
    run_tracker(monkeypatch, "mark", ID, RAW, NOTE, "es-ct", "ley")
    assert lint.check_never_compiled(tracker.load_manifest(), None) == [second]
