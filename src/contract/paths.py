"""Where contract-review files live; hashing."""

import hashlib
from pathlib import Path


def resolve_pdf(arg: str) -> Path:
    return Path(arg).expanduser().resolve()


def review_dir(pdf: Path) -> Path:
    return pdf.parent / f"{pdf.stem}.review"


def reviewed_pdf(pdf: Path) -> Path:
    return pdf.parent / f"{pdf.stem}.reviewed.pdf"


def file_md5(path: Path) -> str:
    return hashlib.md5(path.read_bytes()).hexdigest()
