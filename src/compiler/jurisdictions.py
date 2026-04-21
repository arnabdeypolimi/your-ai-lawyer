"""Generate jurisdiction overview notes from compiled laws."""

from collections import defaultdict
from datetime import date
from pathlib import Path

import frontmatter

from .. import config

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

# Localized jurisdiction overview headers (falls back to "en" for unsupported codes)
HEADERS: dict[str, dict[str, str]] = {
    "en": {
        "title_suffix": "Legal Jurisdiction Overview",
        "country_code": "Country code",
        "compiled_laws": "Compiled laws",
        "last_updated": "Last updated",
        "laws_by_rank": "Laws by Rank",
        "more_suffix": "more",
        "repealed": "(repealed)",
    },
    "es": {
        "title_suffix": "Panorama de la Jurisdicción Legal",
        "country_code": "Código de país",
        "compiled_laws": "Leyes compiladas",
        "last_updated": "Última actualización",
        "laws_by_rank": "Leyes por Rango",
        "more_suffix": "más",
        "repealed": "(derogada)",
    },
    "ca": {
        "title_suffix": "Panorama de la Jurisdicció Legal",
        "country_code": "Codi de país",
        "compiled_laws": "Lleis compilades",
        "last_updated": "Última actualització",
        "laws_by_rank": "Lleis per Rang",
        "more_suffix": "més",
        "repealed": "(derogada)",
    },
    "fr": {
        "title_suffix": "Aperçu de la Juridiction Légale",
        "country_code": "Code pays",
        "compiled_laws": "Lois compilées",
        "last_updated": "Dernière mise à jour",
        "laws_by_rank": "Lois par Rang",
        "more_suffix": "de plus",
        "repealed": "(abrogée)",
    },
    "it": {
        "title_suffix": "Panoramica della Giurisdizione Legale",
        "country_code": "Codice paese",
        "compiled_laws": "Leggi compilate",
        "last_updated": "Ultimo aggiornamento",
        "laws_by_rank": "Leggi per Rango",
        "more_suffix": "altre",
        "repealed": "(abrogata)",
    },
    "de": {
        "title_suffix": "Überblick über die Rechtsprechung",
        "country_code": "Ländercode",
        "compiled_laws": "Kompilierte Gesetze",
        "last_updated": "Zuletzt aktualisiert",
        "laws_by_rank": "Gesetze nach Rang",
        "more_suffix": "weitere",
        "repealed": "(aufgehoben)",
    },
    "pt": {
        "title_suffix": "Panorama da Jurisdição Legal",
        "country_code": "Código do país",
        "compiled_laws": "Leis compiladas",
        "last_updated": "Última atualização",
        "laws_by_rank": "Leis por Nível",
        "more_suffix": "mais",
        "repealed": "(revogada)",
    },
}


def build_jurisdiction_note(country: str, language: str | None = None) -> None:
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
    lang = language or config.get_language()
    h = HEADERS.get(lang, HEADERS["en"])

    lines = [
        f"# {name} — {h['title_suffix']}",
        "",
        f"**{h['country_code']}:** {country}  ",
        f"**{h['compiled_laws']}:** {total}  ",
        f"**{h['last_updated']}:** {date.today().isoformat()}",
        "",
        f"## {h['laws_by_rank']}",
    ]

    for rank in RANK_ORDER:
        if rank in by_rank:
            lines.append(f"\n### {rank.title()} ({len(by_rank[rank])})")
            for law in by_rank[rank][:20]:
                status = f" *{h['repealed']}*" if law["status"] == "repealed" else ""
                lines.append(f"- [[{law['identifier']}]] — {law['title'][:70]}{status}")
            if len(by_rank[rank]) > 20:
                lines.append(f"- *... and {len(by_rank[rank]) - 20} {h['more_suffix']}*")

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
