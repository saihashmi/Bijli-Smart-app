"""Excel export (SPEC FR-6.1, FR-6.5): cleaned data, quality report, cleaning audit log, summary statistics.

Written with OpenPyXL in write-only mode so large sheets do not need to fit in memory twice. Native numbers,
dates and booleans stay native. Text that a spreadsheet could read as a formula is neutralised.
"""

from __future__ import annotations

from datetime import date, datetime, time
from pathlib import Path
from typing import Any

import pandas as pd
from openpyxl import Workbook
from openpyxl.cell import WriteOnlyCell
from openpyxl.styles import Alignment, Font, PatternFill
from openpyxl.utils import get_column_letter

DANGEROUS_START = ("=", "+", "-", "@", "\t", "\r")
HEADER_FILL = PatternFill("solid", fgColor="0B1F3A")
HEADER_FONT = Font(bold=True, color="FFFFFF")
TITLE_FONT = Font(bold=True, size=14)
BOLD = Font(bold=True)
MAX_WIDTH = 60
ILLEGAL = dict.fromkeys(range(0x00, 0x20))
for _keep in (0x09, 0x0A, 0x0D):
    ILLEGAL.pop(_keep)


def safe_text(value: str) -> str:
    """Neutralise formula injection: a leading apostrophe makes spreadsheet apps treat the cell as text."""
    value = value.translate(ILLEGAL)  # control characters are not allowed in XML
    return "'" + value if value.startswith(DANGEROUS_START) else value


def safe_cell(value: Any) -> Any:
    if value is None:
        return None
    if isinstance(value, str):
        return safe_text(value)
    if isinstance(value, (bool, int, float, datetime, date, time)):
        if isinstance(value, float) and value != value:  # NaN
            return None
        return value
    if isinstance(value, pd.Timestamp):
        return value.to_pydatetime()
    return safe_text(str(value))


def _header(ws: Any, names: list[str]) -> list[Any]:
    cells = []
    for name in names:
        c = WriteOnlyCell(ws, value=safe_text(str(name)))
        c.font, c.fill = HEADER_FONT, HEADER_FILL
        c.alignment = Alignment(vertical="center", wrap_text=True)
        cells.append(c)
    return cells


def _text_row(ws: Any, values: list[Any], font: Font | None = None) -> list[Any]:
    out = []
    for v in values:
        c = WriteOnlyCell(ws, value=safe_cell(v))
        if font:
            c.font = font
        out.append(c)
    return out


def _widths(ws: Any, widths: list[int]) -> None:
    for i, w in enumerate(widths, start=1):
        ws.column_dimensions[get_column_letter(i)].width = max(8, min(MAX_WIDTH, w + 2))


def _table(
    ws: Any,
    title: str,
    subtitle: str | None,
    head: list[str],
    rows: list[list[Any]],
    start_widths: list[int] | None = None,
) -> None:
    widths = start_widths or [len(h) for h in head]
    for r in rows:
        for i, v in enumerate(r[: len(widths)]):
            widths[i] = max(widths[i], min(MAX_WIDTH, len(str(v)) if v is not None else 0))
    _widths(ws, widths)
    ws.append(_text_row(ws, [title], TITLE_FONT))
    if subtitle:
        ws.append(_text_row(ws, [subtitle]))
    ws.append([])
    ws.append(_header(ws, head))
    for r in rows:
        ws.append(_text_row(ws, r))


def build_xlsx(df: pd.DataFrame, ctx: dict[str, Any], out: Path) -> dict[str, Any]:
    wb = Workbook(write_only=True)
    stamp = f"Generated {ctx['generated_at']} · {ctx['filename']} · sheet “{ctx['sheet_name']}”"

    # 1. Cleaned Data
    ws = wb.create_sheet("Cleaned Data")
    columns = [str(c) for c in df.columns]
    sample = df.head(200)
    widths = [
        max(len(name), *(len(str(v)) for v in sample[col] if v is not None), 0)
        for name, col in zip(columns, df.columns, strict=True)
    ]
    _widths(ws, widths)
    ws.freeze_panes = "A2"
    if columns:
        ws.auto_filter.ref = f"A1:{get_column_letter(len(columns))}{len(df) + 1}"
    ws.append(_header(ws, columns))
    neutralised = 0
    for row in df.itertuples(index=False, name=None):
        out_row = []
        for v in row:
            cell = safe_cell(v)
            if isinstance(v, str) and cell != v and cell.startswith("'"):
                neutralised += 1
            out_row.append(cell)
        ws.append(out_row)

    # 2. Data Quality Report
    profile = ctx["profile"]
    health = profile["health"]
    ws = wb.create_sheet("Data Quality Report")
    _widths(ws, [34, 26, 14, 12, 70, 34])
    ws.append(_text_row(ws, ["Data Quality Report"], TITLE_FONT))
    ws.append(_text_row(ws, [stamp]))
    ws.append([])
    ws.append(_text_row(ws, ["Data Health Score", health["score"], f"out of 100 ({health['band']})"], BOLD))
    ws.append(_text_row(ws, [health["formula"]]))
    ws.append([])
    ws.append(_header(ws, ["Score component", "Value (0–1)", "Weight", "Points", "How it is measured"]))
    for c in health["components"]:
        ws.append(
            _text_row(
                ws, [c["key"].replace("_", " ").capitalize(), c["value"], c["weight"], c["points"], c["explanation"]]
            )
        )
    ws.append([])
    ws.append(_header(ws, ["Issue", "Column", "Rows affected", "Severity", "What it means", "Suggested fix"]))
    for i in profile["issues"]:
        ws.append(
            _text_row(
                ws,
                [
                    i["title"],
                    i["column"] or "(whole sheet)",
                    i["affected_rows"],
                    i["severity"],
                    i["description"],
                    i["suggested_action"]["label"] or "Review manually",
                ],
            )
        )
    if not profile["issues"]:
        ws.append(_text_row(ws, ["No issues were found."]))
    ws.append([])
    for line in health.get("limitations", []):
        ws.append(_text_row(ws, [line]))

    # 3. Cleaning Audit Log
    ws = wb.create_sheet("Cleaning Audit Log")
    ops = ctx["operations"]
    _table(
        ws,
        "Cleaning Audit Log",
        f"{stamp}. The original upload is unchanged; these steps were applied to a working copy.",
        ["Step", "Operation", "Settings", "Rows affected", "Status", "Applied at", "Undone at"],
        [
            [
                o["sequence"],
                o["title"],
                o["parameters"],
                o["affected_rows"],
                o["status"],
                o["created_at"],
                o["undone_at"] or "",
            ]
            for o in ops
        ]
        or [["", "No cleaning steps were applied. This sheet is the data as uploaded.", "", "", "", "", ""]],
        [6, 30, 50, 14, 10, 22, 22],
    )

    # 4. Summary Statistics
    ws = wb.create_sheet("Summary Statistics")
    rows = []
    for c in profile["column_profiles"]:
        n, d = c.get("numeric") or {}, c.get("date") or {}
        top = (c.get("top_values") or [{}])[0]
        rows.append(
            [
                c["name"],
                c["type"],
                c["non_missing"],
                c["missing"],
                c["missing_pct"],
                c["unique"],
                n.get("min", (d.get("min") or "")[:10] if d else ""),
                n.get("max", (d.get("max") or "")[:10] if d else ""),
                n.get("mean", ""),
                n.get("median", ""),
                n.get("std", ""),
                top.get("value", ""),
                top.get("count", ""),
            ]
        )
    _table(
        ws,
        "Summary Statistics",
        f"{stamp}. {profile['rows']:,} rows × {profile['columns']:,} columns. Missing and non-numeric cells are left out of calculations, never counted as zero.",
        [
            "Column",
            "Type",
            "Filled",
            "Missing",
            "Missing %",
            "Distinct",
            "Minimum",
            "Maximum",
            "Average",
            "Median",
            "Std deviation",
            "Most frequent value",
            "Its count",
        ],
        rows,
    )

    wb.save(out)
    return {"rows": int(len(df)), "columns": len(columns), "neutralised_cells": neutralised, "size": out.stat().st_size}
