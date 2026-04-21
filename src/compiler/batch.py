"""Batch compile raw law files into the knowledge graph."""

import argparse
import sys
from datetime import date
from pathlib import Path

from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn, MofNCompleteColumn

from .extractor import extract
from .parser import LawDocument, iter_laws, parse_law
from .tracker import (
    is_changed,
    load_index,
    load_manifest,
    log_run,
    mark_compiled,
    mark_error,
    save_index,
    save_manifest,
)

ROOT = Path(__file__).parents[2]
KNOWLEDGE_DIR = ROOT / "knowledge"

console = Console()


def _slug(text: str) -> str:
    import re
    return re.sub(r"[^\w-]", "-", text.lower().strip()).strip("-")


def _write_compiled_note(doc: LawDocument, extracted: dict) -> Path:
    out_dir = KNOWLEDGE_DIR / "laws" / doc.country
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / f"{doc.identifier}.md"

    concepts_wikilinks = " · ".join(f"[[{c}]]" for c in extracted.get("concepts", []))
    provisions = "\n".join(f"- {p}" for p in extracted.get("key_provisions", []))
    cross_refs = "\n".join(
        f"- [[{r}]]" for r in extracted.get("cross_references", []) if r != doc.identifier
    )
    supersedes = "\n".join(f"- [[{r}]]" for r in extracted.get("supersedes", []))
    implements = "\n".join(f"- [[{r}]]" for r in extracted.get("implements", []))

    lines = [
        "---",
        f"identifier: {doc.identifier}",
        f"title: \"{doc.title}\"",
        f"country: {doc.country}",
        f"jurisdiction: {doc.jurisdiction}",
        f"rank: {doc.rank}",
        f"status: {doc.status}",
        f"publication_date: {doc.publication_date}",
        f"last_updated: {doc.last_updated}",
        f"source: {doc.source}",
        f"compiled_at: {date.today().isoformat()}",
        "---",
        "",
        f"# {doc.title}",
        "",
        "## Summary",
        extracted.get("summary", ""),
        "",
    ]

    if provisions:
        lines += ["## Key Provisions", provisions, ""]

    if cross_refs:
        lines += ["## Cross-References", cross_refs, ""]

    if supersedes:
        lines += ["## Supersedes", supersedes, ""]

    if implements:
        lines += ["## Implements", implements, ""]

    if concepts_wikilinks:
        lines += ["## Concepts", concepts_wikilinks, ""]

    lines += [
        "## Source",
        f"Raw text: `{doc.raw_path.relative_to(ROOT)}`",
        "",
    ]

    out_path.write_text("\n".join(lines), encoding="utf-8")
    return out_path


def _update_concept_files(doc: LawDocument, extracted: dict) -> None:
    concepts_dir = KNOWLEDGE_DIR / "concepts"
    concepts_dir.mkdir(parents=True, exist_ok=True)

    for concept in extracted.get("concepts", []):
        slug = _slug(concept)
        concept_path = concepts_dir / f"{slug}.md"

        backlink = f"- [[{doc.identifier}]] — {doc.title[:60]}"

        if concept_path.exists():
            existing = concept_path.read_text(encoding="utf-8")
            if doc.identifier not in existing:
                concept_path.write_text(existing.rstrip() + "\n" + backlink + "\n", encoding="utf-8")
        else:
            concept_path.write_text(
                f"# {concept}\n\n## Laws\n{backlink}\n",
                encoding="utf-8",
            )


def compile_country(country: str, submodule: str | None = None, limit: int | None = None, force: bool = False) -> None:
    submodule_dir = ROOT / (submodule or f"legalize-{country}")
    if not submodule_dir.exists():
        console.print(f"[red]Submodule not found: {submodule_dir}[/red]")
        sys.exit(1)

    paths = iter_laws(submodule_dir, country)
    if limit:
        paths = paths[:limit]

    manifest = load_manifest()
    index = load_index()
    compiled = skipped = errors = 0
    error_ids: list[str] = []

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        BarColumn(),
        MofNCompleteColumn(),
        console=console,
    ) as progress:
        task = progress.add_task(f"Compiling {country}", total=len(paths))

        for path in paths:
            progress.update(task, advance=1, description=f"{path.stem}")

            if not force and not is_changed(path, manifest):
                skipped += 1
                continue

            try:
                doc = parse_law(path)
                extracted = extract(doc)
                note_path = _write_compiled_note(doc, extracted)
                _update_concept_files(doc, extracted)
                mark_compiled(path, doc.identifier, doc.jurisdiction, doc.rank, note_path, manifest, index)
                compiled += 1
            except Exception as exc:
                doc_id = path.stem
                console.print(f"[yellow]Error processing {doc_id}: {exc}[/yellow]")
                mark_error(path, doc_id, country, "", str(exc), index)
                error_ids.append(doc_id)
                errors += 1

    save_manifest(manifest)
    save_index(index)
    log_run(country, compiled, skipped, errors, error_ids)
    console.print(
        f"\n[green]Done.[/green] Compiled: {compiled} | Skipped (unchanged): {skipped} | Errors: {errors}"
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="Compile raw law files into knowledge graph")
    parser.add_argument("country", help="Country code, e.g. es")
    parser.add_argument("--submodule", help="Submodule directory name (default: legalize-<country>)")
    parser.add_argument("--limit", type=int, help="Max files to process")
    parser.add_argument("--force", action="store_true", help="Recompile even if unchanged")
    args = parser.parse_args()

    compile_country(args.country, submodule=args.submodule, limit=args.limit, force=args.force)


if __name__ == "__main__":
    main()
