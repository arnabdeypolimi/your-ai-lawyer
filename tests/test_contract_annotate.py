"""Tests for src/contract/annotate.py."""

import json
import sys

import pypdfium2
import pytest
from pypdf import PdfReader, PdfWriter
from pypdf.annotations import Text
from pypdf.generic import RectangleObject

from conftest import CONTRACT_PAGES, StubIndex, make_review
from pdf_factory import make_pdf
from src.contract import annotate as annotate_module
from src.contract.annotate import (
    DISCLAIMER, ZERO_FINDINGS_NOTE, annotate, line_rects, locate_quote, summary_text,
)
from src.contract.extract import extract, write_outputs
from src.contract.paths import review_dir, reviewed_pdf


def run(pdf, review=None):
    doc = extract(pdf)
    out = reviewed_pdf(pdf)
    stats = annotate(pdf, doc, review or make_review(), out)
    return doc, out, stats


def annots(path, page_index):
    page = PdfReader(str(path)).pages[page_index]
    return [a.get_object() for a in page["/Annots"]] if "/Annots" in page else []


def highlights(path, page_index):
    return [a for a in annots(path, page_index) if a["/Subtype"] == "/Highlight"]


def quads(annot):          # [(x0, y0, x1, y1), ...] from /QuadPoints (8 numbers per rectangle)
    q = [float(v) for v in annot["/QuadPoints"]]
    return [(min(q[i:i + 8:2]), min(q[i + 1:i + 8:2]), max(q[i:i + 8:2]), max(q[i + 1:i + 8:2])) for i in range(0, len(q), 8)]


def pixel(path, page_index, x, y, scale=2):     # x, y in PDF coordinates
    page = pypdfium2.PdfDocument(str(path))[page_index]
    left, bottom, right, top = page.get_mediabox()
    image = page.render(scale=scale).to_pil().convert("RGB")
    return image.getpixel((int((x - left) * scale), int((top - y) * scale)))


def test_locate_quote_spans_a_line_break_hyphen(contract_pdf):
    words = extract(contract_pdf)["passages"][2]["words"]
    hit = locate_quote(words, "fianza de tres mensualidades")
    assert [words[i]["text"] for i in hit] == ["fian-", "za", "de", "tres", "mensualidades"]


def test_locate_quote_ignores_case_and_punctuation(contract_pdf):
    words = extract(contract_pdf)["passages"][2]["words"]
    assert [words[i]["text"] for i in locate_quote(words, "segunda  FIANZA")] == ["SEGUNDA.", "Fianza."]


def _words(text):
    return [{"text": t, "x0": i, "x1": i + 1, "y0": 0, "y1": 1, "line": 0} for i, t in enumerate(text.split())]


def test_locate_quote_respects_word_boundaries():
    words = _words("La renta sera de 1.100 euros y los gastos de 100 euros.")
    assert [words[i]["text"] for i in locate_quote(words, "100 euros")] == ["100", "euros."]
    words = _words("El plazo corre desde tres meses atras, y es de tres meses.")
    assert [words[i]["text"] for i in locate_quote(words, "de tres meses")] == ["de", "tres", "meses."]
    assert locate_quote(_words("Se regula rentas antiguas."), "la renta") is None


def test_locate_quote_takes_first_occurrence_and_handles_misses():
    words = [{"text": t, "x0": i, "x1": i + 1, "y0": 0, "y1": 1, "line": 0} for i, t in enumerate("la renta y la renta".split())]
    assert locate_quote(words, "la renta") == [0, 1]
    assert locate_quote(words, "el precio") is None
    assert locate_quote(words, None) is None
    assert locate_quote(words, " .,- ") is None


def test_counts_and_stats(contract_pdf):
    _, out, stats = run(contract_pdf)
    assert stats == {"high": 1, "medium": 1, "low": 1, "exact": 1, "fallback": 2}
    assert len(highlights(out, 0)) == 2 and len(highlights(out, 1)) == 1
    notes = [a for a in annots(out, 0) if a["/Subtype"] == "/Text"]
    assert len(notes) == 1
    assert len(PdfReader(str(out)).pages) == 3


def test_exact_sentence_highlight(contract_pdf):
    doc, out, _ = run(contract_pdf)
    high = next(a for a in highlights(out, 0) if a["/Contents"].startswith("[HIGH]"))
    assert high["/Contents"] == (
        "[HIGH] Deposit exceeds the legal maximum\nTres meses > un mes. ñ €\nLaw: [BOE-A-1994-26003, Art. 36]"
    )
    assert high["/T"] == "Your AI Lawyer"
    assert [float(v) for v in high["/C"]] == pytest.approx([1.0, 0x9a / 255, 0x9a / 255], abs=0.01)
    assert "/N" in high["/AP"]
    rects = quads(high)
    assert len(rects) == 2                                   # "fian-" on one line, the rest on the next
    p3 = doc["passages"][2]
    bx0, by0, bx1, by1 = p3["bbox"]
    assert all(bx0 - 0.1 <= x0 and x1 <= bx1 + 0.1 and by0 - 0.1 <= y0 and y1 <= by1 + 0.1 for x0, y0, x1, y1 in rects)
    fian = next(w for w in p3["words"] if w["text"] == "fian-")
    assert rects[0][0] == pytest.approx(fian["x0"], abs=0.1)  # starts at the quoted word, not at "SEGUNDA."


def test_fallback_when_quote_missing(contract_pdf):
    doc, out, _ = run(contract_pdf)
    medium = next(a for a in highlights(out, 0) if a["/Contents"].startswith("[MEDIUM]"))
    rects = quads(medium)
    assert len(rects) == 2
    x0, y0, x1, y1 = doc["passages"][1]["bbox"]
    assert min(r[0] for r in rects) == pytest.approx(x0, abs=0.1) and max(r[2] for r in rects) == pytest.approx(x1, abs=0.1)
    assert min(r[1] for r in rects) == pytest.approx(y0, abs=0.1) and max(r[3] for r in rects) == pytest.approx(y1, abs=0.1)
    low = highlights(out, 1)[0]                               # quote not in passage 6 -> whole passage
    assert low["/Contents"] == "[LOW] Short term\nCheck the minimum term."
    assert len(quads(low)) == 1


def test_summary_note(contract_pdf):
    _, out, _ = run(contract_pdf)
    note = next(a for a in annots(out, 0) if a["/Subtype"] == "/Text")
    assert note["/Contents"] == summary_text(make_review(), extract(contract_pdf))
    assert note["/T"] == "Your AI Lawyer" and "/N" in note["/AP"]
    text = note["/Contents"]
    assert text.splitlines()[0] == "Contract review: residential lease"
    assert "Findings: 1 high, 1 medium, 1 low" in text
    assert "Missing terms:\n- No energy certificate: It must be attached. Law: [BOE-A-2013-3904]" in text
    assert "Not covered by the knowledge base:\n- Pets clause (passage 5)" in text
    assert "Passages not reviewed:" not in text
    assert "Pages skipped:\n- Page 3: no extractable text" in text
    assert text.endswith(DISCLAIMER)
    assert ZERO_FINDINGS_NOTE not in text and not note.get("/Open", False).value


def test_summary_lists_unreviewed_passages(contract_pdf):
    review = make_review()
    review["unreviewed"] = ["Passages 5-6: review stopped early"]
    assert "Passages not reviewed:\n- Passages 5-6: review stopped early" in summary_text(review, extract(contract_pdf))


@pytest.mark.parametrize("origin", [(0, 0), (100, 50)])
def test_highlight_is_visible_when_rendered(tmp_path, origin):
    pdf = make_pdf(tmp_path / "lease.pdf", CONTRACT_PAGES, origin=origin)
    doc, out, _ = run(pdf)
    words = doc["passages"][2]["words"]
    de, tres = next(w for w in words if w["text"] == "de"), next(w for w in words if w["text"] == "tres")
    x, y = (de["x1"] + tres["x0"]) / 2, (de["y0"] + de["y1"]) / 2     # the gap between two quoted words
    assert pixel(pdf, 0, x, y) == (255, 255, 255)
    r, g, b = pixel(out, 0, x, y)
    assert r > 240 and g < 200 and b < 200                            # tinted red
    note = next(a for a in annots(out, 0) if a["/Subtype"] == "/Text")
    nx0, ny0, nx1, ny1 = (float(v) for v in note["/Rect"])
    assert pixel(out, 0, (nx0 + nx1) / 2, (ny0 + ny1) / 2) != (255, 255, 255)


def test_zero_findings_still_writes_summary(contract_pdf):
    review = make_review()
    review["findings"] = []
    _, out, stats = run(contract_pdf, review)
    assert stats == {"high": 0, "medium": 0, "low": 0, "exact": 0, "fallback": 0}
    assert highlights(out, 0) == []
    note = next(a for a in annots(out, 0) if a["/Subtype"] == "/Text")
    assert "Findings: 0 high, 0 medium, 0 low" in note["/Contents"]
    lines = note["/Contents"].splitlines()
    assert lines[1] == "Findings: 0 high, 0 medium, 0 low" and lines[2] == ZERO_FINDINGS_NOTE
    assert note["/Open"].value is True


def test_summary_note_sits_inside_an_inset_cropbox(tmp_path):
    plain = make_pdf(tmp_path / "plain.pdf", CONTRACT_PAGES)
    writer = PdfWriter(clone_from=str(plain))
    writer.pages[0].cropbox = RectangleObject((50, 50, 545, 800))
    pdf = tmp_path / "lease.pdf"
    writer.write(str(pdf))
    _, out, _ = run(pdf)
    note = next(a for a in annots(out, 0) if a["/Subtype"] == "/Text")
    assert [float(v) for v in note["/Rect"]] == [505, 760, 525, 780]


def test_source_file_is_untouched(contract_pdf):
    before = contract_pdf.read_bytes()
    run(contract_pdf)
    assert contract_pdf.read_bytes() == before


def test_existing_annotations_kept_and_rerun_is_idempotent(tmp_path):
    plain = make_pdf(tmp_path / "plain.pdf", CONTRACT_PAGES)
    writer = PdfWriter(clone_from=str(plain))
    writer.add_annotation(page_number=0, annotation=Text(text="already here", rect=(10, 10, 30, 30)))
    pdf = tmp_path / "lease.pdf"
    writer.write(str(pdf))
    _, out, _ = run(pdf)
    first = len(annots(out, 0))
    assert first == 1 + 2 + 1                                 # existing + two highlights + summary note
    run(pdf)
    assert len(annots(out, 0)) == first


def cli(monkeypatch, capsys, *args, index=None):
    monkeypatch.setattr(annotate_module, "ChromaCitationIndex", lambda: index or StubIndex())
    monkeypatch.setattr(sys, "argv", ["annotate", *args])
    code = 0
    try:
        annotate_module.main()
    except SystemExit as exc:
        code = exc.code
    return code, capsys.readouterr().out


def prepared(pdf, review=None):
    write_outputs(pdf, extract(pdf))
    (review_dir(pdf) / "findings.json").write_text(json.dumps(review or make_review()))


def test_main_writes_pdf_and_reports(contract_pdf, monkeypatch, capsys):
    prepared(contract_pdf)
    code, out = cli(monkeypatch, capsys, str(contract_pdf))
    assert code == 0 and reviewed_pdf(contract_pdf).exists()
    assert "Findings: 1 high, 1 medium, 1 low" in out
    assert "Placed on the exact sentence: 1 | whole passage: 2" in out
    assert "lease.reviewed.pdf" in out.replace("\n", "")


def test_main_with_a_missing_contract(contract_pdf, monkeypatch, capsys):
    prepared(contract_pdf)
    contract_pdf.unlink()
    code, out = cli(monkeypatch, capsys, str(contract_pdf))
    assert code == 1 and "File not found" in out


def test_main_with_unreadable_review_data(contract_pdf, monkeypatch, capsys):
    prepared(contract_pdf)
    (review_dir(contract_pdf) / "passages.json").write_text("[1, 2]")
    code, out = cli(monkeypatch, capsys, str(contract_pdf))
    assert code == 1 and "is unreadable" in out and "/review-contract" in out


def test_main_check_validates_without_writing(contract_pdf, monkeypatch, capsys):
    prepared(contract_pdf)
    code, out = cli(monkeypatch, capsys, str(contract_pdf), "--check")
    assert code == 0 and "findings.json is valid: 3 findings" in out
    assert not reviewed_pdf(contract_pdf).exists()


def test_main_lists_every_problem(contract_pdf, monkeypatch, capsys):
    review = make_review()
    review["findings"][0]["passage"] = 99
    review["findings"][1]["confidence"] = "certain"
    prepared(contract_pdf, review)
    code, out = cli(monkeypatch, capsys, str(contract_pdf))
    assert code == 1 and "passage 99" in out and "high, medium, low" in out
    assert not reviewed_pdf(contract_pdf).exists()


def test_main_refuses_changed_contract(contract_pdf, monkeypatch, capsys):
    prepared(contract_pdf)
    make_pdf(contract_pdf, CONTRACT_PAGES[:1])
    code, out = cli(monkeypatch, capsys, str(contract_pdf))
    assert code == 1 and "changed since it was read" in out and "/review-contract" in out


def test_main_without_a_review(contract_pdf, monkeypatch, capsys):
    code, out = cli(monkeypatch, capsys, str(contract_pdf))
    assert code == 1 and "Run /review-contract first" in out


def test_main_with_malformed_findings(contract_pdf, monkeypatch, capsys):
    prepared(contract_pdf)
    (review_dir(contract_pdf) / "findings.json").write_text("{not json")
    code, out = cli(monkeypatch, capsys, str(contract_pdf))
    assert code == 1 and "not valid JSON" in out
