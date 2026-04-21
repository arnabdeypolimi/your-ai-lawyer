"""Generate jurisdiction overview notes from compiled laws."""

from collections import defaultdict
from datetime import date
from pathlib import Path

import frontmatter

ROOT = Path(__file__).parents[2]
KNOWLEDGE_DIR = ROOT / "knowledge"

COUNTRY_NAMES = {
    "es": "Spain",
    "fr": "France",
    "de": "Germany",
    "it": "Italy",
    "pt": "Portugal",
}

RANK_ORDER = [
    "constitucion", "ley organica", "ley orgánica", "ley", "real decreto legislativo",
    "real decreto", "orden ministerial", "orden", "resolucion", "resolución",
]


def build_jurisdiction_note(country: str) -> None:
    laws_dir = KNOWLEDGE_DIR / "laws" / country
    if not laws_dir.exists():
        return

    by_rank: dict[str, list[dict]] = defaultdict(list)
    for md in sorted(laws_dir.glob("*.md")):
        try:
            post = frontmatter.load(str(md))
            meta = post.metadata
            by_rank[meta.get("rank", "other")].append(
                {"identifier": meta.get("identifier", md.stem), "title": meta.get("title", ""), "status": meta.get("status", "")}
            )
        except Exception:
            continue

    total = sum(len(v) for v in by_rank.values())
    name = COUNTRY_NAMES.get(country, country.upper())

    lines = [
        f"# {name} — Legal Jurisdiction Overview",
        "",
        f"**Country code:** {country}  ",
        f"**Compiled laws:** {total}  ",
        f"**Last updated:** {date.today().isoformat()}",
        "",
        "## Laws by Rank",
    ]

    for rank in RANK_ORDER:
        if rank in by_rank:
            lines.append(f"\n### {rank.title()} ({len(by_rank[rank])})")
            for law in by_rank[rank][:20]:
                status = " *(repealed)*" if law["status"] == "repealed" else ""
                lines.append(f"- [[{law['identifier']}]] — {law['title'][:70]}{status}")
            if len(by_rank[rank]) > 20:
                lines.append(f"- *... and {len(by_rank[rank]) - 20} more*")

    for rank, laws in by_rank.items():
        if rank not in RANK_ORDER:
            lines.append(f"\n### {rank.title()} ({len(laws)})")
            for law in laws[:10]:
                lines.append(f"- [[{law['identifier']}]] — {law['title'][:70]}")

    out = KNOWLEDGE_DIR / "jurisdictions" / f"{country}.md"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text("\n".join(lines) + "\n", encoding="utf-8")


if __name__ == "__main__":
    import sys
    country = sys.argv[1] if len(sys.argv) > 1 else "es"
    build_jurisdiction_note(country)
    print(f"Written: knowledge/jurisdictions/{country}.md")
