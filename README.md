<div align="center">

<img src="docs/logo.svg?v=2" alt="Your AI Lawyer" width="420"/>

</div>

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

<div align="center">

![Knowledge graph — 10 compiled Cataluña laws and their concept nodes in Obsidian](docs/knowledge-graph.png)

*Obsidian graph view of the first 10 compiled Cataluña laws (`BOE-A-*` nodes) and their shared concept index files.*

</div>

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

All country data comes from the [legalize-dev](https://github.com/legalize-dev) organization — each repo is a country's legislation as Markdown files with git history.

### Step 1 — Add the submodule

Replace `XX` with the country code (e.g. `fr`, `de`, `us`):

```bash
git submodule add https://github.com/legalize-dev/legalize-XX.git legalize-XX
git submodule update --init legalize-XX
```

### Step 2 — Compile in Claude Code

```bash
claude .
```

Then run:

```bash
/compile XX --limit 20    # test run — first 20 laws
/compile XX               # full run (use --limit N and repeat in batches for large countries)
```

### Step 3 — Build the search index

```bash
/index --country XX
```

### Step 4 — Query

```bash
/qa What are the employment rights in France?
/search data protection --country fr
```

### Tips for large countries

The US (`legalize-us`) has 60,000+ sections and Portugal (`legalize-pt`) has 109,000+ norms. Compile in batches by rank:

```bash
/compile us --rank statute --limit 50
/compile pt --rank lei --limit 50
```

Check progress between runs:

```bash
uv run python -m src.compiler.tracker status --jurisdiction us
```

---

## Available Countries

All 28 countries are available from [github.com/legalize-dev](https://github.com/legalize-dev). Add any as a submodule using the instructions above.

| Country | Code | Submodule | Laws | Source |
|---------|------|-----------|------|--------|
| 🇦🇩 Andorra | `ad` | `legalize-ad` | — | BOPA |
| 🇦🇷 Argentina | `ar` | `legalize-ar` | — | Infoleg |
| 🇦🇹 Austria | `at` | `legalize-at` | — | RIS |
| 🇧🇪 Belgium | `be` | `legalize-be` | — | Justel |
| 🇨🇱 Chile | `cl` | `legalize-cl` | — | BCN / Ley Chile |
| 🇨🇿 Czech Republic | `cz` | `legalize-cz` | — | ⚠️ Under development |
| 🇩🇰 Denmark | `dk` | `legalize-dk` | — | retsinformation.dk |
| 🇪🇪 Estonia | `ee` | `legalize-ee` | — | Riigi Teataja |
| 🇫🇮 Finland | `fi` | `legalize-fi` | — | Finlex |
| 🇫🇷 France | `fr` | `legalize-fr` | — | Légifrance |
| 🇩🇪 Germany | `de` | `legalize-de` | — | gesetze-im-internet.de |
| 🇬🇷 Greece | `gr` | `legalize-gr` | — | ΦΕΚ Α' |
| 🇮🇪 Ireland | `ie` | `legalize-ie` | — | legislation.ie |
| 🇮🇹 Italy | `it` | `legalize-it` | — | Normattiva |
| 🇰🇷 South Korea | `kr` | `legalize-kr` | — | 국가법령정보센터 |
| 🇱🇻 Latvia | `lv` | `legalize-lv` | — | likumi.lv |
| 🇱🇹 Lithuania | `lt` | `legalize-lt` | — | TAR / data.gov.lt |
| 🇱🇺 Luxembourg | `lu` | `legalize-lu` | — | legilux.lu |
| 🇳🇱 Netherlands | `nl` | `legalize-nl` | — | Basis Wetten Bestand |
| 🇳🇴 Norway | `no` | `legalize-no` | — | Lovdata (NLOD 2.0) |
| 🇵🇱 Poland | `pl` | `legalize-pl` | — | Sejm / Dziennik Ustaw |
| 🇵🇹 Portugal | `pt` | `legalize-pt` | 109K+ | Diário da República |
| 🇸🇰 Slovakia | `sk` | `legalize-sk` | — | Slov-Lex |
| 🇪🇸 Spain | `es` | `legalize-es` ✅ | 12K+ | BOE |
| 🇸🇪 Sweden | `se` | `legalize-se` | — | riksdagen.se |
| 🇺🇦 Ukraine | `ua` | `legalize-ua` | — | Verkhovna Rada |
| 🇬🇧 United Kingdom | `gb` | — | — | Coming soon |
| 🇺🇸 United States | `us` | `legalize-us` | 60K+ | US Code |
| 🇺🇾 Uruguay | `uy` | `legalize-uy` | — | IMPO |

✅ = already added as submodule · ⚠️ = under active development, structure may change

---

## Contributing

Open an [issue](https://github.com/arnabdeypolimi/your-ai-lawyer/issues) to discuss new country submodules, pipeline improvements, or query enhancements, then submit a PR.

## Acknowledgements

Raw legislation data is provided by [legalize-dev](https://github.com/legalize-dev), an open-source organization that publishes official government law texts as structured Markdown repositories. Each country submodule is maintained independently under its own license — see the respective repo for terms. This project would not be possible without their work of collecting, cleaning, and versioning public-domain legal sources across 28 countries.

## Terms of Use

This project is intended for **personal and non-commercial use only**.

The information compiled by this tool does not constitute legal advice. The maintainer(s) of this project are not lawyers and accept no responsibility or liability for the accuracy, completeness, or fitness for purpose of any compiled output, search result, or answer generated. Always consult a qualified legal professional for advice on your specific situation.

By using this project you agree that:
- You will not use it for commercial purposes without obtaining appropriate licenses for all underlying law texts
- The maintainer(s) are not liable for any damages, losses, or legal consequences arising from reliance on this tool
- Law texts may be outdated, incomplete, or incorrectly compiled — verify against official government sources before acting on any information

## License

MIT. Law texts in submodules are public domain (official government publications). See each submodule for its own license terms.
