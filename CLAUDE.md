# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Setup

```bash
uv sync                                    # install dependencies
git submodule update --init --recursive    # initialize law submodules
```

No API key required. `/compile` and `/qa` run entirely within Claude Code using its own intelligence and local ChromaDB embeddings.

## Slash commands (primary interface)

| Command | Effect |
|---------|--------|
| `/compile es` | Compile all Spain laws (national + all regions) |
| `/compile es-ct --limit 10` | Compile up to 10 Cataluña laws |
| `/compile es --rank ley --limit 20` | Compile only `ley`-rank laws |
| `/compile es --force` | Recompile even if unchanged |
| `/index` | Build/update ChromaDB from compiled notes + raw chunks |
| `/index --compiled-only` | Skip raw chunk indexing |
| `/search housing rights --country es --n 10` | Semantic search |
| `/qa What are tenant rights in Spain?` | RAG answer with citations |

Supported region codes for Spain: `es` (national), `es-ct` (Cataluña), `es-md` (Madrid), `es-an` (Andalucía), `es-pv` (País Vasco), `es-ga` (Galicia), `es-vc` (Valencia), and 11 more.

Run modules directly when iterating on the pipeline:
```bash
uv run python -m src.compiler.list_files es-ct --limit 5     # preview files to compile
uv run python -m src.compiler.tracker status                  # compilation progress
uv run python -m src.compiler.tracker status --jurisdiction es-ct
uv run python -m src.compiler.tracker log --n 10              # recent compile runs
uv run python -m src.indexer.embed --country es --compiled-only
uv run python -m src.query.search "right to housing" --country es
uv run python -m src.compiler.jurisdictions es
```

## Architecture

### Data flow

```
legalize-<country>/              # raw submodule (markdown + YAML frontmatter)
    │
    ▼ /compile slash command     # Claude Code reads files, writes compiled notes
    │   └─ list_files.py         # lists files needing compilation (checks manifest)
    │   └─ tracker.py mark       # records each compiled file in index + manifest
    │
knowledge/laws/<country>/        # compiled Obsidian notes with wikilinks
knowledge/concepts/              # concept index files (backlinks aggregated here)
knowledge/jurisdictions/         # per-country overview note
    │
    ▼ src/indexer/embed.py       # ChromaDB upsert (local ONNX embeddings, no API key)
    │
data/chroma/                     # persistent vector store (gitignored)
    │
    ▼ src/query/search.py        # cosine similarity → ranked results + citations
```

### Tracking files (`data/`)

| File | Purpose |
|------|---------|
| `manifest.json` | `{raw_path: md5_hash}` — change detection, skips unchanged files |
| `index.json` | `{identifier: {status, compiled_at, note_path, error}}` — per-law status |
| `compile.log` | NDJSON of each compile run: timestamp, jurisdiction, counts, error IDs |

Tracker CLI:
```bash
uv run python -m src.compiler.tracker status [--jurisdiction es-ct]
uv run python -m src.compiler.tracker log [--n 20]
uv run python -m src.compiler.tracker mark <id> <raw> <note> <jur> <rank>
uv run python -m src.compiler.tracker error <id> <raw> <jur> <rank> <msg>
```

### Submodule convention
Each country's raw laws live in `legalize-<country>/`. Inside, directories match jurisdiction codes: `es/` (national), `es-ct/`, `es-md/`, etc. `iter_laws()` in `parser.py` handles both full-country and region-specific traversal. To add a new country:
```bash
git submodule add <url> legalize-fr
/compile fr
/index --country fr
```

### Compiled note format
Each `knowledge/laws/<country>/<identifier>.md` has YAML frontmatter (identifier, title, country, jurisdiction, rank, status, compiled_at) then sections: Summary, Key Provisions, Cross-References, Supersedes, Implements, Concepts (Obsidian `[[wikilinks]]`), Source path. The `knowledge/` directory is itself an Obsidian vault.

### ChromaDB collections
Two collections in `data/chroma/` using local ONNX embeddings (no API key):
- `compiled` — one doc per compiled note
- `raw_chunks` — one doc per article (or 2000-char paragraph chunk for laws without article headers)

Document IDs: `compiled:<id>` and `raw:<id>:art<N>` / `raw:<id>:chunk<N>`. Search queries both collections, deduplicates, returns top-N by cosine similarity.

### Article parsing (`parser.py`)
`_ARTICLE_RE` matches `###`–`######` headers containing `Artículo N`. Laws without this pattern (older texts, short orders) produce `articles=[]` and are chunked by paragraph in the indexer. Jurisdiction is inferred from the parent directory name when not in frontmatter.

### `extractor.py` (optional, API-based alternative)
Calls `claude-sonnet-4-6` with prompt caching (`cache_control: ephemeral`) to extract law knowledge programmatically. Used by `batch.py` for automated bulk compilation without Claude Code. Requires `ANTHROPIC_API_KEY`. Truncates law body to 6000 chars.
