"""Turn the chosen sheet + header row into the session's original snapshot (v0). Runs in the worker process."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

import pandas as pd

from ...config import settings
from ..storage import snapshots
from . import csvfile, workbook
from .errors import IngestError


def _raw_rows(path: Path, kind: str, sheet_index: int) -> tuple[list[list[Any]], int, int]:
    """All rows as native Python values ('' empty cells become None), merged-range count, error-cell count."""
    if kind == "csv":
        fmt = csvfile.detect_format(path)
        rows = [[None if cell == "" else cell for cell in row] for row in csvfile.iter_rows(path, fmt)]
        return rows, 0, 0
    wb = workbook.open_workbook(path)
    try:
        sheet = wb.get_sheet_by_index(sheet_index)
        errors = workbook.count_error_cells(path, sheet.name) if kind == "xlsx" else 0
        data = sheet.to_python(skip_empty_area=False)
        try:
            merged = len(sheet.merged_cell_ranges or [])
        except Exception:  # noqa: BLE001 - not available for every format
            merged = 0
    finally:
        wb.close()
    return [[None if v == "" else v for v in row] for row in data], merged, errors


def normalise_headers(raw: list[Any]) -> tuple[list[str], list[dict[str, Any]]]:
    """Blank headers → "Column N"; duplicates → "Name (2)"; whitespace collapsed. Every change is reported."""
    names: list[str] = []
    changes: list[dict[str, Any]] = []
    seen: dict[str, int] = {}
    for i, value in enumerate(raw):
        original = "" if value is None else workbook.display_value(value)
        name = re.sub(r"\s+", " ", original).strip()[:200]
        reason = None
        if not name:
            name, reason = f"Column {i + 1}", "blank"
        elif name != original:
            reason = "whitespace"
        key = name.casefold()
        if key in seen:
            seen[key] += 1
            candidate = f"{name} ({seen[key]})"
            while candidate.casefold() in seen:
                seen[key] += 1
                candidate = f"{name} ({seen[key]})"
            name, reason = candidate, "duplicate"
        seen.setdefault(name.casefold(), 1)
        names.append(name)
        if reason:
            changes.append({"position": i + 1, "original": original, "new": name, "reason": reason})
    return names, changes


def parse_to_snapshot(
    path: str, kind: str, sheet_index: int, header_row: int, dataset_id: str, session_id: str
) -> dict[str, Any]:
    rows, merged, error_cells = _raw_rows(Path(path), kind, sheet_index)
    if header_row >= len(rows):
        raise IngestError("INVALID_HEADER_ROW", "The header row is beyond the last row of the sheet.")
    width = max((len(r) for r in rows), default=0)
    header = list(rows[header_row]) + [None] * (width - len(rows[header_row]))
    # Drop trailing columns that have neither a header nor any data.
    used = width
    while used > 0 and header[used - 1] is None and all(len(r) < used or r[used - 1] is None for r in rows):
        used -= 1
    if used == 0:
        raise IngestError("EMPTY_SHEET", "This sheet has no data below the chosen header row.")
    body = [list(r[:used]) + [None] * (used - len(r[:used])) for r in rows[header_row + 1 :]]
    # Drop trailing rows that are completely empty (Excel's used range often extends past the data).
    while body and all(v is None for v in body[-1]):
        body.pop()

    n_rows, n_cols = len(body), used
    if n_rows > settings.max_rows or n_cols > settings.max_columns or n_rows * n_cols > settings.max_cells:
        raise IngestError("SHEET_TOO_LARGE", "This sheet is above the configured row, column or cell limits.", 413)

    names, changes = normalise_headers(header[:used])
    df = pd.DataFrame(body, columns=names, dtype=object)
    df.index = pd.RangeIndex(n_rows)
    warnings = []
    if header_row:
        warnings.append(f"{header_row} row(s) above the header row were skipped.")
    if merged:
        warnings.append(
            f"{merged} merged cell range(s): only the first cell of each keeps its value; the others are empty."
        )
    if error_cells:
        warnings.append(
            f"{error_cells} cell(s) contain Excel errors such as #DIV/0! or #REF!. They are treated as missing values."
        )
    meta = {
        "version": 0,
        "rows": n_rows,
        "columns": names,
        "header_row": header_row,
        "header_changes": changes,
        "merged_ranges": merged,
        "excel_error_cells": error_cells,
        "warnings": warnings,
    }
    snapshots.write(df, meta, dataset_id, session_id, 0)
    return meta
