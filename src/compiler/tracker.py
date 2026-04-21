"""Compilation index and log management."""

import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).parents[2]
DATA_DIR = ROOT / "data"
MANIFEST_PATH = DATA_DIR / "manifest.json"
INDEX_PATH = DATA_DIR / "index.json"
LOG_PATH = DATA_DIR / "compile.log"


# ── helpers ────────────────────────────────────────────────────────────────

def _file_hash(path: Path) -> str:
    return hashlib.md5(path.read_bytes()).hexdigest()


def _now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


# ── manifest (hash-based change detection) ─────────────────────────────────

def load_manifest() -> dict:
    if MANIFEST_PATH.exists():
        return json.loads(MANIFEST_PATH.read_text())
    return {}


def save_manifest(manifest: dict) -> None:
    MANIFEST_PATH.write_text(json.dumps(manifest, indent=2))


def is_changed(path: Path, manifest: dict) -> bool:
    key = str(path.relative_to(ROOT)) if path.is_absolute() else str(path)
    return manifest.get(key) != _file_hash(path)


# ── index (per-law compilation status) ─────────────────────────────────────

def load_index() -> dict:
    """Return index keyed by identifier."""
    if INDEX_PATH.exists():
        return json.loads(INDEX_PATH.read_text())
    return {}


def save_index(index: dict) -> None:
    INDEX_PATH.write_text(json.dumps(index, indent=2, ensure_ascii=False))


def mark_compiled(
    raw_path: Path,
    identifier: str,
    jurisdiction: str,
    rank: str,
    note_path: Path,
    manifest: dict,
    index: dict,
) -> None:
    """Record a successful compilation in both manifest and index."""
    manifest[str(raw_path.relative_to(ROOT))] = _file_hash(raw_path)
    index[identifier] = {
        "identifier": identifier,
        "jurisdiction": jurisdiction,
        "rank": rank,
        "status": "compiled",
        "compiled_at": _now(),
        "raw_path": str(raw_path.relative_to(ROOT)),
        "note_path": str(note_path.relative_to(ROOT)),
        "error": None,
    }


def mark_error(
    raw_path: Path,
    identifier: str,
    jurisdiction: str,
    rank: str,
    error: str,
    index: dict,
) -> None:
    index[identifier] = {
        "identifier": identifier,
        "jurisdiction": jurisdiction,
        "rank": rank,
        "status": "error",
        "compiled_at": _now(),
        "raw_path": str(raw_path.relative_to(ROOT)),
        "note_path": None,
        "error": error,
    }


# ── log (per-run history) ───────────────────────────────────────────────────

def log_run(
    jurisdiction: str,
    compiled: int,
    skipped: int,
    errors: int,
    error_identifiers: list[str],
) -> None:
    entry = {
        "timestamp": _now(),
        "jurisdiction": jurisdiction,
        "compiled": compiled,
        "skipped": skipped,
        "errors": errors,
        "error_identifiers": error_identifiers,
    }
    LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
    with LOG_PATH.open("a", encoding="utf-8") as f:
        f.write(json.dumps(entry, ensure_ascii=False) + "\n")


# ── CLI: mark files compiled from Claude Code ───────────────────────────────

def _cli_mark() -> None:
    """
    Usage: python -m src.compiler.tracker mark <identifier> <raw_path> <note_path>
                                                <jurisdiction> <rank>
    Called by the /compile slash command after Claude writes each note.
    """
    if len(sys.argv) < 6:
        print(
            "Usage: python -m src.compiler.tracker mark "
            "<identifier> <raw_path> <note_path> <jurisdiction> <rank>",
        )
        sys.exit(1)

    _, _, identifier, raw_path_str, note_path_str, jurisdiction, rank = sys.argv[:7]
    raw_path = Path(raw_path_str)
    note_path = Path(note_path_str)

    manifest = load_manifest()
    index = load_index()
    mark_compiled(raw_path, identifier, jurisdiction, rank, note_path, manifest, index)
    save_manifest(manifest)
    save_index(index)
    print(f"Tracked: {identifier} → {note_path_str}")


def _cli_error() -> None:
    """
    Usage: python -m src.compiler.tracker error <identifier> <raw_path>
                                                 <jurisdiction> <rank> <error_msg>
    """
    if len(sys.argv) < 6:
        print(
            "Usage: python -m src.compiler.tracker error "
            "<identifier> <raw_path> <jurisdiction> <rank> <error_msg>",
        )
        sys.exit(1)

    _, _, identifier, raw_path_str, jurisdiction, rank = sys.argv[1:7]
    error_msg = " ".join(sys.argv[7:]) if len(sys.argv) > 7 else "unknown error"
    raw_path = Path(raw_path_str)

    index = load_index()
    mark_error(raw_path, identifier, jurisdiction, rank, error_msg, index)
    save_index(index)
    print(f"Error logged: {identifier} — {error_msg}")


def _cli_status() -> None:
    """
    Usage: python -m src.compiler.tracker status [--jurisdiction es-ct]
    Print a summary of the compilation index.
    """
    import argparse
    p = argparse.ArgumentParser()
    p.add_argument("--jurisdiction", help="Filter by jurisdiction")
    p.add_argument("--status", choices=["compiled", "error", "all"], default="all")
    args = p.parse_args(sys.argv[2:])

    index = load_index()
    rows = list(index.values())
    if args.jurisdiction:
        rows = [r for r in rows if r["jurisdiction"].startswith(args.jurisdiction)]
    if args.status != "all":
        rows = [r for r in rows if r["status"] == args.status]

    compiled = sum(1 for r in rows if r["status"] == "compiled")
    errors = sum(1 for r in rows if r["status"] == "error")

    print(f"Total: {len(rows)}  |  Compiled: {compiled}  |  Errors: {errors}")
    print()
    for r in sorted(rows, key=lambda x: x.get("compiled_at", ""), reverse=True)[:50]:
        status_icon = "✓" if r["status"] == "compiled" else "✗"
        print(f"  {status_icon} {r['identifier']:<30} {r['jurisdiction']:<10} {r['rank']:<25} {r.get('compiled_at','')[:19]}")
    if len(rows) > 50:
        print(f"  ... and {len(rows) - 50} more")


def _cli_log() -> None:
    """
    Usage: python -m src.compiler.tracker log [--n 20]
    Print recent compile run log entries.
    """
    import argparse
    p = argparse.ArgumentParser()
    p.add_argument("--n", type=int, default=20, help="Number of entries to show")
    args = p.parse_args(sys.argv[2:])

    if not LOG_PATH.exists():
        print("No compile log yet.")
        return

    lines = LOG_PATH.read_text().strip().splitlines()
    for line in lines[-args.n:]:
        entry = json.loads(line)
        print(
            f"[{entry['timestamp']}] jurisdiction={entry['jurisdiction']} "
            f"compiled={entry['compiled']} skipped={entry['skipped']} errors={entry['errors']}"
        )
        if entry.get("error_identifiers"):
            print(f"  errors: {', '.join(entry['error_identifiers'])}")


def main() -> None:
    subcommands = {
        "mark": _cli_mark,
        "error": _cli_error,
        "status": _cli_status,
        "log": _cli_log,
    }
    if len(sys.argv) < 2 or sys.argv[1] not in subcommands:
        print(f"Usage: python -m src.compiler.tracker <{'|'.join(subcommands)}>")
        sys.exit(1)
    subcommands[sys.argv[1]]()


if __name__ == "__main__":
    main()
