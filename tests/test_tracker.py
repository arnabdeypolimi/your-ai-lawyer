import hashlib
import json

import pytest

from src.compiler import tracker

from conftest import ID, NOTE, RAW, RAW_CONTENT, run_tracker


def _index(repo):
    return json.loads((repo / "data" / "index.json").read_text())


def _manifest(repo):
    return json.loads((repo / "data" / "manifest.json").read_text())


def _log_lines(repo):
    log = repo / "data" / "compile.log"
    return log.read_text().strip().splitlines()


def test_error_records_arguments_in_the_right_fields(repo, monkeypatch):
    run_tracker(monkeypatch, "error", ID, RAW, "es-ct", "ley", "read", "failed", "badly")
    entry = _index(repo)[ID]
    assert entry["status"] == "error"
    assert entry["raw_path"] == RAW
    assert entry["jurisdiction"] == "es-ct"
    assert entry["rank"] == "ley"
    assert entry["error"] == "read failed badly"
    assert entry["note_path"] is None


def test_error_accepts_message_as_single_argument(repo, monkeypatch):
    run_tracker(monkeypatch, "error", ID, RAW, "es-ct", "ley", "read failed badly")
    assert _index(repo)[ID]["error"] == "read failed badly"


def test_error_without_message_records_unknown_error(repo, monkeypatch):
    run_tracker(monkeypatch, "error", ID, RAW, "es-ct", "ley")
    assert _index(repo)[ID]["error"] == "unknown error"


def test_mark_accepts_repo_relative_paths(repo, monkeypatch):
    run_tracker(monkeypatch, "mark", ID, RAW, NOTE, "es-ct", "ley")
    expected_hash = hashlib.md5(RAW_CONTENT.encode()).hexdigest()
    assert _manifest(repo) == {RAW: expected_hash}
    entry = _index(repo)[ID]
    assert entry["status"] == "compiled"
    assert entry["raw_path"] == RAW
    assert entry["note_path"] == NOTE
    assert entry["jurisdiction"] == "es-ct"
    assert entry["rank"] == "ley"


def test_mark_accepts_absolute_paths(repo, monkeypatch):
    run_tracker(
        monkeypatch, "mark", ID, str(repo / RAW), str(repo / NOTE), "es-ct", "ley"
    )
    expected_hash = hashlib.md5(RAW_CONTENT.encode()).hexdigest()
    assert _manifest(repo) == {RAW: expected_hash}
    entry = _index(repo)[ID]
    assert entry["raw_path"] == RAW
    assert entry["note_path"] == NOTE


def test_mark_missing_rank_exits_with_usage(repo, monkeypatch):
    with pytest.raises(SystemExit) as exc:
        run_tracker(monkeypatch, "mark", ID, RAW, NOTE, "es-ct")
    assert exc.value.code == 1


def test_log_run_appends_run_with_errors(repo, monkeypatch):
    run_tracker(
        monkeypatch,
        "log-run", "es-ct", "--compiled", "3",
        "--error-ids", "BOE-A-X", "BOE-A-Y",
    )
    lines = _log_lines(repo)
    assert len(lines) == 1
    entry = json.loads(lines[0])
    assert entry["jurisdiction"] == "es-ct"
    assert entry["compiled"] == 3
    assert entry["skipped"] == 0
    assert entry["errors"] == 2
    assert entry["error_identifiers"] == ["BOE-A-X", "BOE-A-Y"]


def test_log_run_without_errors(repo, monkeypatch):
    run_tracker(monkeypatch, "log-run", "es-ct", "--compiled", "2", "--skipped", "1")
    entry = json.loads(_log_lines(repo)[0])
    assert entry["compiled"] == 2
    assert entry["skipped"] == 1
    assert entry["errors"] == 0
    assert entry["error_identifiers"] == []
