"""Lint the legal knowledge base for health issues."""

import argparse
import json
import re
from pathlib import Path

import frontmatter
from rich.console import Console
from rich.table import Table
from rich import box

ROOT = Path(__file__).parents[2]
KNOWLEDGE_DIR = ROOT / "knowledge"
DATA_DIR = ROOT / "data"
MANIFEST_PATH = DATA_DIR / "manifest.json"
INDEX_PATH = DATA_DIR / "index.json"

console = Console()

WIKILINK_RE = re.compile(r"\[\[([^\]|#]+?)(?:[|#][^\]]*)?\]\]")


def _load_json(path: Path) -> dict:
    if path.exists():
        return json.loads(path.read_text())
    return {}


# ── checks ──────────────────────────────────────────────────────────────────

def check_error_laws(index: dict) -> list[dict]:
    """Laws that failed compilation."""
    return [v for v in index.values() if v.get("status") == "error"]


def check_never_compiled(manifest: dict, jurisdiction: str | None) -> list[Path]:
    """Raw law files that have never been processed (not in manifest at all)."""
    never = []
    submodule_dirs = sorted(ROOT.glob("legalize-*/"))
    for submodule in submodule_dirs:
        country = submodule.name.removeprefix("legalize-")
        for jur_dir in submodule.iterdir():
            if not jur_dir.is_dir() or jur_dir.name.startswith("."):
                continue
            if jurisdiction and not jur_dir.name.startswith(jurisdiction):
                continue
            for md in jur_dir.glob("*.md"):
                if str(md) not in manifest:
                    never.append(md)
    return never


def check_orphaned_notes(index: dict) -> list[str]:
    """Compiled notes whose raw source file no longer exists."""
    orphaned = []
    for identifier, entry in index.items():
        if entry.get("status") != "compiled":
            continue
        raw = entry.get("raw_path")
        if raw and not (ROOT / raw).exists():
            orphaned.append(identifier)
    return orphaned


def check_missing_note_files(index: dict) -> list[str]:
    """Index says compiled but the note file is gone."""
    missing = []
    for identifier, entry in index.items():
        if entry.get("status") != "compiled":
            continue
        note = entry.get("note_path")
        if note and not (ROOT / note).exists():
            missing.append(identifier)
    return missing


def check_broken_wikilinks(jurisdiction: str | None, limit: int = 200) -> list[dict]:
    """Wikilinks in compiled notes that point to non-existent compiled notes."""
    compiled_ids: set[str] = set()
    laws_dir = KNOWLEDGE_DIR / "laws"
    if laws_dir.exists():
        for md in laws_dir.rglob("*.md"):
            compiled_ids.add(md.stem)

    broken = []
    checked = 0
    for md in sorted((KNOWLEDGE_DIR / "laws").rglob("*.md")) if laws_dir.exists() else []:
        if checked >= limit:
            break
        try:
            text = md.read_text(encoding="utf-8")
            for match in WIKILINK_RE.finditer(text):
                target = match.group(1).strip()
                # Only flag links that look like law identifiers (BOE-A-... etc.)
                if re.match(r"[A-Z]+-[A-Z]+-\d{4}-\d+", target) and target not in compiled_ids:
                    broken.append({"source": md.stem, "target": target})
        except Exception:
            pass
        checked += 1
    return broken


def check_untracked_compiled_notes(index: dict) -> list[str]:
    """Compiled note files on disk that aren't in index.json."""
    indexed_notes = {
        entry["note_path"]
        for entry in index.values()
        if entry.get("note_path")
    }
    untracked = []
    laws_dir = KNOWLEDGE_DIR / "laws"
    if laws_dir.exists():
        for md in laws_dir.rglob("*.md"):
            rel = str(md.relative_to(ROOT))
            if rel not in indexed_notes:
                untracked.append(rel)
    return untracked


def check_concept_orphans() -> list[str]:
    """Concept files that have no laws linking back to them."""
    concepts_dir = KNOWLEDGE_DIR / "concepts"
    if not concepts_dir.exists():
        return []

    # Collect all concept slugs referenced in compiled notes
    referenced: set[str] = set()
    laws_dir = KNOWLEDGE_DIR / "laws"
    if laws_dir.exists():
        for md in laws_dir.rglob("*.md"):
            try:
                text = md.read_text(encoding="utf-8")
                for match in WIKILINK_RE.finditer(text):
                    slug = match.group(1).strip()
                    if not re.match(r"[A-Z]+-[A-Z]+-\d{4}-\d+", slug):
                        referenced.add(slug)
            except Exception:
                pass

    orphaned = []
    for concept_md in concepts_dir.glob("*.md"):
        if concept_md.stem not in referenced:
            orphaned.append(concept_md.stem)
    return orphaned


# ── report ───────────────────────────────────────────────────────────────────

def _section(title: str, items: list, item_fmt=str, warn_threshold: int = 0) -> bool:
    """Print a section. Returns True if issues found."""
    count = len(items)
    color = "green" if count == 0 else ("yellow" if count <= warn_threshold or warn_threshold == 0 else "red")
    icon = "✓" if count == 0 else "✗"
    console.print(f"\n[{color}]{icon} {title}: {count}[/{color}]")
    for item in items[:20]:
        console.print(f"   {item_fmt(item)}")
    if count > 20:
        console.print(f"   [dim]... and {count - 20} more[/dim]")
    return count > 0


def run_lint(jurisdiction: str | None = None, broken_links: bool = False) -> int:
    """Run all checks. Returns exit code (0 = clean, 1 = issues found)."""
    manifest = _load_json(MANIFEST_PATH)
    index = _load_json(INDEX_PATH)

    compiled_count = sum(1 for v in index.values() if v.get("status") == "compiled")
    error_count = sum(1 for v in index.values() if v.get("status") == "error")
    never_count = len(check_never_compiled(manifest, jurisdiction))

    # Summary header
    console.print("\n[bold]Legal Knowledge Base — Lint Report[/bold]")
    if jurisdiction:
        console.print(f"[dim]Jurisdiction filter: {jurisdiction}[/dim]")
    console.print(
        f"[dim]Index: {compiled_count} compiled, {error_count} errors | "
        f"Manifest: {len(manifest)} tracked files[/dim]"
    )

    issues = 0

    # 1. Compilation errors
    errors = check_error_laws(index)
    if _section("Compilation errors", errors,
                 item_fmt=lambda e: f"[red]{e['identifier']}[/red] — {e.get('error', '')[:80]}"):
        issues += len(errors)

    # 2. Missing note files (compiled in index but file gone)
    missing = check_missing_note_files(index)
    if _section("Compiled in index but note file missing", missing,
                 item_fmt=lambda s: f"[yellow]{s}[/yellow]"):
        issues += len(missing)

    # 3. Orphaned notes (raw source gone)
    orphaned = check_orphaned_notes(index)
    if _section("Note has no raw source (raw file deleted/moved)", orphaned,
                 item_fmt=lambda s: f"[yellow]{s}[/yellow]"):
        issues += len(orphaned)

    # 4. Untracked compiled notes (file on disk, not in index)
    untracked = check_untracked_compiled_notes(index)
    if _section("Compiled notes not tracked in index.json", untracked,
                 item_fmt=lambda s: f"[yellow]{s}[/yellow]"):
        issues += len(untracked)

    # 5. Never compiled (informational, not an error)
    never = check_never_compiled(manifest, jurisdiction)
    _section(
        f"Raw files never compiled{'  (run /compile to process)' if never else ''}",
        never[:5],  # only show sample
        item_fmt=lambda p: f"[dim]{p.parent.name}/{p.stem}[/dim]",
    )
    if len(never) > 5:
        console.print(f"   [dim]... {len(never) - 5} more not shown[/dim]")

    # 6. Orphaned concept files
    concept_orphans = check_concept_orphans()
    _section("Concept files with no law backlinks", concept_orphans,
             item_fmt=lambda s: f"[dim]{s}[/dim]")

    # 7. Broken wikilinks (opt-in, slow)
    if broken_links:
        broken = check_broken_wikilinks(jurisdiction)
        if _section("Broken wikilinks in compiled notes", broken,
                     item_fmt=lambda b: f"[yellow][[{b['target']}]][/yellow] ← {b['source']}"):
            issues += len(broken)
    else:
        console.print("\n[dim]Tip: run with --broken-links to also check wikilink targets[/dim]")

    # Final verdict
    console.print()
    if issues == 0:
        console.print("[bold green]✓ Knowledge base is healthy.[/bold green]")
    else:
        console.print(f"[bold red]✗ {issues} issue(s) found.[/bold red]")

    return 0 if issues == 0 else 1


def main() -> None:
    parser = argparse.ArgumentParser(description="Lint the legal knowledge base")
    parser.add_argument("--jurisdiction", help="Filter checks to a jurisdiction (e.g. es, es-ct)")
    parser.add_argument("--broken-links", action="store_true",
                        help="Check for broken wikilinks in compiled notes (slower)")
    args = parser.parse_args()

    import sys
    sys.exit(run_lint(jurisdiction=args.jurisdiction, broken_links=args.broken_links))


if __name__ == "__main__":
    main()
