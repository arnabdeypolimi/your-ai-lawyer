# Your AI Lawyer

A multi-country legal knowledge base that compiles raw legislation into an Obsidian-compatible knowledge graph. Law submodules provide the raw data; Claude Code reads and compiles them into structured notes with wikilinks, concept indexes, and cross-references — no external API key required.

## How it works

1. **Raw data** — Each country's laws live in a git submodule (`legalize-<country>/`), as markdown files with YAML frontmatter.
2. **Compile** — The `/compile` slash command instructs Claude Code to read each law and write a structured compiled note to `knowledge/laws/<country>/`.
3. **Index** — `/index` embeds the compiled notes and raw article chunks into a local ChromaDB vector store (no API key — uses local ONNX embeddings).
4. **Query** — `/qa` runs a semantic search and answers with inline citations to the original law text.

```
legalize-es/          ← raw Spain laws (submodule)
knowledge/
  laws/es/            ← compiled notes with summaries, wikilinks, concepts
  concepts/           ← concept index files with backlinks
  jurisdictions/      ← per-country overview notes
data/
  index.json          ← per-law compilation status
  compile.log         ← run history (NDJSON)
  manifest.json       ← change detection hashes
  chroma/             ← vector store (gitignored)
src/
  compiler/           ← parser, extractor, batch runner, tracker
  indexer/            ← ChromaDB embedding pipeline
  query/              ← semantic search
```

## Setup

```bash
git clone --recurse-submodules <repo-url>
cd your-ai-lawyer
uv sync
```

Requires [uv](https://github.com/astral-sh/uv) and [Claude Code](https://claude.ai/code).

## Usage

Open this folder in Claude Code. All interaction happens through slash commands:

### Compile laws

```
/compile es                      # all Spain (national + all autonomous communities)
/compile es-ct                   # Cataluña only
/compile es-ct --limit 10        # test run — first 10 files
/compile es --rank ley           # only laws of rank "ley"
/compile es --force              # recompile even unchanged files
```

Compiled notes are written to `knowledge/laws/<country>/` as Obsidian-compatible markdown with:
- Plain-language summary
- Key provisions list
- `[[wikilinks]]` to cross-referenced laws
- Concept tags linking to `knowledge/concepts/`
- Path back to the original source file

### Build the search index

```
/index                           # index Spain (default)
/index --country fr              # index a specific country
/index --compiled-only           # skip raw chunk indexing
```

### Query

```
/qa What are the rights of tenants in Spain?
/qa What does the Spanish Constitution say about education?
/qa Are there specific housing laws in Cataluña?
```

Answers always include inline citations (`[BOE-A-XXXX-XXXXX, Art. N]`) and a Sources section.

### Search

```
/search housing rights --country es
/search data protection --rank ley --n 10
```

### Check compilation status

```
/compile es --limit 0            # dry run — shows what needs compiling
```

Or directly:

```bash
uv run python -m src.compiler.tracker status
uv run python -m src.compiler.tracker status --jurisdiction es-ct
uv run python -m src.compiler.tracker log --n 20
```

## Adding a new country

```bash
git submodule add <legalize-XX-url> legalize-XX
git submodule update --init legalize-XX
```

Then in Claude Code:
```
/compile XX
/index --country XX
```

## Country submodules

| Submodule | Coverage | Source |
|-----------|----------|--------|
| `legalize-es` | Spain — 8,600+ national laws + 17 autonomous communities | [legalize.dev](https://legalize.dev) |

## Knowledge graph format

Each compiled note (`knowledge/laws/es/BOE-A-XXXX-XXXXX.md`) contains:

```yaml
---
identifier: BOE-A-1978-31229
title: "Constitución Española"
country: es
jurisdiction: es
rank: constitucion
status: in_force
compiled_at: 2026-04-21
---
```

Followed by Summary, Key Provisions, Cross-References, Supersedes, Implements, Concepts, and a link to the raw source file. The `knowledge/` directory is a valid Obsidian vault and can be opened directly in Obsidian.

## Tech stack

- **Python 3.12** managed with [uv](https://github.com/astral-sh/uv)
- **ChromaDB** — local vector store with ONNX embeddings
- **python-frontmatter** — YAML + markdown parsing
- **Claude Code** — compilation intelligence (slash commands)
- **anthropic SDK** — optional, for automated batch compilation via `src/compiler/batch.py`

## License

Application code: MIT. Law texts in submodules are public domain (official government publications). See each submodule for its own license terms.
