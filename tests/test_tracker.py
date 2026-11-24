import hashlib
import json
import shutil

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


def test_mark_missing_rank_exits_with_usage(repo, monkeypatch, capsys):
    with pytest.raises(SystemExit) as exc:
        run_tracker(monkeypatch, "mark", ID, RAW, NOTE, "es-ct")
    assert exc.value.code == 1
    assert "Usage: python -m src.compiler.tracker mark" in capsys.readouterr().out


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


def test_mark_stores_repo_relative_note_when_knowledge_is_symlinked_outside_repo(
    repo, monkeypatch, tmp_path_factory
):
    vault = tmp_path_factory.mktemp("vault")
    (vault / "laws" / "es").mkdir(parents=True)
    shutil.rmtree(repo / "knowledge")
    (repo / "knowledge").symlink_to(vault, target_is_directory=True)
    run_tracker(monkeypatch, "mark", ID, RAW, str(repo / NOTE), "es-ct", "ley")
    entry = _index(repo)[ID]
    assert entry["note_path"] == NOTE
    assert entry["raw_path"] == RAW


def test_mark_stores_lexical_key_when_submodule_is_symlinked_inside_repo(
    repo, monkeypatch
):
    (repo / "vendor").mkdir()
    (repo / "legalize-es").rename(repo / "vendor" / "legalize-es")
    (repo / "legalize-es").symlink_to(
        repo / "vendor" / "legalize-es", target_is_directory=True
    )
    run_tracker(monkeypatch, "mark", ID, str(repo / RAW), NOTE, "es-ct", "ley")
    expected_hash = hashlib.md5(RAW_CONTENT.encode()).hexdigest()
    assert _manifest(repo) == {RAW: expected_hash}


def test_mark_accepts_absolute_paths_through_symlinked_root(
    repo, monkeypatch, tmp_path_factory
):
    link = tmp_path_factory.mktemp("links") / "repo"
    link.symlink_to(repo, target_is_directory=True)
    run_tracker(
        monkeypatch,
        "mark", ID, str(link / RAW), str(link / NOTE), "es-ct", "ley",
    )
    expected_hash = hashlib.md5(RAW_CONTENT.encode()).hexdigest()
    assert _manifest(repo) == {RAW: expected_hash}
    assert _index(repo)[ID]["note_path"] == NOTE


def test_mark_rejects_unquoted_multi_word_rank(repo, monkeypatch):
    with pytest.raises(SystemExit) as exc:
        run_tracker(
            monkeypatch,
            "mark", ID, RAW, NOTE, "es-ct", "real", "decreto", "legislativo",
        )
    assert exc.value.code == 1
    assert not (repo / "data" / "index.json").exists()


def test_mark_stores_quoted_multi_word_rank(repo, monkeypatch):
    run_tracker(
        monkeypatch, "mark", ID, RAW, NOTE, "es-ct", "real decreto legislativo"
    )
    assert _index(repo)[ID]["rank"] == "real decreto legislativo"


def test_error_stores_quoted_multi_word_rank(repo, monkeypatch):
    run_tracker(
        monkeypatch, "error", ID, RAW, "es-ct", "real decreto", "could not read"
    )
    entry = _index(repo)[ID]
    assert entry["rank"] == "real decreto"
    assert entry["error"] == "could not read"


def test_log_run_appends_to_existing_log(repo, monkeypatch):
    run_tracker(monkeypatch, "log-run", "es-ct", "--compiled", "3")
    run_tracker(monkeypatch, "log-run", "es", "--compiled", "1")
    lines = _log_lines(repo)
    assert len(lines) == 2
    first = json.loads(lines[0])
    second = json.loads(lines[1])
    assert first["jurisdiction"] == "es-ct"
    assert first["compiled"] == 3
    assert second["jurisdiction"] == "es"
    assert second["compiled"] == 1


def test_error_stores_repo_relative_path_for_absolute_input(repo, monkeypatch):
    run_tracker(monkeypatch, "error", ID, str(repo / RAW), "es-ct", "ley", "boom")
    assert _index(repo)[ID]["raw_path"] == RAW
