"""Excel (OpenPyXL) and PDF (ReportLab) exports built from computed results only."""
from __future__ import annotations

import io
from xml.sax.saxutils import escape as _esc
from datetime import datetime
from typing import Any

import pandas as pd
from openpyxl import Workbook
from openpyxl.chart import BarChart, LineChart, Reference
from openpyxl.styles import Alignment, Font, PatternFill
from openpyxl.utils import get_column_letter
from reportlab.graphics.charts.barcharts import VerticalBarChart
from reportlab.graphics.charts.lineplots import LinePlot
from reportlab.graphics.shapes import Drawing, String
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

BRAND = "0F766E"  # teal-700
HEADER_FILL = PatternFill("solid", fgColor=BRAND)
HEADER_FONT = Font(bold=True, color="FFFFFF")


def _write_table(ws, rows: list[dict[str, Any]], headers: list[tuple[str, str]], start_row: int = 1) -> int:
    for j, (_, label) in enumerate(headers, start=1):
        cell = ws.cell(row=start_row, column=j, value=label)
        cell.fill, cell.font = HEADER_FILL, HEADER_FONT
        cell.alignment = Alignment(horizontal="center")
    for i, row in enumerate(rows, start=start_row + 1):
        for j, (key, _) in enumerate(headers, start=1):
            ws.cell(row=i, column=j, value=row.get(key))
    for j, (key, label) in enumerate(headers, start=1):
        width = max([len(str(label))] + [len(str(r.get(key, ""))) for r in rows[:200]]) + 2
        ws.column_dimensions[get_column_letter(j)].width = min(max(width, 10), 60)
    ws.freeze_panes = ws.cell(row=start_row + 1, column=1)
    return start_row + len(rows)


def build_xlsx(name: str, analysis: dict[str, Any], insights: dict[str, Any], cleaned: pd.DataFrame,
               cleaning_log: list[dict[str, Any]]) -> bytes:
    wb = Workbook()
    s = analysis.get("summary", {})
    cur = s.get("currency", "")

    ws = wb.active
    ws.title = "Summary"
    ws["A1"] = f"Bijli Smart report — {name}"
    ws["A1"].font = Font(bold=True, size=14, color=BRAND)
    ws["A2"] = f"Generated {datetime.now().strftime('%Y-%m-%d %H:%M')}. All figures computed from the uploaded data."
    ws["A2"].font = Font(italic=True, color="666666")
    rows = [
        ("Records analysed", s.get("records")),
        ("Period", f"{(s.get('start') or '')[:10]} to {(s.get('end') or '')[:10]}"),
        ("Days covered", s.get("span_days")),
        ("Data granularity", s.get("granularity")),
        ("Total consumption (kWh)", s.get("total_kwh")),
        ("Average per day (kWh)", s.get("avg_daily_kwh")),
        (f"Total cost ({cur})", s.get("total_cost")),
        (f"Effective rate ({cur}/kWh)", s.get("effective_rate")),
        ("Cost source", {"file": "Billed amounts in file", "tariff": "Tariff entered by user"}.get(s.get("cost_source"), "Not available")),
    ]
    if s.get("peak_day"):
        rows.append(("Highest day", f"{s['peak_day']['date']} ({s['peak_day']['kwh']} kWh)"))
    for i, (k, v) in enumerate(rows, start=4):
        ws.cell(row=i, column=1, value=k).font = Font(bold=True)
        ws.cell(row=i, column=2, value=v)
    r0 = 4 + len(rows) + 1
    ws.cell(row=r0, column=1, value="Key findings").font = Font(bold=True, size=12, color=BRAND)
    for i, f in enumerate(analysis.get("facts", []), start=r0 + 1):
        ws.cell(row=i, column=1, value=f["category"].title())
        ws.cell(row=i, column=2, value=f["text"]).alignment = Alignment(wrap_text=True, vertical="top")
    ws.column_dimensions["A"].width = 28
    ws.column_dimensions["B"].width = 110

    daily = analysis.get("daily") or []
    if daily:
        wsd = wb.create_sheet("Daily")
        headers = [("date", "Date"), ("kwh", "kWh")] + ([("cost", f"Cost ({cur})")] if "cost" in daily[0] else [])
        last = _write_table(wsd, daily, headers)
        ch = LineChart()
        ch.title, ch.y_axis.title, ch.height, ch.width = "Daily consumption", "kWh", 9, 24
        ch.add_data(Reference(wsd, min_col=2, min_row=1, max_row=last), titles_from_data=True)
        ch.set_categories(Reference(wsd, min_col=1, min_row=2, max_row=last))
        ch.legend = None
        wsd.add_chart(ch, "E2")

    monthly = analysis.get("monthly") or []
    if monthly:
        wsm = wb.create_sheet("Monthly")
        headers = [("month", "Month"), ("kwh", "kWh"), ("change_pct", "Change vs previous (%)")] + (
            [("cost", f"Cost ({cur})")] if "cost" in monthly[0] else [])
        last = _write_table(wsm, monthly, headers)
        ch = BarChart()
        ch.title, ch.y_axis.title, ch.height, ch.width = "Monthly consumption", "kWh", 9, 20
        ch.add_data(Reference(wsm, min_col=2, min_row=1, max_row=last), titles_from_data=True)
        ch.set_categories(Reference(wsm, min_col=1, min_row=2, max_row=last))
        ch.legend = None
        wsm.add_chart(ch, "F2")

    if analysis.get("categories"):
        cats = analysis["categories"]
        wsc = wb.create_sheet("Categories")
        _write_table(wsc, cats, [("category", "Category"), ("kwh", "kWh"), ("share_pct", "Share (%)")] + (
            [("cost", f"Cost ({cur})")] if "cost" in cats[0] else []))

    if analysis.get("hourly"):
        wsh = wb.create_sheet("Hourly profile")
        _write_table(wsh, analysis["hourly"], [("hour", "Hour"), ("avg_kwh", "Average kWh")])

    if analysis.get("anomalies"):
        wsa = wb.create_sheet("Anomalies")
        _write_table(wsa, analysis["anomalies"], [("date", "Date"), ("kwh", "kWh"), ("typical_kwh", "Typical day kWh"),
                                                  ("deviation_pct", "Deviation (%)"), ("direction", "Direction")])

    if analysis.get("savings"):
        wss = wb.create_sheet("Savings scenarios")
        _write_table(wss, analysis["savings"], [("title", "Scenario"), ("kwh", "kWh saved"), ("cost", f"Cost saved ({cur})"),
                                                ("basis", "How it was calculated")])

    if insights and insights.get("insights"):
        wsi = wb.create_sheet("Insights")
        wsi["A1"] = "Source: " + ("AI interpretation of computed facts (numbers verified)" if insights.get("source") == "groq"
                                   else "Rule-based statements from computed facts")
        wsi["A1"].font = Font(italic=True)
        _write_table(wsi, [{"title": i.get("title"), "explanation": i.get("explanation")} for i in insights["insights"]],
                     [("title", "Insight"), ("explanation", "Explanation")], start_row=3)
        wsi.column_dimensions["B"].width = 110

    if cleaning_log:
        wsl = wb.create_sheet("Cleaning log")
        _write_table(wsl, cleaning_log, [("title", "Step"), ("rows_before", "Rows before"), ("rows_after", "Rows after"),
                                         ("values_changed", "Values changed"), ("detail", "Detail")])

    wsx = wb.create_sheet("Cleaned data")
    data = cleaned.copy()
    for c in data.columns:
        if pd.api.types.is_datetime64_any_dtype(data[c]):
            data[c] = data[c].astype(object).where(data[c].notna(), None)
    wsx.append(list(map(str, data.columns)))
    for cell in wsx[1]:
        cell.fill, cell.font = HEADER_FILL, HEADER_FONT
    for row in data.itertuples(index=False):
        wsx.append([None if (isinstance(v, float) and v != v) or v is pd.NaT else v for v in row])
    for j, c in enumerate(data.columns, start=1):
        wsx.column_dimensions[get_column_letter(j)].width = max(12, min(40, len(str(c)) + 4))
    wsx.freeze_panes = "A2"

    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()


# ---------------- PDF ----------------

TEAL = colors.HexColor("#0f766e")
AMBER = colors.HexColor("#d97706")


def _line_chart(points: list[tuple[int, float]], labels: list[str], title: str) -> Drawing:
    d = Drawing(170 * mm, 70 * mm)
    lp = LinePlot()
    lp.x, lp.y, lp.width, lp.height = 14 * mm, 10 * mm, 150 * mm, 50 * mm
    lp.data = [points]
    lp.lines[0].strokeColor = TEAL
    lp.lines[0].strokeWidth = 1.5
    lp.xValueAxis.valueMin, lp.xValueAxis.valueMax = 0, max(1, len(points) - 1)
    step = max(1, len(points) // 6)
    lp.xValueAxis.valueSteps = list(range(0, len(points), step))
    lp.xValueAxis.labelTextFormat = lambda v: labels[int(v)] if 0 <= int(v) < len(labels) else ""
    lp.xValueAxis.labels.fontSize = 7
    lp.xValueAxis.labels.fontName = lp.yValueAxis.labels.fontName = "Helvetica"
    lp.yValueAxis.labels.fontSize = 7
    lp.yValueAxis.valueMin = 0
    d.add(lp)
    d.add(String(14 * mm, 65 * mm, title, fontName="Helvetica-Bold", fontSize=9, fillColor=colors.HexColor("#334155")))
    return d


def _bar_chart(values: list[float], labels: list[str], title: str) -> Drawing:
    d = Drawing(170 * mm, 70 * mm)
    bc = VerticalBarChart()
    bc.x, bc.y, bc.width, bc.height = 14 * mm, 12 * mm, 150 * mm, 48 * mm
    bc.data = [values]
    bc.bars[0].fillColor = TEAL
    bc.bars[0].strokeColor = None
    bc.categoryAxis.categoryNames = labels
    bc.categoryAxis.labels.fontSize = 6.5
    bc.categoryAxis.labels.angle = 30 if len(labels) > 8 else 0
    bc.categoryAxis.labels.dy = -6 if len(labels) > 8 else -2
    bc.valueAxis.valueMin = 0
    bc.valueAxis.labels.fontSize = 7
    bc.valueAxis.labels.fontName = bc.categoryAxis.labels.fontName = "Helvetica"
    d.add(bc)
    d.add(String(14 * mm, 65 * mm, title, fontName="Helvetica-Bold", fontSize=9, fillColor=colors.HexColor("#334155")))
    return d


def _table(data: list[list[Any]], widths: list[float] | None = None) -> Table:
    t = Table(data, colWidths=widths, repeatRows=1)
    t.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), TEAL),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, -1), 8),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#f1f5f9")]),
        ("GRID", (0, 0), (-1, -1), 0.25, colors.HexColor("#cbd5e1")),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
    ]))
    return t


def _n(v: Any, digits: int = 2) -> str:
    if v is None:
        return "–"
    try:
        f = float(v)
    except (TypeError, ValueError):
        return str(v)
    return f"{f:,.0f}" if abs(f) >= 1000 else f"{f:,.{digits}f}"


def build_pdf(name: str, analysis: dict[str, Any], insights: dict[str, Any], cleaning_log: list[dict[str, Any]]) -> bytes:
    buf = io.BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=A4, leftMargin=18 * mm, rightMargin=18 * mm, topMargin=16 * mm,
                            bottomMargin=16 * mm, title=f"Bijli Smart report — {name}")
    ss = getSampleStyleSheet()
    h1 = ParagraphStyle("h1", parent=ss["Heading1"], textColor=TEAL, fontSize=18, spaceAfter=4)
    h2 = ParagraphStyle("h2", parent=ss["Heading2"], textColor=TEAL, fontSize=12, spaceBefore=10, spaceAfter=4)
    body = ParagraphStyle("b", parent=ss["BodyText"], fontSize=9, leading=12.5)
    small = ParagraphStyle("s", parent=body, fontSize=7.5, textColor=colors.HexColor("#64748b"))
    s = analysis.get("summary", {})
    cur = s.get("currency", "")
    story: list[Any] = [
        Paragraph("Bijli Smart — electricity report", h1),
        Paragraph(f"{_esc(name)} · generated {datetime.now().strftime('%Y-%m-%d %H:%M')}", small),
        Paragraph("Every figure in this report is computed directly from the uploaded data. "
                  "Text marked as AI interpretation only restates those computed figures.", small),
        Spacer(1, 6),
    ]
    kpis = [["Total kWh", "Avg / day (kWh)", f"Total cost ({cur})", f"Rate ({cur}/kWh)", "Period"],
            [_n(s.get("total_kwh")), _n(s.get("avg_daily_kwh")), _n(s.get("total_cost")), _n(s.get("effective_rate"), 3),
             f"{(s.get('start') or '')[:10]} → {(s.get('end') or '')[:10]}"]]
    story.append(_table(kpis, [30 * mm, 30 * mm, 32 * mm, 30 * mm, 52 * mm]))

    if insights:
        story.append(Paragraph("Summary", h2))
        label = "AI interpretation (numbers verified against computed results)" if insights.get("source") == "groq" else "Computed findings"
        story.append(Paragraph(label, small))
        story.append(Paragraph(_esc(insights.get("summary") or ""), body))

    daily = analysis.get("daily") or []
    if len(daily) >= 3:
        pts = [(i, d["kwh"] or 0) for i, d in enumerate(daily)]
        story.append(Spacer(1, 6))
        story.append(_line_chart(pts, [d["date"][5:] for d in daily], "Daily consumption (kWh)"))
    monthly = analysis.get("monthly") or []
    if len(monthly) >= 2:
        story.append(_bar_chart([m["kwh"] or 0 for m in monthly[-18:]], [m["month"] for m in monthly[-18:]],
                                "Monthly consumption (kWh)"))

    story.append(Paragraph("Key findings", h2))
    for f in analysis.get("facts", []):
        if f["category"] != "saving":
            story.append(Paragraph("• " + _esc(f['text']), body))

    if analysis.get("categories"):
        story.append(Paragraph("Breakdown by category", h2))
        rows = [["Category", "kWh", "Share"] + ([f"Cost ({cur})"] if "cost" in analysis["categories"][0] else [])]
        for c in analysis["categories"][:20]:
            rows.append([c["category"], _n(c["kwh"]), f"{_n(c['share_pct'], 1)}%"] + ([_n(c.get("cost"))] if "cost" in c else []))
        story.append(_table(rows))

    if analysis.get("anomalies"):
        story.append(Paragraph("Unusual days", h2))
        rows = [["Date", "kWh", "Typical day", "Deviation"]]
        for a in analysis["anomalies"][:15]:
            rows.append([a["date"], _n(a["kwh"]), _n(a["typical_kwh"]), f"{_n(a['deviation_pct'], 1)}%"])
        story.append(_table(rows, [40 * mm, 30 * mm, 30 * mm, 30 * mm]))

    if analysis.get("savings"):
        story.append(Paragraph("Savings scenarios", h2))
        rows = [["Scenario", "kWh", f"{cur}", "Basis"]]
        for sv in analysis["savings"]:
            rows.append([Paragraph(_esc(sv["title"]), body), _n(sv["kwh"]), _n(sv.get("cost")), Paragraph(_esc(sv["basis"]), small)])
        story.append(_table(rows, [52 * mm, 22 * mm, 22 * mm, 78 * mm]))

    recs = (insights or {}).get("recommendations") or []
    if recs and insights.get("source") == "groq":
        story.append(Paragraph("Recommendations", h2))
        for rec in recs:
            story.append(Paragraph(f"• <b>{_esc(str(rec.get('action', '')))}</b> — {_esc(str(rec.get('why', '')))}", body))

    if cleaning_log:
        story.append(Paragraph("Data cleaning applied", h2))
        rows = [["Step", "Rows before", "Rows after", "Detail"]]
        for l in cleaning_log:
            rows.append([Paragraph(_esc(l["title"]), body), l["rows_before"], l["rows_after"], Paragraph(_esc(l["detail"]), small)])
        story.append(_table(rows, [50 * mm, 22 * mm, 22 * mm, 80 * mm]))

    doc.build(story)
    return buf.getvalue()
