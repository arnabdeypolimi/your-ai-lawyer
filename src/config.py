"""Project-level configuration backed by .claude/settings.json.

The output language lives under `env.OUTPUT_LANGUAGE` so it is surfaced as
an environment variable to subprocesses Claude Code spawns, and can be
read uniformly from Python, shell, or Claude prompts.
"""

import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).parents[1]
SETTINGS_PATH = ROOT / ".claude" / "settings.json"

SUPPORTED_LANGUAGES = {
    "en": "English",
    "es": "Spanish",
    "ca": "Catalan",
    "fr": "French",
    "it": "Italian",
    "de": "German",
    "pt": "Portuguese",
}

DEFAULT_LANGUAGE = "en"


def _load() -> dict:
    if SETTINGS_PATH.exists():
        return json.loads(SETTINGS_PATH.read_text())
    return {}


def _save(data: dict) -> None:
    SETTINGS_PATH.write_text(json.dumps(data, indent=2) + "\n")


def get_language() -> str:
    """Return the configured output language code.

    Precedence: process env `OUTPUT_LANGUAGE` → settings.json `env.OUTPUT_LANGUAGE` → default `en`.
    """
    env_override = os.environ.get("OUTPUT_LANGUAGE")
    if env_override:
        return env_override
    data = _load()
    return data.get("env", {}).get("OUTPUT_LANGUAGE", DEFAULT_LANGUAGE)


def language_name(code: str | None = None) -> str:
    """Human-readable name for a language code, falling back to the code itself."""
    code = code or get_language()
    return SUPPORTED_LANGUAGES.get(code, code)


def set_language(code: str) -> None:
    """Write output language to settings.json, preserving other keys."""
    data = _load()
    env = data.setdefault("env", {})
    env["OUTPUT_LANGUAGE"] = code
    _save(data)


def _cli() -> None:
    if len(sys.argv) < 2:
        print("usage: python -m src.config {get_language|set_language <code>}", file=sys.stderr)
        sys.exit(2)

    cmd = sys.argv[1]
    if cmd == "get_language":
        print(get_language())
    elif cmd == "set_language":
        if len(sys.argv) < 3:
            print("error: set_language requires a language code", file=sys.stderr)
            sys.exit(2)
        code = sys.argv[2].strip().lower()
        set_language(code)
        print(f"output_language = {code} ({language_name(code)})")
    else:
        print(f"unknown command: {cmd}", file=sys.stderr)
        sys.exit(2)


if __name__ == "__main__":
    _cli()
