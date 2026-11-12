"""CSV encoding and delimiter detection, plus streaming row reading."""

from __future__ import annotations

import codecs
import csv
from collections.abc import Iterator
from dataclasses import dataclass
from pathlib import Path

from charset_normalizer import from_bytes

DELIMITERS = [",", ";", "\t", "|"]
_SAMPLE = 256 * 1024
csv.field_size_limit(10 * 1024 * 1024)


@dataclass
class CsvFormat:
    encoding: str
    delimiter: str
    replaced_characters: int  # bytes that could not be decoded (shown as U+FFFD)

    @property
    def delimiter_label(self) -> str:
        return {",": "comma", ";": "semicolon", "\t": "tab", "|": "pipe"}.get(self.delimiter, repr(self.delimiter))


def _decodes(path: Path, encoding: str) -> bool:
    decoder = codecs.getincrementaldecoder(encoding)(errors="strict")
    try:
        with path.open("rb") as fh:
            while chunk := fh.read(1024 * 1024):
                decoder.decode(chunk)
            decoder.decode(b"", final=True)
        return True
    except UnicodeDecodeError:
        return False


def detect_encoding(path: Path) -> tuple[str, int]:
    """Return (encoding, number of undecodable characters). Strict UTF-8 is preferred when it fits."""
    with path.open("rb") as fh:
        head = fh.read(_SAMPLE)
    if head.startswith(codecs.BOM_UTF8):
        enc = "utf-8-sig"
    elif head.startswith((codecs.BOM_UTF16_LE, codecs.BOM_UTF16_BE)):
        enc = "utf-16"
    elif _decodes(path, "utf-8"):
        return "utf-8", 0
    else:
        best = from_bytes(head).best()
        enc = best.encoding if best else "cp1252"
        if enc in ("ascii", "utf_8"):  # the sample was ASCII/UTF-8 but the whole file is not
            enc = "cp1252"
    if _decodes(path, enc):
        return enc, 0
    # Count characters that will be replaced, so the user is told rather than data silently changing.
    replaced = 0
    with path.open("r", encoding=enc, errors="replace", newline="") as fh:
        while chunk := fh.read(1024 * 1024):
            replaced += chunk.count("�")
    return enc, replaced


def detect_delimiter(sample: str) -> str:
    lines = [ln for ln in sample.splitlines() if ln.strip()][:50]
    if not lines:
        return ","
    try:
        return csv.Sniffer().sniff("\n".join(lines), delimiters="".join(DELIMITERS)).delimiter
    except csv.Error:
        # Fall back to the delimiter that appears most consistently per line.
        def score(d: str) -> tuple[int, int]:
            counts = [ln.count(d) for ln in lines]
            return (min(counts), sum(counts))

        best = max(DELIMITERS, key=score)
        return best if score(best)[0] > 0 else ","


def detect_format(path: Path) -> CsvFormat:
    encoding, replaced = detect_encoding(path)
    with path.open("r", encoding=encoding, errors="replace", newline="") as fh:
        sample = fh.read(64 * 1024)
    return CsvFormat(encoding=encoding, delimiter=detect_delimiter(sample), replaced_characters=replaced)


def iter_rows(path: Path, fmt: CsvFormat) -> Iterator[list[str]]:
    with path.open("r", encoding=fmt.encoding, errors="replace", newline="") as fh:
        yield from csv.reader(fh, delimiter=fmt.delimiter)


def dimensions(path: Path, fmt: CsvFormat) -> tuple[int, int]:
    """(rows, columns) counting quoted multi-line fields correctly. Trailing blank lines are ignored."""
    rows = cols = last_non_empty = 0
    for i, row in enumerate(iter_rows(path, fmt), start=1):
        rows = i
        if any(cell.strip() for cell in row):
            last_non_empty = i
            cols = max(cols, len(row))
    return (last_non_empty if rows else 0), cols


def sample_text(path: Path, fmt: CsvFormat, limit: int = 2000) -> str:
    with path.open("r", encoding=fmt.encoding, errors="replace", newline="") as fh:
        return fh.read(limit)
