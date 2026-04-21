"""Build or update the ChromaDB vector index from compiled notes and raw law chunks."""

import argparse
import sys
from pathlib import Path

import chromadb
import frontmatter
from rich.console import Console
from rich.progress import BarColumn, MofNCompleteColumn, Progress, SpinnerColumn, TextColumn

from src.compiler.parser import iter_laws, parse_law

ROOT = Path(__file__).parents[2]
KNOWLEDGE_DIR = ROOT / "knowledge"
CHROMA_DIR = ROOT / "data" / "chroma"

console = Console()

CHUNK_SIZE = 500  # tokens ≈ chars / 4; use char limit of 2000


def _get_collections(client: chromadb.PersistentClient):
    compiled = client.get_or_create_collection(
        "compiled",
        metadata={"hnsw:space": "cosine"},
    )
    raw_chunks = client.get_or_create_collection(
        "raw_chunks",
        metadata={"hnsw:space": "cosine"},
    )
    return compiled, raw_chunks


def _chunk_text(text: str, max_chars: int = 2000) -> list[str]:
    paragraphs = text.split("\n\n")
    chunks, current = [], ""
    for para in paragraphs:
        if len(current) + len(para) > max_chars and current:
            chunks.append(current.strip())
            current = para
        else:
            current += "\n\n" + para if current else para
    if current.strip():
        chunks.append(current.strip())
    return chunks


def index_compiled(compiled_col, country: str | None = None) -> int:
    dirs = []
    if country:
        d = KNOWLEDGE_DIR / "laws" / country
        if d.exists():
            dirs.append(d)
    else:
        laws_dir = KNOWLEDGE_DIR / "laws"
        if laws_dir.exists():
            dirs = [d for d in laws_dir.iterdir() if d.is_dir()]

    total = 0
    for d in dirs:
        for md in sorted(d.glob("*.md")):
            try:
                post = frontmatter.load(str(md))
                meta = post.metadata
                doc_id = f"compiled:{meta.get('identifier', md.stem)}"
                text = post.content.strip()
                if not text:
                    continue
                compiled_col.upsert(
                    ids=[doc_id],
                    documents=[text],
                    metadatas=[{
                        "identifier": meta.get("identifier", md.stem),
                        "title": meta.get("title", ""),
                        "country": meta.get("country", ""),
                        "jurisdiction": meta.get("jurisdiction", ""),
                        "rank": meta.get("rank", ""),
                        "status": meta.get("status", ""),
                        "source_path": str(md.relative_to(ROOT)),
                        "type": "compiled",
                    }],
                )
                total += 1
            except Exception as exc:
                console.print(f"[yellow]Compiled index error {md.stem}: {exc}[/yellow]")
    return total


def index_raw_chunks(raw_col, country: str, submodule: str | None = None) -> int:
    submodule_dir = ROOT / (submodule or f"legalize-{country}")
    if not submodule_dir.exists():
        console.print(f"[red]Submodule not found: {submodule_dir}[/red]")
        return 0

    paths = iter_laws(submodule_dir, country)
    total = 0

    with Progress(
        SpinnerColumn(),
        TextColumn("{task.description}"),
        BarColumn(),
        MofNCompleteColumn(),
        console=console,
    ) as progress:
        task = progress.add_task(f"Indexing raw chunks ({country})", total=len(paths))

        for path in paths:
            progress.update(task, advance=1, description=path.stem)
            try:
                doc = parse_law(path)
                # Index per-article chunks if articles exist, else chunk the body
                if doc.articles:
                    for art in doc.articles:
                        chunk_text = f"Artículo {art.number}: {art.title}\n{art.text}".strip()
                        if not chunk_text:
                            continue
                        doc_id = f"raw:{doc.identifier}:art{art.number}"
                        raw_col.upsert(
                            ids=[doc_id],
                            documents=[chunk_text[:2000]],
                            metadatas=[{
                                "identifier": doc.identifier,
                                "title": doc.title,
                                "country": doc.country,
                                "jurisdiction": doc.jurisdiction,
                                "rank": doc.rank,
                                "status": doc.status,
                                "article_num": art.number,
                                "source_path": str(path.relative_to(ROOT)),
                                "type": "raw_chunk",
                            }],
                        )
                        total += 1
                else:
                    for i, chunk in enumerate(_chunk_text(doc.body)):
                        doc_id = f"raw:{doc.identifier}:chunk{i}"
                        raw_col.upsert(
                            ids=[doc_id],
                            documents=[chunk],
                            metadatas=[{
                                "identifier": doc.identifier,
                                "title": doc.title,
                                "country": doc.country,
                                "jurisdiction": doc.jurisdiction,
                                "rank": doc.rank,
                                "status": doc.status,
                                "article_num": "",
                                "source_path": str(path.relative_to(ROOT)),
                                "type": "raw_chunk",
                            }],
                        )
                        total += 1
            except Exception as exc:
                console.print(f"[yellow]Raw index error {path.stem}: {exc}[/yellow]")

    return total


def main() -> None:
    parser = argparse.ArgumentParser(description="Build/update vector index")
    parser.add_argument("--country", default="es", help="Country code (default: es)")
    parser.add_argument("--compiled-only", action="store_true")
    parser.add_argument("--raw-only", action="store_true")
    args = parser.parse_args()

    CHROMA_DIR.mkdir(parents=True, exist_ok=True)
    client = chromadb.PersistentClient(path=str(CHROMA_DIR))
    compiled_col, raw_col = _get_collections(client)

    if not args.raw_only:
        console.print("[bold]Indexing compiled notes...[/bold]")
        n = index_compiled(compiled_col, args.country)
        console.print(f"  Compiled notes indexed: {n}")

    if not args.compiled_only:
        console.print("[bold]Indexing raw law chunks...[/bold]")
        n = index_raw_chunks(raw_col, args.country)
        console.print(f"  Raw chunks indexed: {n}")

    console.print("\n[green]Index complete.[/green]")
    console.print(f"  compiled collection: {compiled_col.count()} docs")
    console.print(f"  raw_chunks collection: {raw_col.count()} docs")


if __name__ == "__main__":
    main()
