Review a contract PDF against the legal knowledge base and write an annotated copy. No API key required.

Usage: `/review-contract <path-to-pdf> [--country <code>] [--force]`

`$ARGUMENTS` holds the path and the flags. The path may contain spaces: everything before the first `--` flag is the path. Always quote it in shell commands.

For a contract at `<dir>/<stem>.pdf` the review data lives in `<dir>/<stem>.review/` and the annotated copy is `<dir>/<stem>.reviewed.pdf`. Never modify the contract itself.

## Step 1 — Is there already a review?

```bash
uv run python -m src.contract.extract "<pdf>" --status
```

- If the command exits with an error (for example `File not found`), relay the message and stop.
- `reviewed` and no `--force`: tell the user a review already exists, give the path of `<stem>.reviewed.pdf`, mention `/contract-qa` for questions and `--force` to redo it, and stop.
- `no-review`, `changed`, or `--force`: continue.

## Step 2 — Read the contract into passages

```bash
uv run python -m src.contract.extract "<pdf>"
```

If it exits with an error, relay the message and stop. Otherwise note the passage count and any skipped pages.

## Step 3 — Output language

```bash
uv run python -m src.config get_language
```

## Step 4 — Understand the contract

Read `<dir>/<stem>.review/passages.txt` from start to finish. If it is long, read it in several parts; do not skip any.

Work out:
- the contract type (lease, employment, services, sale, ...);
- which country's law governs it: `--country` if given, otherwise the governing-law clause or the parties' addresses, otherwise unknown;
- the region, if the contract is tied to one.

Search can only filter by top-level country. If `--country` is a region code such as `es-ct`, search with its country (`--country es`) and keep the region as context. If the country is unknown, search without `--country` and say so in the summary.

## Step 5 — Check every clause against the laws

Go through **all** passages in order. Skip headings, party details and signatures; review every passage that creates an obligation, a right, a deadline, a price, a penalty, a waiver or a termination rule.

For each legal point, run one to three searches:

```bash
uv run python -m src.query.search "<query>" --country <cc> --n 8
```

- Write the query **in the language of the laws** (Spanish for `es`), using the legal terms a statute would use. The local search matches poorly across languages.
- If the search says the index was not found, tell the user to run `/index` and stop.
- For each promising result, read the source before judging. A result whose `Source:` is a raw law file (under `legalize-*/`) is a piece of the law's text: open that file, find the passage, and read the whole article it belongs to, noting the number in its `Artículo N` heading. Most results show only `[BOE-...]` with no article number, so the heading in the file is where the number comes from. A result whose `Source:` is under `knowledge/laws/` is a compiled note: read the note, and if the raw file named in its Source section exists, read the relevant articles there.
- Note each result's jurisdiction and status. A regional law applies only if the contract is tied to that region.

If you have to stop before the last passage, record the passages you did not reach in `unreviewed`. Never present a partial review as complete.

## Step 6 — Write the findings

Write `<dir>/<stem>.review/findings.json`:

```json
{
  "language": "<output language code>",
  "country": "<top-level country code, or null>",
  "contract_type": "residential lease",
  "summary": "Two to four sentences.",
  "findings": [
    {
      "passage": 14,
      "quote": "the offending words, copied exactly from that passage, or null",
      "confidence": "high",
      "issue": "Short title",
      "comment": "What the clause says, what the law says, why they conflict.",
      "citations": [{"identifier": "BOE-A-1994-26003", "article": "36", "title": "Ley 29/1994 ..."}]
    }
  ],
  "omissions": [
    {"issue": "Short title", "comment": "What the law requires that the contract lacks.", "citations": [{"identifier": "BOE-A-...", "article": "..."}]}
  ],
  "not_covered": ["Non-compete clause (passage 22): no relevant law in the knowledge base"],
  "unreviewed": []
}
```

All top-level keys are required; the four lists may be empty.

Confidence is how sure you are that the clause conflicts with the cited law:
- `high` — the clause contradicts the cited article as written. Needs a citation with an `article`.
- `medium` — it probably conflicts, but that depends on facts or interpretation the contract does not settle; or the cited law's status is not `in_force`; or you only have the law-level summary, not the article.
- `low` — worth a second look; the law you found is only loosely on point.

Rules:
1. Cite only laws you retrieved and read in this run. Nothing from memory. Every identifier is checked against the index and an unknown one is rejected.
2. Write `article` as the number printed in the law's own heading (`Artículo 9 bis.` -> `"9 bis"`). Leave `article` out when you only have the compiled note. The article is checked against the law's text, and one that is not there is rejected.
3. If the knowledge base has nothing on a point, do not guess: add it to `not_covered`. If no search returned anything useful at all, open the `summary` by saying the knowledge base did not cover this contract.
4. A law whose status is not `in_force` caps the finding at `medium`, and the comment says the law may be repealed or superseded.
5. Say whether a cited law is national or regional when it matters.
6. Things the law requires that the contract lacks go in `omissions`, each with a citation.
7. `quote` is copied character for character from the passage text, and is short: the sentence or phrase that is the problem. Use null to mark the whole passage.
8. Write `issue`, `comment`, `summary`, `omissions`, `not_covered` and `unreviewed` in the output language from Step 3. Identifiers and article numbers stay as they are.
9. Do not highlight clauses that are fine.

## Step 7 — Validate, then write the PDF

```bash
uv run python -m src.contract.annotate "<pdf>" --check
```

If it lists problems, fix `findings.json` and run it again until it passes. Fix a rejected citation by citing what you actually read, lowering the confidence, or moving the point to `not_covered`; never by inventing an identifier. Then:

```bash
uv run python -m src.contract.annotate "<pdf>"
```

## Step 8 — Report

In the output language, tell the user:
- the path of the annotated PDF;
- a table of findings: page, passage, confidence, issue, citation as **[BOE-A-XXXX-XXXXX, Art. N]**;
- the omissions;
- what the knowledge base did not cover, passages not reviewed, and pages skipped;
- how many highlights sit on the exact sentence and how many cover the whole passage;
- that this is an automated review against the laws in this knowledge base, not legal advice;
- that they can ask follow-up questions now, or later with `/contract-qa <pdf> <question>`.
