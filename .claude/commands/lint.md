Check the legal knowledge base for health issues.

Run the lint script:

```bash
uv run python -m src.compiler.lint $ARGUMENTS
```

Optional flags:
- `--jurisdiction es-ct` — scope checks to a specific jurisdiction
- `--broken-links` — also scan compiled notes for wikilinks pointing to non-existent notes (slower)

## What it checks

| Check | Meaning |
|-------|---------|
| Compilation errors | Laws in `index.json` with `status: error` — need to be retried with `/compile --force` |
| Missing note files | `index.json` says compiled but the `.md` file is gone from `knowledge/laws/` |
| Orphaned notes | Compiled note exists but its raw source file has been deleted or moved |
| Untracked notes | `.md` file exists in `knowledge/laws/` but has no entry in `index.json` — run `tracker mark` to fix |
| Never compiled | Raw law files that have never been processed — not an error, just informational |
| Concept orphans | Files in `knowledge/concepts/` that no compiled note links to — safe to delete |
| Broken wikilinks | `[[BOE-A-...]]` references in compiled notes pointing to laws not yet compiled (opt-in) |

## After linting

- **Errors** → `/compile --force --rank <rank>` to retry failed files
- **Missing notes** → `/compile --force` to regenerate
- **Untracked notes** → run `uv run python -m src.compiler.tracker mark <id> <raw> <note> <jur> <rank>` for each
- **Never compiled** → `/compile <jurisdiction> --limit N` to process in batches
- **Broken wikilinks** → compile the missing laws, or they will resolve automatically as more laws are compiled
