"""Turn a stored upload into a list of selectable tables (worksheets, or the single CSV table)."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from ...config import settings
from . import csvfile, workbook
from .workbook import SheetInfo


@dataclass
class Discovery:
    sheets: list[SheetInfo]
    csv: csvfile.CsvFormat | None = None
    warnings: list[str] = field(default_factory=list)


def limit_problem(rows: int, cols: int) -> str | None:
    """Why a table is too large to analyse (SPEC NFR-4), or None."""
    if rows > settings.max_rows:
        return f"{rows:,} rows is above the {settings.max_rows:,}-row limit."
    if cols > settings.max_columns:
        return f"{cols:,} columns is above the {settings.max_columns:,}-column limit."
    if rows * cols > settings.max_cells:
        return f"{rows * cols:,} cells is above the {settings.max_cells:,}-cell limit."
    return None


def discover(path: Path, kind: str) -> Discovery:
    if kind == "csv":
        fmt = csvfile.detect_format(path)
        rows, cols = csvfile.dimensions(path, fmt)
        warnings = []
        if fmt.replaced_characters:
            warnings.append(
                f"{fmt.replaced_characters:,} characters could not be decoded as {fmt.encoding} and are shown as '�'."
            )
        return Discovery(
            sheets=[SheetInfo(index=0, name="CSV data", visibility="visible", rows=rows, columns=cols)],
            csv=fmt,
            warnings=warnings,
        )
    return Discovery(sheets=workbook.discover(path, kind))


def peek(path: Path, kind: str, sheet_index: int, rows: int = 15, max_columns: int = 50) -> list[list[str]]:
    if kind == "csv":
        if sheet_index != 0:
            from .errors import IngestError

            raise IngestError("SHEET_NOT_FOUND", "A CSV file has a single table.", 404)
        fmt = csvfile.detect_format(path)
        out = []
        for row in csvfile.iter_rows(path, fmt):
            out.append(row[:max_columns])
            if len(out) >= rows:
                break
        return out
    return workbook.peek(path, sheet_index, rows, max_columns)
