# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Setup

```bash
uv sync                                    # install dependencies
git submodule update --init --recursive    # initialize law submodules
```

Then run `/setup` inside Claude Code to pick an output language (en/es/ca/fr/it/de/pt). The choice is stored in `.claude/settings.json → env.OUTPUT_LANGUAGE` and every `/compile` + `/qa` reads it via `uv run python -m src.config get_language`. Already-compiled notes are not retroactively translated — use `/compile --force` to re-localize.

No API key required. `/compile` and `/qa` run entirely within Claude Code using its own intelligence and local ChromaDB embeddings.

## Slash commands (primary interface)

| Command | Effect |
|---------|--------|
| `/setup es` | Pick output language (en/es/ca/fr/it/de/pt) for compiled notes + `/qa` |
| `/compile es` | Compile all Spain laws (national + all regions) |
| `/compile es-ct --limit 10` | Compile up to 10 Cataluña laws |
| `/compile es --rank ley --limit 20` | Compile only `ley`-rank laws |
| `/compile es --force` | Recompile even if unchanged |
| `/index` | Build/update ChromaDB from compiled notes + raw chunks |
| `/index --compiled-only` | Skip raw chunk indexing |
| `/search housing rights --country es --n 10` | Semantic search |
| `/qa What are tenant rights in Spain?` | RAG answer with citations |
| `/review-contract ~/lease.pdf` | Check a contract PDF against the indexed laws; writes lease.reviewed.pdf |
| `/contract-qa ~/lease.pdf <question>` | Follow-up questions about a reviewed contract |

Supported region codes for Spain: `es` (national), `es-ct` (Cataluña), `es-md` (Madrid), `es-an` (Andalucía), `es-pv` (País Vasco), `es-ga` (Galicia), `es-vc` (Valencia), and 11 more.

Run modules directly when iterating on the pipeline:
```bash
uv run python -m src.compiler.list_files es-ct --limit 5     # preview files to compile
uv run python -m src.compiler.tracker status                  # compilation progress
uv run python -m src.compiler.tracker status --jurisdiction es-ct
uv run python -m src.compiler.tracker log --n 10              # recent compile runs
uv run python -m src.indexer.embed --country es --compiled-only
uv run python -m src.query.search "right to housing" --country es
uv run python -m src.contract.extract <pdf> [--status]
uv run python -m src.contract.annotate <pdf> [--check]
uv run python -m src.compiler.jurisdictions es
uv run pytest                                                 # run the test suite
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
uv run python -m src.compiler.tracker log-run <jur> --compiled N [--skipped N] [--error-ids <id> ...]
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

### Contract review (`src/contract/`)
`/review-contract` runs three steps: `extract.py` splits the PDF into numbered passages with word-level PDF coordinates (`passages.json`, `passages.txt`), Claude writes `findings.json`, then `annotate.py` validates it and paints highlights plus a page-1 summary note onto `<stem>.reviewed.pdf`. For `<dir>/<stem>.pdf` everything lands beside it: `<stem>.review/{passages.json,passages.txt,findings.json}` and `<stem>.reviewed.pdf`; the original is never modified.

Findings carry `confidence` of `high` (red), `medium` (orange) or `low` (yellow). `high` requires a citation with an `article`; `medium`/`high` require at least one citation. `findings.py::validate` checks every citation through `ChromaCitationIndex` before the PDF is written: the identifier must be in the Chroma index, and an `article` must exist either as a `raw:<id>:art<N>` doc or as an `Artículo N` heading line in the law's raw source file (located via the `source_path` of its indexed chunks). An unknown identifier or article fails `--check` and the annotate run.

CLIs: `extract <pdf>` extracts; `--status` prints `no-review`/`incomplete`/`reviewed`/`changed` (`reviewed` only once the annotated PDF exists and is newer than `findings.json`). `annotate <pdf>` validates + writes the PDF; `--check` validates without writing. Both exit 1 with one red line on error (missing file, no review data, changed contract, bad findings).
