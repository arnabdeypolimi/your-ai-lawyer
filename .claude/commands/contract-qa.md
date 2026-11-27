Answer a question about a contract that has already been reviewed with `/review-contract`. No API key required.

Usage: `/contract-qa <path-to-pdf> <question>`

`$ARGUMENTS` starts with the path to the contract PDF (it ends in `.pdf` and may contain spaces); the rest is the question.

## Step 1 — Load the review

```bash
uv run python -m src.contract.extract "<pdf>" --status
```

- If the command exits with an error (for example `File not found`), relay the message and stop.
- `no-review`: tell the user to run `/review-contract "<pdf>"` first, and stop.
- `changed`: tell the user the contract has changed since it was reviewed and to re-run `/review-contract`, and stop.
- `reviewed`: read `<dir>/<stem>.review/passages.txt` and `<dir>/<stem>.review/findings.json`.

## Step 2 — Search the laws

```bash
uv run python -m src.query.search "<query>" --country <cc> --n 8
```

Use the `country` stored in `findings.json` (omit `--country` if it is null). Write the query in the language of the laws. For each relevant result, open its `Source:` file and read the whole article (or the compiled note) before relying on it; take the article number from the `Artículo N` heading in the law's text.

## Step 3 — Answer

Get the output language:

```bash
uv run python -m src.config get_language
```

Answer in that language. Rules:
1. Cite the contract as **[¶14, p.2]** (passage number and page from `passages.txt`).
2. Cite laws as **[BOE-A-XXXX-XXXXX, Art. N]**, or **[BOE-A-XXXX-XXXXX]** when there is no specific article. Cite only what you retrieved and read.
3. Use the existing findings where they bear on the question, and say which finding you are relying on.
4. If a law's status is not `in_force`, say it may be repealed or superseded.
5. If the knowledge base does not cover the question, say so. Do not speculate.
6. End with a **Sources** section listing the cited law identifiers with their titles, and the contract passages used.
7. This is not legal advice; say so in one line.

Do not change `findings.json` or the annotated PDF.
