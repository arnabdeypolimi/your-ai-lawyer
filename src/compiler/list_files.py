"""List law files that need compilation, for use by Claude Code slash commands."""

import argparse
import hashlib
import json
import sys
from pathlib import Path

from .parser import iter_laws, parse_law

ROOT = Path(__file__).parents[2]
MANIFEST_PATH = ROOT / "data" / "manifest.json"
INDEX_PATH = ROOT / "data" / "index.json"


def _file_hash(path: Path) -> str:
    return hashlib.md5(path.read_bytes()).hexdigest()


def _load_json(path: Path) -> dict:
    if path.exists():
        return json.loads(path.read_text())
    return {}


def _compiled_raw_paths(index: dict) -> set[str]:
    return {
        entry["raw_path"]
        for entry in index.values()
        if entry.get("status") == "compiled" and entry.get("raw_path")
    }


def main() -> None:
    parser = argparse.ArgumentParser(
        description="List law files needing compilation. Outputs JSON array."
    )
    parser.add_argument(
        "jurisdiction",
        help="Jurisdiction code: country (es) or region (es-ct, es-md, es-pv, ...)",
    )
    parser.add_argument("--limit", type=int, help="Max files to return")
    parser.add_argument("--force", action="store_true", help="Include unchanged files")
    parser.add_argument("--rank", help="Filter by rank (e.g. ley, constitucion)")
    args = parser.parse_args()

    jurisdiction = args.jurisdiction
    # Derive submodule from country prefix (es-ct → legalize-es)
    country_prefix = jurisdiction.split("-")[0]
    submodule_dir = ROOT / f"legalize-{country_prefix}"

    if not submodule_dir.exists():
        print(
            json.dumps({"error": f"Submodule not found: legalize-{country_prefix}"}),
            file=sys.stderr,
        )
        sys.exit(1)

    manifest = _load_json(MANIFEST_PATH)
    compiled_raw = _compiled_raw_paths(_load_json(INDEX_PATH))
    paths = iter_laws(submodule_dir, jurisdiction)

    if not args.force:
        def _needs_compile(p: Path) -> bool:
            rel = str(p.relative_to(ROOT))
            # Skip only when both signals agree the file is already compiled and unchanged
            return not (manifest.get(rel) == _file_hash(p) and rel in compiled_raw)

        paths = [p for p in paths if _needs_compile(p)]

    results = []
    for path in paths:
        try:
            doc = parse_law(path)
            if args.rank and doc.rank != args.rank:
                continue
            results.append(
                {
                    "path": str(path),
                    "identifier": doc.identifier,
                    "title": doc.title,
                    "rank": doc.rank,
                    "jurisdiction": doc.jurisdiction,
                    "country": doc.country,
                    "status": doc.status,
                    "publication_date": doc.publication_date,
                    "source": doc.source,
                    "article_count": len(doc.articles),
                }
            )
        except Exception as exc:
            results.append({"path": str(path), "error": str(exc)})

        if args.limit and len(results) >= args.limit:
            break

    print(json.dumps(results, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
