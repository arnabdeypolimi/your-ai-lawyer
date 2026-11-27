"""Build small text PDFs for tests: standard Helvetica 11pt, WinAnsi, A4."""

from pypdf import PdfWriter
from pypdf.generic import (
    ArrayObject, DecodedStreamObject, DictionaryObject, FloatObject, NameObject, NumberObject,
)

WIDTH, HEIGHT = 595, 842


def make_pdf(path, pages, rotate=None, origin=(0, 0)):
    """pages: list of pages; each page is a list of (x, y, text) lines, y = baseline from page bottom.
    rotate: {page_index: degrees}. origin: lower-left corner of the MediaBox."""
    ox, oy = origin
    writer = PdfWriter()
    for i, lines in enumerate(pages):
        page = writer.add_blank_page(width=WIDTH, height=HEIGHT)
        page[NameObject("/MediaBox")] = ArrayObject(
            [FloatObject(v) for v in (ox, oy, ox + WIDTH, oy + HEIGHT)]
        )
        font = DictionaryObject({
            NameObject("/Type"): NameObject("/Font"),
            NameObject("/Subtype"): NameObject("/Type1"),
            NameObject("/BaseFont"): NameObject("/Helvetica"),
            NameObject("/Encoding"): NameObject("/WinAnsiEncoding"),
        })
        page[NameObject("/Resources")] = DictionaryObject(
            {NameObject("/Font"): DictionaryObject({NameObject("/F1"): font})}
        )
        ops = []
        for line in lines:
            x, y, text = line[:3]
            size = line[3] if len(line) > 3 else 11
            esc = text.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")
            ops.append(f"BT /F1 {size} Tf {x + ox} {y + oy} Td ({esc}) Tj ET")
        stream = DecodedStreamObject()
        stream.set_data("\n".join(ops).encode("cp1252"))
        page[NameObject("/Contents")] = writer._add_object(stream)
        if rotate and i in rotate:
            page[NameObject("/Rotate")] = NumberObject(rotate[i])
    writer.write(str(path))
    return path
