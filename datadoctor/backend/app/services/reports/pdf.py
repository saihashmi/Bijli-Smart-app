"""PDF report (SPEC FR-6.2). Every figure is passed in already computed by the profile or the analytics engine;
this module only lays them out. Text from the data is escaped before it reaches the page."""

from __future__ import annotations

from pathlib import Path
from typing import Any
from xml.sax.saxutils import escape

from reportlab.graphics.charts.barcharts import VerticalBarChart
from reportlab.graphics.charts.linecharts import HorizontalLineChart
from reportlab.graphics.shapes import Drawing, String
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import KeepTogether, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

NAVY = colors.HexColor("#0B1F3A")
BLUE = colors.HexColor("#2563EB")
GREY = colors.HexColor("#475569")
LINE = colors.HexColor("#E2E8F0")
SOFT = colors.HexColor("#F1F5F9")
MAX_CHARTS = 8
MAX_ISSUES = 40
MAX_STEPS = 60
MAX_COLUMNS = 60

_styles = getSampleStyleSheet()
H1 = ParagraphStyle("H1", parent=_styles["Title"], textColor=NAVY, fontSize=22, leading=26, alignment=0, spaceAfter=4)
H2 = ParagraphStyle(
    "H2", parent=_styles["Heading2"], textColor=NAVY, fontSize=13, leading=16, spaceBefore=12, spaceAfter=6
)
BODY = ParagraphStyle("Body", parent=_styles["BodyText"], fontSize=9.5, leading=13)
SMALL = ParagraphStyle("Small", parent=BODY, fontSize=8, leading=10.5, textColor=GREY)
CELL = ParagraphStyle("Cell", parent=BODY, fontSize=8, leading=10)
CELL_HEAD = ParagraphStyle("CellHead", parent=CELL, textColor=colors.white, fontName="Helvetica-Bold")


def _latin(text: Any) -> str:
    """The built-in PDF fonts cover Latin text only; other characters are shown as '?' rather than blank boxes."""
    return str(text).encode("cp1252", "replace").decode("cp1252")


def P(text: Any, style: ParagraphStyle = BODY) -> Paragraph:
    return Paragraph(escape(_latin(text)), style)


def fmt(v: Any) -> str:
    if v is None or v == "":
        return "–"
    if isinstance(v, bool):
        return str(v)
    if isinstance(v, (int, float)):
        return f"{int(v):,}" if float(v).is_integer() else f"{v:,.2f}"
    return str(v)


def _table(head: list[str], rows: list[list[Any]], widths: list[float]) -> Table:
    data = [[P(h, CELL_HEAD) for h in head]] + [[P(fmt(c), CELL) for c in r] for r in rows]
    t = Table(data, colWidths=[w * mm for w in widths], repeatRows=1)
    t.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), NAVY),
                ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, SOFT]),
                ("GRID", (0, 0), (-1, -1), 0.25, LINE),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("TOPPADDING", (0, 0), (-1, -1), 3),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
            ]
        )
    )
    return t


def _chart(widget: dict[str, Any]) -> Drawing | None:
    """A simple bar or line drawing of an already computed result. Returns None when it cannot be drawn honestly."""
    res = widget["result"]
    if res["kind"] == "histogram":
        labels = [fmt(b["start"]) for b in res["bins"]]
        values = [b["count"] for b in res["bins"]]
        kind = "bar"
    elif res["kind"] == "aggregate" and res["dimension"] and not res["series"]:
        rows = [r for r in res["rows"] if isinstance(r["value"], (int, float))][:30]
        labels = [_latin(r["label"])[:14] for r in rows]
        values = [r["value"] for r in rows]
        kind = "line" if widget["chart"] in ("line", "area") else "bar"
    else:
        return None
    if not values:
        return None
    d = Drawing(170 * mm, 62 * mm)
    chart: Any = HorizontalLineChart() if kind == "line" else VerticalBarChart()
    chart.x, chart.y, chart.width, chart.height = 14 * mm, 12 * mm, 150 * mm, 44 * mm
    chart.data = [values]
    chart.categoryAxis.categoryNames = labels
    chart.categoryAxis.labels.fontSize = 6
    chart.categoryAxis.labels.fontName = "Helvetica"
    chart.valueAxis.labels.fontName = "Helvetica"
    chart.categoryAxis.labels.angle = 30 if len(labels) > 8 else 0
    chart.categoryAxis.labels.boxAnchor = "ne" if len(labels) > 8 else "n"
    if len(labels) > 16:  # thin out crowded labels
        step = len(labels) // 12 + 1
        chart.categoryAxis.categoryNames = [name if i % step == 0 else "" for i, name in enumerate(labels)]
    chart.valueAxis.labels.fontSize = 6
    chart.valueAxis.labelTextFormat = lambda v: fmt(v)
    chart.valueAxis.gridStrokeColor = LINE
    chart.valueAxis.visibleGrid = True
    low, high = min(values), max(values)
    chart.valueAxis.valueMin = min(0, low)
    chart.valueAxis.valueMax = high * 1.08 if high > 0 else 1
    if kind == "line":
        chart.lines[0].strokeColor = BLUE
        chart.lines[0].strokeWidth = 1.5
    else:
        chart.bars[0].fillColor = BLUE
        chart.bars[0].strokeColor = None
    d.add(chart)
    d.add(String(0, 58 * mm, "", fontSize=1))
    return d


def build_pdf(ctx: dict[str, Any], out: Path) -> dict[str, Any]:
    profile, health = ctx["profile"], ctx["profile"]["health"]
    story: list[Any] = []

    story += [P("Data Report", H1), P(ctx["filename"], ParagraphStyle("Sub", parent=BODY, fontSize=12, textColor=GREY))]
    story += [
        Spacer(1, 3 * mm),
        P(
            f"Generated {ctx['generated_at']} by DataDoctor AI. Sheet “{ctx['sheet_name']}”, data version {ctx['version']}.",
            SMALL,
        ),
    ]
    story.append(P("All figures in this report were calculated from the uploaded file. Nothing is estimated.", SMALL))

    story.append(P("Dataset summary", H2))
    story.append(
        _table(
            ["Rows", "Columns", "Missing cells", "Exact duplicate rows", "Empty rows", "Cleaning steps applied"],
            [
                [
                    profile["rows"],
                    profile["columns"],
                    f"{fmt(profile['missing_cells'])} ({profile['missing_pct']}%)",
                    profile["duplicate_rows"],
                    profile["empty_rows"],
                    ctx["active_steps"],
                ]
            ],
            [25, 25, 35, 35, 25, 35],
        )
    )

    story.append(P("Data Health Score", H2))
    story.append(Paragraph(f"<b>{health['score']} out of 100</b> ({escape(_latin(health['band']))})", BODY))
    story.append(P(health["formula"], SMALL))
    story.append(Spacer(1, 2 * mm))
    story.append(
        _table(
            ["Component", "Value (0–1)", "Weight", "Points", "How it is measured"],
            [
                [c["key"].replace("_", " ").capitalize(), c["value"], c["weight"], c["points"], c["explanation"]]
                for c in health["components"]
            ],
            [34, 20, 16, 16, 94],
        )
    )
    for line in health.get("limitations", []):
        story.append(P(line, SMALL))

    story.append(P("Key statistics by column", H2))
    cols = profile["column_profiles"]
    rows = []
    for c in cols[:MAX_COLUMNS]:
        n, d = c.get("numeric") or {}, c.get("date") or {}
        rows.append(
            [
                c["name"],
                c["type"],
                c["non_missing"],
                c["missing"],
                c["unique"],
                n.get("min") if n else (d.get("min") or "")[:10],
                n.get("max") if n else (d.get("max") or "")[:10],
                n.get("mean"),
                n.get("median"),
            ]
        )
    story.append(
        _table(
            ["Column", "Type", "Filled", "Missing", "Distinct", "Minimum", "Maximum", "Average", "Median"],
            rows,
            [32, 16, 16, 16, 16, 21, 23, 20, 20],
        )
    )
    if len(cols) > MAX_COLUMNS:
        story.append(
            P(f"Showing the first {MAX_COLUMNS} of {len(cols)} columns. The Excel export lists all of them.", SMALL)
        )

    story.append(P("Data-quality findings", H2))
    issues = profile["issues"]
    if issues:
        story.append(
            _table(
                ["Issue", "Column", "Rows", "Severity", "Suggested fix"],
                [
                    [
                        i["title"],
                        i["column"] or "(whole sheet)",
                        i["affected_rows"],
                        i["severity"],
                        i["suggested_action"]["label"] or "Review manually",
                    ]
                    for i in issues[:MAX_ISSUES]
                ],
                [52, 38, 16, 18, 56],
            )
        )
        if len(issues) > MAX_ISSUES:
            story.append(
                P(f"Showing {MAX_ISSUES} of {len(issues)} findings. The Excel export lists all of them.", SMALL)
            )
    else:
        story.append(P("No data-quality issues were found."))

    story.append(P("Cleaning summary", H2))
    ops = ctx["operations"]
    if ops:
        story.append(P("The original upload is unchanged. These steps were applied to a working copy, in this order."))
        story.append(Spacer(1, 2 * mm))
        story.append(
            _table(
                ["Step", "Operation", "Settings", "Rows affected", "Status", "Applied at"],
                [
                    [o["sequence"], o["title"], o["parameters"][:160], o["affected_rows"], o["status"], o["created_at"]]
                    for o in ops[:MAX_STEPS]
                ],
                [10, 40, 62, 20, 16, 32],
            )
        )
    else:
        story.append(P("No cleaning steps were applied. The figures describe the data as uploaded."))

    widgets = ctx.get("widgets") or []
    skipped: list[str] = []
    if widgets:
        story.append(P("Dashboard", H2))
        if ctx.get("dashboard_filters"):
            story.append(P("Dashboard filters applied: " + "; ".join(ctx["dashboard_filters"]) + ".", SMALL))
        kpis = [w for w in widgets if w["chart"] == "kpi"]
        if kpis:
            story.append(
                _table(
                    ["Figure", "Value", "Based on"],
                    [
                        [w["title"], w["result"]["total"]["value"], f"{fmt(w['result']['total']['n'])} values"]
                        for w in kpis
                    ],
                    [70, 50, 60],
                )
            )
        drawn = 0
        for w in widgets:
            if w["chart"] == "kpi":
                continue
            drawing = _chart(w) if drawn < MAX_CHARTS else None
            if drawing is None:
                skipped.append(w["title"])
                continue
            drawn += 1
            block = [
                Spacer(1, 4 * mm),
                P(w["title"], ParagraphStyle("W", parent=BODY, fontName="Helvetica-Bold")),
                drawing,
            ]
            block += [P(n, SMALL) for n in w.get("notes", [])]
            story.append(KeepTogether(block))
        if skipped:
            story.append(Spacer(1, 3 * mm))
            story.append(
                P(
                    "Not drawn in this report (see the app or save them as images there): " + "; ".join(skipped) + ".",
                    SMALL,
                )
            )

    answers = ctx.get("answers") or []
    if answers:
        story.append(P("Answers from the AI Analyst", H2))
        story.append(
            P("These answers were calculated from the data by fixed calculations. They are not AI-written text.", SMALL)
        )
        story.append(Spacer(1, 2 * mm))
        story.append(
            _table(["Question", "Computed answer"], [[a["question"], a["summary"]] for a in answers], [60, 120])
        )

    def footer(canvas: Any, doc: Any) -> None:
        canvas.saveState()
        canvas.setFont("Helvetica", 7.5)
        canvas.setFillColor(GREY)
        canvas.drawString(
            15 * mm, 9 * mm, _latin(f"DataDoctor AI · {ctx['filename']} · generated {ctx['generated_at']}")[:130]
        )
        canvas.drawRightString(195 * mm, 9 * mm, f"Page {doc.page}")
        canvas.restoreState()

    doc = SimpleDocTemplate(
        str(out),
        pagesize=A4,
        leftMargin=15 * mm,
        rightMargin=15 * mm,
        topMargin=15 * mm,
        bottomMargin=16 * mm,
        title=_latin(f"Data Report: {ctx['filename']}"),
        author="DataDoctor AI",
    )
    doc.build(story, onFirstPage=footer, onLaterPages=footer)
    return {
        "pages": doc.page,
        "charts": sum(1 for w in widgets if w["chart"] != "kpi") - len(skipped),
        "size": out.stat().st_size,
    }
