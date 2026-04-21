"""Semantic search over the legal knowledge base."""

import argparse
import sys
from pathlib import Path

import chromadb
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

ROOT = Path(__file__).parents[2]
CHROMA_DIR = ROOT / "data" / "chroma"

console = Console()


def _get_collections(client: chromadb.PersistentClient):
    compiled = client.get_or_create_collection("compiled", metadata={"hnsw:space": "cosine"})
    raw_chunks = client.get_or_create_collection("raw_chunks", metadata={"hnsw:space": "cosine"})
    return compiled, raw_chunks


def search(
    query: str,
    country: str | None = None,
    rank: str | None = None,
    n_results: int = 5,
    raw: bool = False,
) -> list[dict]:
    """Return search results from the vector index as a list of dicts."""
    if not CHROMA_DIR.exists():
        console.print("[red]Index not found. Run /index first.[/red]")
        sys.exit(1)

    client = chromadb.PersistentClient(path=str(CHROMA_DIR))
    compiled_col, raw_col = _get_collections(client)

    where: dict = {}
    if country and rank:
        where = {"$and": [{"country": {"$eq": country}}, {"rank": {"$eq": rank}}]}
    elif country:
        where = {"country": {"$eq": country}}
    elif rank:
        where = {"rank": {"$eq": rank}}

    results = []

    # Search compiled notes first (higher signal)
    if not raw and compiled_col.count() > 0:
        kwargs = {"query_texts": [query], "n_results": min(n_results, compiled_col.count())}
        if where:
            kwargs["where"] = where
        res = compiled_col.query(**kwargs)
        for doc, meta, dist in zip(res["documents"][0], res["metadatas"][0], res["distances"][0]):
            results.append({
                "type": "compiled",
                "identifier": meta["identifier"],
                "title": meta["title"],
                "country": meta.get("country", ""),
                "jurisdiction": meta.get("jurisdiction", ""),
                "rank": meta.get("rank", ""),
                "status": meta.get("status", ""),
                "source_path": meta.get("source_path", ""),
                "article_num": "",
                "text": doc[:600],
                "score": round(1 - dist, 3),
            })

    # Also search raw chunks for specific article context
    if raw_col.count() > 0:
        kwargs = {"query_texts": [query], "n_results": min(n_results, raw_col.count())}
        if where:
            kwargs["where"] = where
        res = raw_col.query(**kwargs)
        for doc, meta, dist in zip(res["documents"][0], res["metadatas"][0], res["distances"][0]):
            results.append({
                "type": "raw",
                "identifier": meta["identifier"],
                "title": meta["title"],
                "country": meta.get("country", ""),
                "jurisdiction": meta.get("jurisdiction", ""),
                "rank": meta.get("rank", ""),
                "status": meta.get("status", ""),
                "source_path": meta.get("source_path", ""),
                "article_num": meta.get("article_num", ""),
                "text": doc[:600],
                "score": round(1 - dist, 3),
            })

    # Sort by score descending, deduplicate by identifier keeping highest score
    seen: dict[str, dict] = {}
    for r in sorted(results, key=lambda x: x["score"], reverse=True):
        key = f"{r['identifier']}:{r['article_num']}"
        if key not in seen:
            seen[key] = r

    return list(seen.values())[:n_results]


def print_results(results: list[dict]) -> None:
    if not results:
        console.print("[yellow]No results found.[/yellow]")
        return

    for i, r in enumerate(results, 1):
        article_label = f", Art. {r['article_num']}" if r["article_num"] else ""
        citation = f"[{r['identifier']}{article_label}]"
        header = f"{i}. {r['title'][:65]} {citation}"
        body = (
            f"[dim]Rank:[/dim] {r['rank']}  "
            f"[dim]Jurisdiction:[/dim] {r['jurisdiction']}  "
            f"[dim]Score:[/dim] {r['score']}  "
            f"[dim]Status:[/dim] {r['status']}\n\n"
            f"{r['text'].strip()}\n\n"
            f"[dim]Source: {r['source_path']}[/dim]"
        )
        console.print(Panel(body, title=header, border_style="blue"))


def main() -> None:
    parser = argparse.ArgumentParser(description="Search the legal knowledge base")
    parser.add_argument("query", nargs="?", help="Search query")
    parser.add_argument("--country", help="Filter by country code")
    parser.add_argument("--rank", help="Filter by legal rank")
    parser.add_argument("--n", type=int, default=5, help="Number of results (default: 5)")
    parser.add_argument("--raw", action="store_true", help="Search raw chunks only")
    args = parser.parse_args()

    if not args.query:
        parser.print_help()
        sys.exit(1)

    results = search(args.query, country=args.country, rank=args.rank, n_results=args.n, raw=args.raw)
    print_results(results)


if __name__ == "__main__":
    main()
