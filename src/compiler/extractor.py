"""Extract structured knowledge from a law document using the Claude API."""

import json
import os

import anthropic

from .parser import LawDocument

_client: anthropic.Anthropic | None = None


def _get_client() -> anthropic.Anthropic:
    global _client
    if _client is None:
        _client = anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])
    return _client


_SYSTEM_PROMPT = """\
You are a legal knowledge extraction assistant. Given the full text of a law document, \
extract structured information in JSON. Return ONLY valid JSON, no markdown fences.

The JSON must have these fields:
{
  "summary": "2-3 sentence plain-language summary of what this law does",
  "key_provisions": ["list of the most important rights, obligations, or rules (max 8, each ≤ 15 words)"],
  "concepts": ["list of 3-8 legal concept tags, lowercase hyphenated, e.g. 'tenant-rights', 'data-protection'"],
  "cross_references": ["list of BOE identifiers or other law identifiers explicitly mentioned, e.g. 'BOE-A-1978-31229'"],
  "supersedes": ["identifiers this law explicitly replaces or repeals"],
  "implements": ["identifiers this law implements or develops (e.g. an EU directive number or constitution article)"]
}

Keep concepts concise and reusable across laws. Cross-references should only include \
explicitly cited identifiers, not inferred ones.\
"""


def extract(doc: LawDocument) -> dict:
    """Call Claude API to extract structured knowledge from a law document."""
    client = _get_client()

    # Build a focused excerpt: first 6000 chars of body (covers most short laws fully,
    # and for long laws covers the preamble + early articles which carry most semantic weight)
    body_excerpt = doc.body[:6000]
    if len(doc.body) > 6000:
        body_excerpt += "\n\n[... text truncated for extraction ...]"

    law_text = (
        f"IDENTIFIER: {doc.identifier}\n"
        f"TITLE: {doc.title}\n"
        f"RANK: {doc.rank}\n"
        f"COUNTRY: {doc.country}\n"
        f"JURISDICTION: {doc.jurisdiction}\n"
        f"STATUS: {doc.status}\n"
        f"PUBLICATION DATE: {doc.publication_date}\n\n"
        f"{body_excerpt}"
    )

    response = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=1024,
        system=[
            {
                "type": "text",
                "text": _SYSTEM_PROMPT,
                "cache_control": {"type": "ephemeral"},
            }
        ],
        messages=[{"role": "user", "content": law_text}],
    )

    raw = response.content[0].text.strip()
    # Strip accidental markdown fences
    if raw.startswith("```"):
        raw = raw.split("\n", 1)[1]
        raw = raw.rsplit("```", 1)[0]

    return json.loads(raw)
