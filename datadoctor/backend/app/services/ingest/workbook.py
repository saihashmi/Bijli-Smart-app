"""Worksheet discovery and raw peeks for Excel workbooks (python-calamine; formulas are never evaluated)."""

from __future__ import annotations

import posixpath
import re
import zipfile
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta
from pathlib import Path
from typing import Any

import python_calamine as pc
from defusedxml.ElementTree import parse

from .errors import IngestError

NS_MAIN = "{http://schemas.openxmlformats.org/spreadsheetml/2006/main}"
NS_REL = "{http://schemas.openxmlformats.org/officeDocument/2006/relationships}"
NS_PKG_REL = "{http://schemas.openxmlformats.org/package/2006/relationships}"


def _visibility(value: object) -> str:
    # Calamine's enum values are not hashable; compare by their string form.
    name = str(value).rsplit(".", 1)[-1]
    return {"Visible": "visible", "Hidden": "hidden", "VeryHidden": "very_hidden"}.get(name, "visible")


def _sheet_kind(value: object) -> str:
    name = str(value).rsplit(".", 1)[-1]
    return {"WorkSheet": "worksheet", "ChartSheet": "chartsheet"}.get(name, "other")


@dataclass
class SheetInfo:
    index: int
    name: str
    visibility: str
    rows: int
    columns: int
    formula_cells_without_cache: int = 0
    kind: str = "worksheet"  # worksheet | chartsheet | other


def open_workbook(path: Path) -> pc.CalamineWorkbook:
    try:
        return pc.CalamineWorkbook.from_path(str(path))
    except pc.PasswordError as e:
        raise IngestError(
            "PASSWORD_PROTECTED",
            "This workbook is password-protected. Remove the password in Excel and upload it again.",
        ) from e
    except Exception as e:  # noqa: BLE001 - calamine raises several error types for damaged files
        raise IngestError("CORRUPTED_FILE", "The workbook appears to be damaged and cannot be opened.") from e


# A cell element (optionally namespace-prefixed): self-closing, or with content up to its closing tag.
_CELL_RE = re.compile(rb"<(?:\w+:)?c\b[^>]*?(?:/>|>(.*?)</(?:\w+:)?c>)", re.S)
_F_RE = re.compile(rb"<(?:\w+:)?f[\s>/]")
_V_RE = re.compile(rb"<(?:\w+:)?v(?:\s[^>]*)?>[^<]+</(?:\w+:)?v>")
_CELL_END_RE = re.compile(rb"</(?:\w+:)?c>")
_SCAN_CHUNK = 4 * 1024 * 1024


def _count_uncached_formulas(stream) -> int:
    """Stream a worksheet XML part and count cells that have a formula but no saved value.

    A regex scan is used instead of an XML parser: ~20x faster on large sheets. Only well-formed cell
    elements are matched, and nothing in the file is evaluated.
    """
    missing = 0
    buf = b""
    while True:
        chunk = stream.read(_SCAN_CHUNK)
        buf += chunk
        if not chunk:
            tail_start = len(buf)
        else:
            # Only process up to the last closing cell tag; keep the rest (possibly a partial cell) for later.
            # ("/>" is not a safe boundary: it also closes elements inside a cell, e.g. <f t="shared"/>.)
            ends = [m.end() for m in _CELL_END_RE.finditer(buf, max(0, len(buf) - _SCAN_CHUNK - 1024))]
            tail_start = ends[-1] if ends else 0
        head, buf = buf[:tail_start], buf[tail_start:]
        if _F_RE.search(head):
            for m in _CELL_RE.finditer(head):
                body = m.group(1)
                if body and _F_RE.search(body) and not _V_RE.search(body):
                    missing += 1
        if not chunk:
            return missing


def _formula_scan(path: Path) -> dict[str, int]:
    """Count formula cells whose last calculated value was not saved in the file (xlsx only)."""
    counts: dict[str, int] = {}
    try:
        with zipfile.ZipFile(path) as zf:
            wb_root = parse(zf.open("xl/workbook.xml")).getroot()
            rels_root = parse(zf.open("xl/_rels/workbook.xml.rels")).getroot()
            targets = {r.get("Id"): r.get("Target", "") for r in rels_root.iter(f"{NS_PKG_REL}Relationship")}
            names = set(zf.namelist())
            for sheet in wb_root.iter(f"{NS_MAIN}sheet"):
                target = targets.get(sheet.get(f"{NS_REL}id"), "")
                part = (
                    target.lstrip("/") if target.startswith("/") else posixpath.normpath(posixpath.join("xl", target))
                )
                if part in names:
                    with zf.open(part) as fh:
                        counts[sheet.get("name", "")] = _count_uncached_formulas(fh)
    except Exception:  # noqa: BLE001 - scan is advisory; never block an upload
        return counts
    return counts


def discover(path: Path, kind: str) -> list[SheetInfo]:
    wb = open_workbook(path)
    formula_missing = _formula_scan(path) if kind == "xlsx" else {}
    sheets: list[SheetInfo] = []
    try:
        for i, meta in enumerate(wb.sheets_metadata):
            kind = _sheet_kind(meta.typ)
            is_ws = kind == "worksheet"
            rows = cols = 0
            if is_ws:
                try:
                    sheet = wb.get_sheet_by_index(i)
                    rows, cols = sheet.height, sheet.width
                except Exception:  # noqa: BLE001 - an unreadable sheet is reported as empty, not fatal
                    rows = cols = 0
            sheets.append(
                SheetInfo(
                    index=i,
                    name=meta.name,
                    visibility=_visibility(meta.visible),
                    rows=rows,
                    columns=cols,
                    formula_cells_without_cache=formula_missing.get(meta.name, 0),
                    kind=kind,
                )
            )
    finally:
        wb.close()
    if not sheets:
        raise IngestError("EMPTY_FILE", "The workbook contains no worksheets.")
    return sheets


def display_value(v: Any) -> str:
    """Render a raw cell for previews without changing what it means."""
    if v is None:
        return ""
    if isinstance(v, bool):
        return "TRUE" if v else "FALSE"
    if isinstance(v, float):
        return str(int(v)) if v.is_integer() and abs(v) < 1e15 else repr(v)
    if isinstance(v, datetime):
        return v.isoformat(sep=" ", timespec="seconds").removesuffix(" 00:00:00")
    if isinstance(v, (date, time)):
        return v.isoformat()
    if isinstance(v, timedelta):
        return str(v)
    return str(v)


def peek(path: Path, sheet_index: int, rows: int, max_columns: int) -> list[list[str]]:
    wb = open_workbook(path)
    try:
        sheet = wb.get_sheet_by_index(sheet_index)
        data = sheet.to_python(skip_empty_area=False, nrows=rows)
    except IndexError as e:
        raise IngestError("SHEET_NOT_FOUND", "That worksheet does not exist.", 404) from e
    finally:
        wb.close()
    return [[display_value(v) for v in row[:max_columns]] for row in data]
