"""Tests for src/contract/extract.py and src/contract/paths.py."""

import hashlib
import json
import os
import sys

import pytest
from pypdf import PdfWriter

from conftest import CONTRACT_PAGES
from pdf_factory import make_pdf
from src.contract import extract as extract_module
from src.contract.extract import (
    MAX_PASSAGE_CHARS, ExtractError, extract, review_status, write_outputs,
)
from src.contract.paths import review_dir, reviewed_pdf


def _write(path, data):
    path.write_bytes(data)
    return path


def _encrypted(path):
    make_pdf(path, [[(72, 770, "Secret.")]])
    writer = PdfWriter(clone_from=str(path))
    writer.encrypt("pw")
    writer.write(str(path))
    return path


def test_passages_ids_pages_and_text(contract_pdf):
    doc = extract(contract_pdf)
    assert [p["id"] for p in doc["passages"]] == [1, 2, 3, 4, 5, 6]
    assert [p["page"] for p in doc["passages"]] == [1, 1, 1, 1, 1, 2]
    assert doc["passages"][0]["text"] == "CONTRATO DE ARRENDAMIENTO"
    assert doc["passages"][2]["text"] == (
        "SEGUNDA. Fianza. El arrendatario entrega una fian- za de tres mensualidades de renta."
    )
    # numbered clauses at normal line spacing still split
    assert doc["passages"][3]["text"] == "1. El pago se hará por meses anticipados."
    assert doc["passages"][4]["text"] == "2. La renta se actualizará cada año."
    assert doc["page_count"] == 3
    assert doc["skipped_pages"] == [{"page": 3, "reason": "no_text"}]
    assert doc["source"] == str(contract_pdf.resolve())
    assert doc["source_md5"] == hashlib.md5(contract_pdf.read_bytes()).hexdigest()


def test_words_carry_pdf_coordinates_and_line_index(contract_pdf):
    p3 = extract(contract_pdf)["passages"][2]
    first, last = p3["words"][0], p3["words"][-1]
    assert first["text"] == "SEGUNDA." and first["line"] == 0 and last["line"] == 1
    assert first["x0"] == pytest.approx(72, abs=0.5)
    assert first["y0"] < 696 < first["y1"]          # baseline of line 1 sits inside the box
    assert last["y0"] < 682 < last["y1"]
    x0, y0, x1, y1 = p3["bbox"]
    assert all(x0 <= w["x0"] and w["x1"] <= x1 and y0 <= w["y0"] and w["y1"] <= y1 for w in p3["words"])


def test_coordinates_follow_a_shifted_page_box(tmp_path):
    pdf = make_pdf(tmp_path / "off.pdf", CONTRACT_PAGES[:1], origin=(100, 50))
    w = extract(pdf)["passages"][0]["words"][0]
    assert w["x0"] == pytest.approx(172, abs=0.5)
    assert w["y0"] < 820 < w["y1"]


def test_rotated_page_is_skipped(tmp_path):
    pdf = make_pdf(tmp_path / "rot.pdf", CONTRACT_PAGES[:2], rotate={0: 90})
    doc = extract(pdf)
    assert doc["skipped_pages"] == [{"page": 1, "reason": "rotated"}]
    assert [(p["id"], p["page"]) for p in doc["passages"]] == [(1, 2)]


def test_long_passage_is_split(tmp_path):
    lines = [(72, 770 - 14 * i, "Lorem ipsum dolor sit amet consectetur adipiscing elit sed do.") for i in range(40)]
    doc = extract(make_pdf(tmp_path / "long.pdf", [lines]))
    assert len(doc["passages"]) >= 2
    assert all(len(p["text"]) <= MAX_PASSAGE_CHARS for p in doc["passages"])
    assert sum(len(p["words"]) for p in doc["passages"]) == 40 * 10


@pytest.mark.parametrize("build, fragment", [
    (lambda d: d / "missing.pdf", "File not found"),
    (lambda d: _write(d / "fake.pdf", b"hello, not a pdf"), "Not a PDF"),
    (lambda d: _encrypted(d / "enc.pdf"), "Encrypted PDF"),
    (lambda d: make_pdf(d / "scan.pdf", [[], []]), "scanned PDF"),
])
def test_extract_errors(tmp_path, build, fragment):
    with pytest.raises(ExtractError, match=fragment):
        extract(build(tmp_path))


def test_write_outputs_and_text_listing(contract_pdf):
    doc = extract(contract_pdf)
    json_path, txt_path = write_outputs(contract_pdf, doc)
    assert json_path == contract_pdf.parent / "lease.review" / "passages.json"
    assert json.loads(json_path.read_text()) == doc
    text = txt_path.read_text()
    assert text.splitlines()[:3] == [
        f"# Source: {contract_pdf.resolve()}",
        "# Pages: 3 | Passages: 6",
        "# Skipped pages: 3 (no extractable text)",
    ]
    assert "\n\n[3] (p.1) SEGUNDA. Fianza. El arrendatario entrega una fian- za" in text
    assert "\n\n[6] (p.2) TERCERA. Duración: un año." in text


def test_review_status(contract_pdf):
    assert review_status(contract_pdf) == "no-review"
    write_outputs(contract_pdf, extract(contract_pdf))
    assert review_status(contract_pdf) == "no-review"          # passages but no findings yet
    findings = review_dir(contract_pdf) / "findings.json"
    findings.write_text("{}")
    assert review_status(contract_pdf) == "incomplete"         # findings written, PDF never produced
    out = reviewed_pdf(contract_pdf)
    out.write_bytes(b"%PDF-1.4")
    os.utime(findings, (1_000, 1_000))
    os.utime(out, (2_000, 2_000))
    assert review_status(contract_pdf) == "reviewed"
    os.utime(findings, (3_000, 3_000))                         # findings edited after the PDF was written
    assert review_status(contract_pdf) == "incomplete"
    os.utime(out, (4_000, 4_000))
    make_pdf(contract_pdf, CONTRACT_PAGES[:1])                 # the contract changes
    assert review_status(contract_pdf) == "changed"


def test_write_outputs_removes_stale_findings(contract_pdf):
    write_outputs(contract_pdf, extract(contract_pdf))
    findings = review_dir(contract_pdf) / "findings.json"
    findings.write_text("{}")
    write_outputs(contract_pdf, extract(contract_pdf))         # unchanged contract: findings kept
    assert findings.exists()
    make_pdf(contract_pdf, CONTRACT_PAGES[:1])
    write_outputs(contract_pdf, extract(contract_pdf))         # changed contract: findings removed
    assert not findings.exists()


def test_input_file_is_not_modified(contract_pdf):
    before = contract_pdf.read_bytes()
    write_outputs(contract_pdf, extract(contract_pdf))
    assert contract_pdf.read_bytes() == before


def test_main_handles_path_with_spaces_and_tilde(tmp_path, monkeypatch, capsys):
    home = tmp_path / "home dir"
    (home / "my contracts").mkdir(parents=True)
    make_pdf(home / "my contracts" / "lease v2.pdf", CONTRACT_PAGES)
    monkeypatch.setenv("HOME", str(home))
    monkeypatch.setattr(sys, "argv", ["extract", "~/my contracts/lease v2.pdf"])
    extract_module.main()
    assert (home / "my contracts" / "lease v2.review" / "passages.txt").exists()
    assert "Passages: 6" in capsys.readouterr().out


def test_main_status_and_error_exit(contract_pdf, tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(sys, "argv", ["extract", str(contract_pdf), "--status"])
    extract_module.main()
    assert capsys.readouterr().out.strip() == "no-review"
    monkeypatch.setattr(sys, "argv", ["extract", str(tmp_path / "nope.pdf")])
    with pytest.raises(SystemExit) as exc:
        extract_module.main()
    assert exc.value.code == 1


def test_status_of_a_missing_contract_is_an_error(contract_pdf, monkeypatch, capsys):
    write_outputs(contract_pdf, extract(contract_pdf))
    (review_dir(contract_pdf) / "findings.json").write_text("{}")
    contract_pdf.unlink()
    with pytest.raises(ExtractError, match="File not found"):
        review_status(contract_pdf)
    monkeypatch.setattr(sys, "argv", ["extract", str(contract_pdf), "--status"])
    with pytest.raises(SystemExit) as exc:
        extract_module.main()
    assert exc.value.code == 1
    assert "File not found" in capsys.readouterr().out


def test_double_spaced_paragraphs_stay_together(tmp_path):
    para1 = [(72, 770 - 28 * i, f"Linea {i} del primer parrafo sin punto final") for i in range(5)]
    para2 = [(72, 770 - 28 * 4 - 56 - 28 * i, f"Linea {i} del segundo parrafo sin punto final") for i in range(3)]
    doc = extract(make_pdf(tmp_path / "double.pdf", [para1 + para2]))
    assert [len({w["line"] for w in p["words"]}) for p in doc["passages"]] == [5, 3]


def test_evenly_spaced_single_line_clauses_split_at_sentence_ends(tmp_path):
    lines = [(72, 770 - 30 * i, f"Clausula {i}: el arrendatario pagara la renta.") for i in range(4)]
    doc = extract(make_pdf(tmp_path / "list.pdf", [lines]))
    assert len(doc["passages"]) == 4


def test_a_directory_is_not_a_pdf(tmp_path):
    with pytest.raises(ExtractError, match="Not a PDF"):
        extract(tmp_path)


def test_corrupt_passages_json_does_not_block_a_new_extract(contract_pdf):
    write_outputs(contract_pdf, extract(contract_pdf))
    rdir = review_dir(contract_pdf)
    (rdir / "findings.json").write_text("{}")
    (rdir / "passages.json").write_text("{broken")
    assert review_status(contract_pdf) == "changed"
    write_outputs(contract_pdf, extract(contract_pdf))
    assert not (rdir / "findings.json").exists()
    assert json.loads((rdir / "passages.json").read_text())["page_count"] == 3
