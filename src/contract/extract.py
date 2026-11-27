"""Split a contract PDF into numbered passages with PDF-space coordinates."""

import argparse
import json
import re
import sys
from pathlib import Path

import pdfplumber
import pypdf
from rich.console import Console

from src.contract.paths import file_md5, resolve_pdf, review_dir, reviewed_pdf

MAX_PASSAGE_CHARS = 1200
SKIP_REASONS = {"no_text": "no extractable text", "rotated": "rotated page"}

_LINE_TOP_TOLERANCE = 3
_GAP_RATIO = 0.8
_WIDE_GAP_FACTOR = 1.5
_MIN_GAP_FACTOR = 0.5
_FONT_CHANGE_RATIO = 0.2
_CLAUSE_RE = re.compile(r"^\d+(\.\d+)*[.)]\s")
_SENTENCE_END_RE = re.compile(r"[.:;?!]$")

console = Console()


class ExtractError(Exception):
    pass


def _round(value: float) -> float:
    return round(value, 2)


def _page_words(page) -> list[dict]:
    words = []
    for w in page.extract_words():
        words.append({
            "text": w["text"],
            "x0": _round(w["x0"]),
            "x1": _round(w["x1"]),
            "y0": _round(page.height - w["bottom"]),
            "y1": _round(page.height - w["top"]),
        })
    return words


def _group_lines(words: list[dict]) -> list[list[dict]]:
    lines = []
    for word in words:
        if lines and abs(lines[-1][0]["y1"] - word["y1"]) < _LINE_TOP_TOLERANCE:
            lines[-1].append(word)
        else:
            lines.append([word])
    return lines


def _line_text(line: list[dict]) -> str:
    return " ".join(w["text"] for w in line)


def _line_box(line: list[dict]) -> tuple[float, float]:
    return min(w["y0"] for w in line), max(w["y1"] for w in line)


def _passage(page_no: int, passage_lines: list[list[dict]]) -> dict:
    words = []
    for line_no, line in enumerate(passage_lines):
        for w in line:
            words.append({**w, "line": line_no})
    return {
        "id": 0,
        "page": page_no,
        "text": " ".join(_line_text(line) for line in passage_lines),
        "bbox": [
            _round(min(w["x0"] for w in words)),
            _round(min(w["y0"] for w in words)),
            _round(max(w["x1"] for w in words)),
            _round(max(w["y1"] for w in words)),
        ],
        "words": words,
    }


def _base_gap(lines: list[list[dict]]) -> float:
    gaps = []
    for prev, line in zip(lines, lines[1:]):
        prev_y0, _ = _line_box(prev)
        _, y1 = _line_box(line)
        if prev_y0 - y1 > 0:
            gaps.append(prev_y0 - y1)
    return sorted(gaps)[len(gaps) // 4] if len(gaps) >= 3 else 0


def _split_passages(page_no: int, lines: list[list[dict]]) -> list[dict]:
    passages, current = [], []
    base_gap = _base_gap(lines)
    for line in lines:
        text = _line_text(line)
        if current:
            prev_y0, prev_y1 = _line_box(current[-1])
            prev_height = max(prev_y1 - prev_y0, 1)
            y0, y1 = _line_box(line)
            height = y1 - y0
            gap = prev_y0 - y1
            candidate = " ".join(map(_line_text, [*current, line]))
            starts_new = (
                gap > max(_WIDE_GAP_FACTOR * base_gap, _MIN_GAP_FACTOR * prev_height)
                or (gap > _GAP_RATIO * prev_height and _SENTENCE_END_RE.search(_line_text(current[-1])))
                or abs(height - prev_height) > _FONT_CHANGE_RATIO * max(height, prev_height)
                or _CLAUSE_RE.match(text)
                or len(candidate) > MAX_PASSAGE_CHARS
            )
        else:
            starts_new = True
        if starts_new:
            if current:
                passages.append(_passage(page_no, current))
            current = [line]
        else:
            current.append(line)
    if current:
        passages.append(_passage(page_no, current))
    return passages


def extract(pdf: Path) -> dict:
    pdf = Path(pdf)
    if not pdf.exists():
        raise ExtractError(f"File not found: {pdf}")
    if not pdf.is_file():
        raise ExtractError(f"Not a PDF: {pdf}")
    try:
        reader = pypdf.PdfReader(str(pdf))
    except (pypdf.errors.PyPdfError, OSError):
        raise ExtractError(f"Not a PDF: {pdf}")
    if reader.is_encrypted:
        raise ExtractError(f"Encrypted PDF is not supported: {pdf}")

    passages, skipped = [], []
    with pdfplumber.open(str(pdf)) as doc:
        for page_no, page in enumerate(doc.pages, start=1):
            if (page.rotation or 0) != 0:
                skipped.append({"page": page_no, "reason": "rotated"})
                continue
            words = _page_words(page)
            if not words:
                skipped.append({"page": page_no, "reason": "no_text"})
                continue
            passages.extend(_split_passages(page_no, _group_lines(words)))
        page_count = len(doc.pages)

    if not passages:
        raise ExtractError(
            f"No extractable text in {pdf}: it looks like a scanned PDF; OCR is not supported."
        )
    for i, passage in enumerate(passages, start=1):
        passage["id"] = i
    return {
        "source": str(pdf.resolve()),
        "source_md5": file_md5(pdf),
        "page_count": page_count,
        "skipped_pages": skipped,
        "passages": passages,
    }


def render_text(doc: dict) -> str:
    lines = [
        f"# Source: {doc['source']}",
        f"# Pages: {doc['page_count']} | Passages: {len(doc['passages'])}",
    ]
    if doc["skipped_pages"]:
        skipped = ", ".join(
            f"{s['page']} ({SKIP_REASONS[s['reason']]})" for s in doc["skipped_pages"]
        )
        lines.append(f"# Skipped pages: {skipped}")
    else:
        lines.append("# Skipped pages: none")
    body = "\n\n".join(
        f"[{p['id']}] (p.{p['page']}) {p['text']}" for p in doc["passages"]
    )
    return "\n".join(lines) + "\n\n" + body + "\n"


def _load_passages_doc(json_path: Path) -> dict | None:
    try:
        data = json.loads(json_path.read_text())
    except (OSError, ValueError):
        return None
    return data if isinstance(data, dict) else None


def _stored_md5(json_path: Path) -> str | None:
    doc = _load_passages_doc(json_path)
    md5 = doc.get("source_md5") if doc else None
    return md5 if isinstance(md5, str) else None


def write_outputs(pdf: Path, doc: dict) -> tuple[Path, Path]:
    out_dir = review_dir(Path(pdf))
    json_path = out_dir / "passages.json"
    txt_path = out_dir / "passages.txt"
    findings = out_dir / "findings.json"
    old = _load_passages_doc(json_path)
    old_passages = old.get("passages") if old else None
    same = (
        isinstance(old_passages, list)
        and old.get("source_md5") == doc["source_md5"]
        and [(p.get("id"), p.get("text")) for p in old_passages]
        == [(p["id"], p["text"]) for p in doc["passages"]]
    )
    if findings.exists() and not same:
        findings.unlink()
        console.print(
            "Removed stale findings.json (the contract or its passages changed).",
            markup=False, highlight=False, soft_wrap=True,
        )
    out_dir.mkdir(parents=True, exist_ok=True)
    json_path.write_text(json.dumps(doc, indent=2, ensure_ascii=False))
    txt_path.write_text(render_text(doc))
    return json_path, txt_path


def review_status(pdf: Path) -> str:
    pdf = Path(pdf)
    if not pdf.exists():
        raise ExtractError(f"File not found: {pdf}")
    findings = review_dir(pdf) / "findings.json"
    if not findings.exists():
        return "no-review"
    if _stored_md5(review_dir(pdf) / "passages.json") != file_md5(pdf):
        return "changed"
    out = reviewed_pdf(pdf)
    if not out.exists() or out.stat().st_mtime < findings.stat().st_mtime:
        return "incomplete"
    return "reviewed"


def main() -> None:
    parser = argparse.ArgumentParser(prog="extract")
    parser.add_argument("pdf")
    parser.add_argument("--status", action="store_true")
    args = parser.parse_args()

    pdf = resolve_pdf(args.pdf)
    try:
        if args.status:
            console.print(review_status(pdf))
            return
        doc = extract(pdf)
    except ExtractError as exc:
        console.print(str(exc), style="red", markup=False, highlight=False, soft_wrap=True)
        sys.exit(1)
    json_path, txt_path = write_outputs(pdf, doc)
    console.print(
        f"Passages: {len(doc['passages'])} "
        f"(pages: {doc['page_count']}, skipped: {len(doc['skipped_pages'])})"
    )
    for skipped in doc["skipped_pages"]:
        console.print(f"Skipped page {skipped['page']}: {SKIP_REASONS[skipped['reason']]}")
    for path in (json_path, txt_path):
        console.print(f"Wrote {path}", markup=False, highlight=False, soft_wrap=True)


if __name__ == "__main__":
    main()
