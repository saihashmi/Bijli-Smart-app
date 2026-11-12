"""File-level validation: names, real content type (magic bytes), zip-bomb guard, encryption detection."""

from __future__ import annotations

import re
import unicodedata
import zipfile
from dataclasses import dataclass, field
from pathlib import Path

import olefile

from ...config import settings
from .errors import IngestError

ALLOWED_EXTENSIONS = {".xlsx": "xlsx", ".xlsm": "xlsx", ".xls": "xls", ".csv": "csv", ".txt": "csv"}

ZIP_MAGIC = b"PK\x03\x04"
OLE_MAGIC = b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1"
_OTHER_BINARY = {
    b"%PDF": "a PDF document",
    b"\x89PNG": "a PNG image",
    b"\xff\xd8\xff": "a JPEG image",
    b"GIF8": "a GIF image",
    b"Rar!": "a RAR archive",
    b"\x1f\x8b": "a gzip archive",
    b"7z\xbc\xaf": "a 7-Zip archive",
}


def sanitize_filename(name: str | None) -> str:
    """Display-only name: last path component, no control characters, max 255 chars. Never used as a path."""
    base = (name or "").replace("\\", "/").split("/")[-1]
    base = unicodedata.normalize("NFC", base)
    base = "".join(ch for ch in base if unicodedata.category(ch)[0] != "C")
    base = re.sub(r"\s+", " ", base).strip(" .")
    if len(base) > 255:
        stem, dot, ext = base.rpartition(".")
        base = (stem[: 250 - len(ext)] + dot + ext) if dot and len(ext) <= 5 else base[:255]
    return base or "upload"


def extension_kind(filename: str) -> str:
    ext = Path(filename).suffix.lower()
    kind = ALLOWED_EXTENSIONS.get(ext)
    if kind is None:
        raise IngestError(
            "UNSUPPORTED_FORMAT", "Unsupported file type. Upload an Excel (.xlsx, .xls) or CSV file.", 415
        )
    return kind


@dataclass
class ContentCheck:
    kind: str  # xlsx | xls | csv (by content, not by name)
    warnings: list[str] = field(default_factory=list)
    has_macros: bool = False


def _is_encrypted_ooxml(path: Path) -> bool:
    """Password-protected .xlsx files are OLE containers holding EncryptionInfo/EncryptedPackage streams."""
    try:
        with olefile.OleFileIO(str(path)) as ole:
            return ole.exists("EncryptionInfo") or ole.exists("EncryptedPackage")
    except OSError:
        return False


def _check_zip(path: Path) -> bool:
    """Validate an xlsx container; returns True if it contains a VBA macro project (never executed)."""
    try:
        with zipfile.ZipFile(path) as zf:
            infos = zf.infolist()
            if len(infos) > settings.max_zip_entries:
                raise IngestError(
                    "FILE_TOO_COMPLEX", "This workbook contains too many internal parts to process safely."
                )
            total = sum(i.file_size for i in infos)
            if total > settings.max_uncompressed_mb * 1024 * 1024:
                raise IngestError(
                    "FILE_TOO_LARGE_UNCOMPRESSED",
                    f"This workbook expands to more than {settings.max_uncompressed_mb} MB when opened, "
                    "which is above the processing limit.",
                    413,
                )
            names = {i.filename for i in infos}
            if "xl/workbook.xml" not in names:
                raise IngestError("INVALID_EXCEL", "The file is a ZIP archive but not a valid Excel workbook.")
            return "xl/vbaProject.bin" in names
    except zipfile.BadZipFile as e:
        raise IngestError(
            "CORRUPTED_FILE", "The workbook appears to be damaged or incomplete and cannot be opened."
        ) from e


def check_content(path: Path, declared_kind: str) -> ContentCheck:
    """Decide what the file really is from its bytes, and reject anything unsafe or unreadable."""
    size = path.stat().st_size
    if size == 0:
        raise IngestError("EMPTY_FILE", "The file is empty.")
    with path.open("rb") as fh:
        head = fh.read(8192)

    for magic, what in _OTHER_BINARY.items():
        if head.startswith(magic):
            raise IngestError("WRONG_CONTENT", f"This file is {what}, not a spreadsheet.")

    if head.startswith(ZIP_MAGIC):
        has_macros = _check_zip(path)
        check = ContentCheck(kind="xlsx", has_macros=has_macros)
        if declared_kind != "xlsx":
            check.warnings.append(
                "The file name says it is not an .xlsx workbook, but its content is; it was read as .xlsx."
            )
        if has_macros:
            check.warnings.append("This workbook contains macros. They were ignored and are never run.")
        return check

    if head.startswith(OLE_MAGIC):
        if _is_encrypted_ooxml(path):
            raise IngestError(
                "PASSWORD_PROTECTED",
                "This workbook is password-protected. Remove the password in Excel (File > Info > Protect Workbook) "
                "and upload it again.",
            )
        check = ContentCheck(kind="xls")
        if declared_kind != "xls":
            check.warnings.append("The file's content is an older Excel (.xls) workbook; it was read as .xls.")
        return check

    if declared_kind in ("xlsx", "xls"):
        raise IngestError("WRONG_CONTENT", "The file content is not a valid Excel workbook.")

    # CSV / text: reject binary content (NUL bytes), except UTF-16 text which legitimately contains them.
    if b"\x00" in head and not head.startswith((b"\xff\xfe", b"\xfe\xff")):
        raise IngestError("WRONG_CONTENT", "The file does not look like a text CSV file.")
    return ContentCheck(kind="csv")
