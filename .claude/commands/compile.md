Compile raw law files into the knowledge graph. You (Claude Code) read each law and write the compiled note — no external API needed.

## Parse arguments from: $ARGUMENTS
- First token is the jurisdiction: `es` (all Spain), `es-ct` (Cataluña), `es-md` (Madrid), `es-pv` (País Vasco), etc.
- Optional: `--limit N` (default 10 per run to avoid context overflow)
- Optional: `--force` (recompile already-compiled files)
- Optional: `--rank <rank>` (filter by legal rank, e.g. `ley`, `constitucion`)

## Step 1 — Get the file list

```bash
uv run python -m src.compiler.list_files <jurisdiction> [--limit N] [--force] [--rank R]
```

This outputs a JSON array. Each object has: `path`, `identifier`, `title`, `rank`, `jurisdiction`, `country`, `status`, `publication_date`, `source`, `article_count`.

`list_files` already excludes any file whose MD5 matches `data/manifest.json` AND is marked `status: compiled` in `data/index.json` — so already-compiled, unchanged files are never returned here.

If the array is empty, report "Nothing to compile — all files are up to date."

**Compile guarantee**: NEVER read or recompile a file that does not appear in this list. NEVER bypass this filter. If the user wants to recompile already-compiled files, they must pass `--force` explicitly.

## Step 2 — For each file in the list

Use the Read tool to read the file at `path`. Then generate a compiled note with this exact structure:

```markdown
---
identifier: <identifier>
title: "<title>"
country: <country>
jurisdiction: <jurisdiction>
rank: <rank>
status: <status>
publication_date: <publication_date>
last_updated: <last_updated from frontmatter>
source: <source>
compiled_at: <today's date YYYY-MM-DD>
---

# <title>

## Summary
<2-3 sentence plain-language summary of what this law establishes, who it affects, and its main purpose>

## Key Provisions
- <most important right, obligation, or rule — max 12 words>
- <repeat for up to 8 provisions>

## Cross-References
- [[<identifier of explicitly cited law>]]
(only include identifiers explicitly named in the text — omit if none)

## Supersedes
- [[<identifier>]]
(only if this law explicitly repeals or replaces another — omit if none)

## Implements
- [[<identifier or directive number>]]
(only if this law explicitly implements another — omit if none)

## Concepts
[[<concept-slug>]] · [[<concept-slug>]] · [[<concept-slug>]]
(3–8 lowercase hyphenated tags, e.g. tenant-rights, data-protection, criminal-procedure)

## Source
Raw text: `<relative path from project root>`
```

Write the note to: `knowledge/laws/<country>/<identifier>.md`

## Step 3 — Update concept backlinks

For each concept tag in the note's Concepts section:
- Concept file path: `knowledge/concepts/<concept-slug>.md`
- If the file does NOT exist, create it:
  ```
  # <concept slug with hyphens replaced by spaces>

  ## Laws
  - [[<identifier>]] — <title (max 60 chars)>
  ```
- If it EXISTS, read it and append the backlink only if `<identifier>` is not already present:
  ```
  - [[<identifier>]] — <title (max 60 chars)>
  ```

## Step 4 — Track each compiled file

After writing each note, run:

```bash
uv run python -m src.compiler.tracker mark <identifier> <raw_path> <note_path> <jurisdiction> <rank>
```

If reading or writing a file fails, run instead:

```bash
uv run python -m src.compiler.tracker error <identifier> <raw_path> <jurisdiction> <rank> "<error message>"
```

## Step 5 — Generate jurisdiction overview

After all files are processed:

```bash
uv run python -m src.compiler.jurisdictions <country_prefix>
```

where `country_prefix` is the first part of the jurisdiction (e.g. `es` for `es-ct`).

## Step 6 — Report

Show a summary:
- Files compiled (with identifiers)
- Files skipped or errored
- Run: `uv run python -m src.compiler.tracker status --jurisdiction <jurisdiction>` and display the output
