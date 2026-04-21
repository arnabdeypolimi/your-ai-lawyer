# Your AI Lawyer

<div align="center">

[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](https://opensource.org/licenses/MIT)
[![Python 3.12+](https://img.shields.io/badge/Python-3.12+-blue)](https://www.python.org/downloads/)
[![uv](https://img.shields.io/badge/managed%20with-uv-blueviolet)](https://github.com/astral-sh/uv)
[![Claude Code](https://img.shields.io/badge/interface-Claude%20Code-orange)](https://claude.ai/code)

**Multi-country legal knowledge base — raw legislation compiled into a queryable knowledge graph via Claude Code slash commands**

[Slash Commands](#slash-commands) • [Architecture](#architecture) • [Adding Countries](#adding-a-new-country) • [Tracking](#tracking) • [Issues](https://github.com/arnabdeypolimi/your-ai-lawyer/issues)

</div>

---

Raw country laws live in git submodules. Claude Code reads each law file directly and compiles it into an Obsidian-compatible knowledge graph with summaries, wikilinks, concept indexes, and cross-references — no external API key required. A local ChromaDB vector store powers semantic search and RAG-based Q&A with inline citations to original law text.

---

## Why Your AI Lawyer?

| Feature | This project | LexisNexis | Westlaw | GPT-4 |
|---------|:-----------:|:----------:|:-------:|:-----:|
| Open source | ✅ | ❌ | ❌ | ❌ |
| No API key to query | ✅ | ❌ | ❌ | ❌ |
| Citations to original text | ✅ | ✅ | ✅ | ❌ |
| Region-level granularity | ✅ | ✅ | ✅ | ❌ |
| Obsidian knowledge graph | ✅ | ❌ | ❌ | ❌ |
| Offline vector search | ✅ | ❌ | ❌ | ❌ |
| Pricing | Free OSS | $$$+ | $$$+ | Usage-based |

---

## Features

- Compile any country or region in isolation — `/compile es-ct` for Cataluña only, `/compile es` for all Spain
- Knowledge graph output is valid Obsidian markdown with `[[wikilinks]]`, concept nodes, and cross-references
- Two-collection ChromaDB index (compiled summaries + raw article chunks) for high-precision retrieval
- Manifest + index tracking — recompilation skips unchanged files; `index.json` and `compile.log` record every run
- `/lint` checks for compilation errors, orphaned notes, broken wikilinks, and untracked files
- `/qa` answers questions with inline citations (`[BOE-A-XXXX-XXXXX, Art. N]`) — no API key needed
- Extensible to any country: add a submodule, run `/compile`, done

---

## Quick Start

### Install

```bash
git clone --recurse-submodules https://github.com/arnabdeypolimi/your-ai-lawyer.git
cd your-ai-lawyer
uv sync
```

Requires [uv](https://github.com/astral-sh/uv) and [Claude Code](https://claude.ai/code).

### Open in Claude Code

```bash
claude .
```

### Compile laws

```bash
/compile es-ct --limit 10       # Cataluña — first 10 laws (test run)
/compile es --rank constitucion  # Spain — constitutional laws only
/compile es                      # Spain — all 12,000+ laws (run in batches)
```

### Build the search index

```bash
/index                           # index Spain (default)
/index --country es --compiled-only
```

### Query

```bash
/qa What are the housing rights of tenants in Spain?
/qa Does Cataluña have its own data protection laws?
/search right to education --country es --n 10
```

### Check health

```bash
/lint                            # full health check
/lint --jurisdiction es-ct       # scoped to Cataluña
/lint --broken-links             # also scan for broken wikilinks (slower)
```

---

## Slash Commands

| Command | Description |
|---------|-------------|
| `/compile <jurisdiction> [--limit N] [--rank R] [--force]` | Compile raw laws into knowledge graph |
| `/index [--country X] [--compiled-only] [--raw-only]` | Build / update ChromaDB vector index |
| `/search <query> [--country X] [--rank R] [--n N]` | Semantic search with ranked results |
| `/qa <question>` | RAG answer with inline citations |
| `/lint [--jurisdiction X] [--broken-links]` | Health check on knowledge base |

Supported jurisdictions for Spain: `es` (national), `es-ct`, `es-md`, `es-an`, `es-pv`, `es-ga`, `es-vc`, `es-ib`, `es-ar`, `es-cn`, `es-cl`, `es-cm`, `es-cb`, `es-as`, `es-ri`, `es-nc`, `es-mc`.

---

## Architecture

```
your-ai-lawyer/
├── legalize-es/              # Spain raw laws (git submodule, 12K+ files)
├── knowledge/                # Compiled Obsidian vault
│   ├── laws/es/              # One .md per law: summary, provisions, wikilinks
│   ├── concepts/             # Concept index files with backlinks
│   └── jurisdictions/        # Per-country overview notes
├── data/
│   ├── index.json            # Per-law compilation status
│   ├── compile.log           # Run history (NDJSON)
│   ├── manifest.json         # MD5 hashes for change detection
│   └── chroma/               # ChromaDB vector store (gitignored)
└── src/
    ├── compiler/             # parser, extractor, batch, tracker, lint
    ├── indexer/              # ChromaDB embedding pipeline
    └── query/                # Semantic search
```

### Compilation pipeline

```
legalize-<country>/
  raw markdown + YAML frontmatter
          │
          ▼  /compile (Claude Code reads + writes directly)
          │   list_files.py  →  lists files needing compilation
          │   tracker.py     →  records result in index.json + compile.log
          │
knowledge/laws/<country>/
  compiled notes with [[wikilinks]]
          │
          ▼  /index (local ONNX embeddings — no API key)
          │
data/chroma/
  compiled collection + raw_chunks collection
          │
          ▼  /qa or /search
  citations: [BOE-A-XXXX-XXXXX, Art. N]
```

### Compiled note format

Each `knowledge/laws/es/<identifier>.md` contains:

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

Followed by: **Summary**, **Key Provisions**, **Cross-References** (`[[wikilinks]]`), **Supersedes**, **Implements**, **Concepts**, and a link back to the raw source file. The `knowledge/` folder is a valid Obsidian vault.

---

## Tracking

Three files in `data/` track compilation state:

| File | Contents |
|------|---------|
| `manifest.json` | `{ raw_path: md5_hash }` — skips unchanged files on recompile |
| `index.json` | Per-law record: `status`, `compiled_at`, `note_path`, `error` |
| `compile.log` | NDJSON run history: timestamp, jurisdiction, counts, error IDs |

Check status directly:

```bash
uv run python -m src.compiler.tracker status
uv run python -m src.compiler.tracker status --jurisdiction es-ct
uv run python -m src.compiler.tracker log --n 20
```

---

## Adding a New Country

```bash
# 1. Add the submodule
git submodule add <legalize-XX-url> legalize-XX
git submodule update --init legalize-XX

# 2. Compile in Claude Code
/compile XX --limit 20    # test run first
/compile XX               # full run in batches

# 3. Build the index
/index --country XX
```

---

## Country Coverage

| Submodule | Coverage | Source |
|-----------|----------|--------|
| `legalize-es` | Spain — 8,600+ national laws + 17 autonomous communities | [legalize.dev](https://legalize.dev) |

---

## Contributing

Open an [issue](https://github.com/arnabdeypolimi/your-ai-lawyer/issues) to discuss new country submodules, pipeline improvements, or query enhancements, then submit a PR.

## License

MIT. Law texts in submodules are public domain (official government publications). See each submodule for its own license terms.
