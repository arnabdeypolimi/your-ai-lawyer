"""Write confidence-coloured highlights and a summary note onto the contract PDF."""

import argparse
import json
import sys
from pathlib import Path

from pypdf import PdfWriter
from pypdf.annotations import Highlight, Text
from pypdf.generic import (
    ArrayObject, DecodedStreamObject, DictionaryObject, FloatObject, NameObject,
    NumberObject, RectangleObject, TextStringObject,
)
from rich.console import Console

from src.contract.extract import SKIP_REASONS
from src.contract.findings import (
    CONFIDENCE_LEVELS, ChromaCitationIndex, FindingsError, format_citation,
    load_review, validate,
)
from src.contract.paths import file_md5, resolve_pdf, review_dir, reviewed_pdf

COLORS = {"high": "ff9a9a", "medium": "ffc266", "low": "fff27a"}
NOTE_COLOR = "4a90d9"
AUTHOR = "Your AI Lawyer"
DISCLAIMER = (
    "Automated review against the laws in this knowledge base. Not legal advice."
)
ZERO_FINDINGS_NOTE = (
    "No highlights does not mean the contract is sound: "
    "only the laws in this knowledge base were checked."
)

console = Console()


def _normalise(text: str) -> str:
    return "".join(c for c in text.casefold() if c.isalnum())


def locate_quote(words: list[dict], quote: str | None) -> list[int] | None:
    if not quote:
        return None
    needle = _normalise(quote)
    if not needle:
        return None
    hay, owner = [], []
    for i, w in enumerate(words):
        for c in _normalise(w["text"]):
            hay.append(c)
            owner.append(i)
    hay = "".join(hay)
    starts = {pos for pos, i in enumerate(owner) if pos == 0 or owner[pos - 1] != i}
    ends = {pos + 1 for pos, i in enumerate(owner) if pos == len(owner) - 1 or owner[pos + 1] != i}
    pos = hay.find(needle)
    while pos >= 0:
        if pos in starts and pos + len(needle) in ends:
            return sorted(set(owner[pos:pos + len(needle)]))
        pos = hay.find(needle, pos + 1)
    return None


def line_rects(words: list[dict]) -> list[tuple[float, float, float, float]]:
    lines: dict[int, list[dict]] = {}
    for w in words:
        lines.setdefault(w["line"], []).append(w)
    return [
        (
            min(w["x0"] for w in ws),
            min(w["y0"] for w in ws),
            max(w["x1"] for w in ws),
            max(w["y1"] for w in ws),
        )
        for ws in lines.values()
    ]


def comment_text(finding: dict) -> str:
    text = f"[{finding['confidence'].upper()}] {finding['issue']}\n{finding['comment']}"
    if finding.get("citations"):
        text += "\nLaw: " + "; ".join(format_citation(c) for c in finding["citations"])
    return text


def summary_text(review: dict, passages_doc: dict) -> str:
    counts = {c: 0 for c in CONFIDENCE_LEVELS}
    for f in review["findings"]:
        counts[f["confidence"]] += 1
    parts = [
        f"Contract review: {review['contract_type']}",
        f"Findings: {counts['high']} high, {counts['medium']} medium, {counts['low']} low",
        *([ZERO_FINDINGS_NOTE] if not review["findings"] else []),
        "Legend: red = high, orange = medium, yellow = low confidence that the clause "
        "conflicts with the cited law.",
        "",
        review["summary"],
    ]
    if review["omissions"]:
        items = []
        for o in review["omissions"]:
            line = f"- {o['issue']}: {o['comment']}"
            if o.get("citations"):
                line += " Law: " + "; ".join(format_citation(c) for c in o["citations"])
            items.append(line)
        parts += ["", "Missing terms:", *items]
    if review["not_covered"]:
        parts += ["", "Not covered by the knowledge base:", *(f"- {s}" for s in review["not_covered"])]
    if review["unreviewed"]:
        parts += ["", "Passages not reviewed:", *(f"- {s}" for s in review["unreviewed"])]
    if passages_doc["skipped_pages"]:
        parts += [
            "",
            "Pages skipped:",
            *(f"- Page {s['page']}: {SKIP_REASONS[s['reason']]}" for s in passages_doc["skipped_pages"]),
        ]
    parts += ["", DISCLAIMER]
    return "\n".join(parts)


def _rgb(color: str) -> tuple[float, float, float]:
    return tuple(int(color[i:i + 2], 16) / 255 for i in (0, 2, 4))


def _union(rects: list[tuple[float, float, float, float]]) -> tuple[float, float, float, float]:
    return (
        min(r[0] for r in rects),
        min(r[1] for r in rects),
        max(r[2] for r in rects),
        max(r[3] for r in rects),
    )


def _appearance(writer: PdfWriter, rects, color: str, multiply: bool) -> DictionaryObject:
    x0, y0, x1, y1 = _union(rects)
    r, g, b = _rgb(color)
    body = ("/GS0 gs " if multiply else "") + f"{r} {g} {b} rg "
    body += "".join(f"{rx0} {ry0} {rx1 - rx0} {ry1 - ry0} re " for rx0, ry0, rx1, ry1 in rects) + "f"
    ap = DecodedStreamObject()
    ap.set_data(body.encode())
    resources = DictionaryObject()
    if multiply:
        resources[NameObject("/ExtGState")] = DictionaryObject({
            NameObject("/GS0"): DictionaryObject({
                NameObject("/Type"): NameObject("/ExtGState"),
                NameObject("/BM"): NameObject("/Multiply"),
            })
        })
    ap.update({
        NameObject("/Type"): NameObject("/XObject"),
        NameObject("/Subtype"): NameObject("/Form"),
        NameObject("/BBox"): RectangleObject((x0, y0, x1, y1)),
        NameObject("/Resources"): resources,
    })
    return DictionaryObject({NameObject("/N"): writer._add_object(ap)})


def _highlight(writer: PdfWriter, rects, contents: str, color: str):
    quads = ArrayObject()
    for x0, y0, x1, y1 in rects:
        for v in (x0, y1, x1, y1, x0, y0, x1, y0):
            quads.append(FloatObject(v))
    ann = Highlight(rect=_union(rects), quad_points=quads, highlight_color=color)
    ann[NameObject("/Contents")] = TextStringObject(contents)
    ann[NameObject("/T")] = TextStringObject(AUTHOR)
    ann[NameObject("/F")] = NumberObject(4)
    ann[NameObject("/C")] = ArrayObject(FloatObject(v) for v in _rgb(color))
    ann[NameObject("/AP")] = _appearance(writer, rects, color, multiply=True)
    return ann


def _summary_note(writer: PdfWriter, text: str, open: bool):
    box = writer.pages[0].cropbox
    right, top = float(box[2]), float(box[3])
    rect = (right - 40, top - 40, right - 20, top - 20)
    ann = Text(text=text, rect=rect, open=open)
    ann[NameObject("/T")] = TextStringObject(AUTHOR)
    ann[NameObject("/F")] = NumberObject(4)
    ann[NameObject("/C")] = ArrayObject(FloatObject(v) for v in _rgb(NOTE_COLOR))
    ann[NameObject("/AP")] = _appearance(writer, [rect], NOTE_COLOR, multiply=False)
    return ann


def annotate(pdf: Path, passages_doc: dict, review: dict, out_path: Path) -> dict:
    writer = PdfWriter(clone_from=str(pdf))
    stats = {**{c: 0 for c in CONFIDENCE_LEVELS}, "exact": 0, "fallback": 0}
    passages = {p["id"]: p for p in passages_doc["passages"]}
    for finding in review["findings"]:
        passage = passages[finding["passage"]]
        hit = locate_quote(passage["words"], finding.get("quote"))
        if hit:
            words = [passage["words"][i] for i in hit]
            stats["exact"] += 1
        else:
            words = passage["words"]
            stats["fallback"] += 1
        stats[finding["confidence"]] += 1
        ann = _highlight(
            writer, line_rects(words), comment_text(finding), COLORS[finding["confidence"]]
        )
        writer.add_annotation(page_number=passage["page"] - 1, annotation=ann)
    writer.add_annotation(
        page_number=0,
        annotation=_summary_note(writer, summary_text(review, passages_doc), not review["findings"]),
    )
    writer.write(str(out_path))
    return stats


def _fail(message: str) -> None:
    console.print(message, style="red", markup=False, highlight=False, soft_wrap=True)
    sys.exit(1)


def main() -> None:
    parser = argparse.ArgumentParser(prog="annotate")
    parser.add_argument("pdf")
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()

    pdf = resolve_pdf(args.pdf)
    if not pdf.exists():
        _fail(f"File not found: {pdf}")
    rdir = review_dir(pdf)
    passages_path = rdir / "passages.json"
    if not passages_path.exists():
        _fail(f"No review data for {pdf}. Run /review-contract first.")
    try:
        doc = json.loads(passages_path.read_text())
    except (OSError, ValueError):
        doc = None
    if (
        not isinstance(doc, dict)
        or not isinstance(doc.get("source_md5"), str)
        or not isinstance(doc.get("passages"), list)
    ):
        _fail(f"Review data for {pdf} is unreadable. Re-run /review-contract.")
    if doc["source_md5"] != file_md5(pdf):
        _fail("The contract changed since it was read; re-run /review-contract.")
    try:
        review = load_review(rdir / "findings.json")
        index = ChromaCitationIndex()
    except FindingsError as exc:
        _fail(str(exc))
    problems = validate(review, {p["id"] for p in doc["passages"]}, index)
    if problems:
        console.print(f"findings.json has {len(problems)} problem(s):", style="red")
        for problem in problems:
            console.print(f"- {problem}", style="red", markup=False, highlight=False, soft_wrap=True)
        sys.exit(1)
    if args.check:
        console.print(f"findings.json is valid: {len(review['findings'])} findings")
        return
    out_path = reviewed_pdf(pdf)
    stats = annotate(pdf, doc, review, out_path)
    console.print(f"Findings: {stats['high']} high, {stats['medium']} medium, {stats['low']} low")
    console.print(f"Placed on the exact sentence: {stats['exact']} | whole passage: {stats['fallback']}")
    console.print(f"Wrote {out_path}", markup=False, highlight=False, soft_wrap=True)


if __name__ == "__main__":
    main()
