Answer a legal question using the compiled knowledge base. No API key required.

## Step 1 — Semantic search

```bash
uv run python -m src.query.search "$ARGUMENTS" --n 8
```

If the index is empty (no results or error), tell the user to run `/index` first.

Optional filters the user can include in their question:
- "in Spain" → append `--country es`
- "in Cataluña" or "es-ct" → append `--country es`
- "only leyes" → append `--rank ley`

## Step 2 — Read top compiled notes

For each result that has a `source_path` pointing to a `knowledge/laws/` file, use the Read tool to read that compiled note to get the full context (not just the search snippet).

## Step 3 — Answer with citations

First, determine the user's preferred output language:

```bash
uv run python -m src.config get_language
```

Answer the question based on the retrieved content. Rules:
0. Write the answer prose in the configured language (e.g. Spanish if `es`, Catalan if `ca`). Inline citations like **[BOE-A-XXXX-XXXXX, Art. N]** and identifiers stay unchanged regardless of language.
1. Cite every claim inline as **[BOE-A-XXXX-XXXXX, Art. N]** or just **[BOE-A-XXXX-XXXXX]** if no specific article
2. Distinguish national law from regional/autonomous community law when relevant
3. If a law's `status` is not `in_force`, note that it may be repealed or superseded
4. If the knowledge base lacks sufficient information to answer confidently, say so — do not speculate
5. End with a **Sources** section listing all cited identifiers and their titles
