One-time project setup. Picks the output language for compiled notes and `/qa` answers.

## Step 1 — Show current language

```bash
uv run python -m src.config get_language
```

## Step 2 — Ask the user which language they prefer

Offer this curated list and ask the user to pick one (or type a custom BCP-47 code):

| Code | Language   |
|------|------------|
| `en` | English    |
| `es` | Spanish    |
| `ca` | Catalan    |
| `fr` | French     |
| `it` | Italian    |
| `de` | German     |
| `pt` | Portuguese |

If the user passed the code directly as `$ARGUMENTS` (e.g. `/setup es`), use that and skip the prompt.

## Step 3 — Persist the choice

```bash
uv run python -m src.config set_language <code>
```

This writes `env.OUTPUT_LANGUAGE` into `.claude/settings.json`. The value is shared across the repo (any collaborator cloning the project inherits it, but each can override locally via `.claude/settings.local.json`).

## Step 4 — Confirm and point to next steps

Print a short confirmation including the language name, then tell the user:

- Existing compiled notes in `knowledge/laws/` are NOT retroactively translated. Run `/compile <jurisdiction> --force` if you want to re-localize them.
- New `/compile` and `/qa` runs will honor the chosen language immediately. No restart needed.
- Suggested next step: `/compile es-ct --limit 10` (or any jurisdiction).

## Notes

- `OUTPUT_LANGUAGE` is exposed as a shell env var in every session because it lives under `.claude/settings.json → env`. Python reads it via `src.config.get_language()`; Claude Code surfaces it to Bash.
- A language override in the parent shell (`OUTPUT_LANGUAGE=fr claude .`) takes precedence over the file value for that session only.
