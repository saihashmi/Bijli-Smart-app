"""Data Health Score (SPEC §10.2) and final issue list. Deterministic; cheap; applied when a profile is served.

Score = round(100 × (0.35·C + 0.20·U + 0.25·T + 0.20·F))
  C completeness       = 1 − missing cells / total cells
  U uniqueness         = 1 − exact duplicate rows / rows
  T type consistency   = mean over non-empty columns of (values matching the column's dominant type / non-missing)
  F format consistency = mean over applicable columns of (values in canonical format / non-missing)
"""

from __future__ import annotations

from typing import Any

WEIGHTS = {"completeness": 0.35, "uniqueness": 0.20, "type_consistency": 0.25, "format_consistency": 0.20}
BANDS = [(90, "Excellent"), (75, "Good"), (50, "Needs attention"), (0, "Poor")]
FORMULA = (
    "Score = round(100 × (0.35 × Completeness + 0.20 × Uniqueness + 0.25 × Type consistency "
    "+ 0.20 × Format consistency))"
)
LIMITATIONS = [
    "The score measures structural quality only: missing values, duplicates, consistent types and formats.",
    "It does not check whether values are true, accurate or complete in a business sense. A file can score 100 "
    "and still contain wrong numbers.",
    "Repeated IDs (key duplicates) and possible outliers do not lower the score, because they may be legitimate.",
    "In CSV files every value is text, so plain numbers such as 1250.5 count as properly stored numbers; only "
    "formatted ones (Rs 1,250 or (250)) count against format consistency.",
]


def band(score: int) -> str:
    return next(label for threshold, label in BANDS if score >= threshold)


def health_score(profile: dict[str, Any], resolved_date_columns: set[str] | None = None) -> dict[str, Any] | None:
    resolved = resolved_date_columns or set()
    rows, total_cells = profile.get("rows", 0), profile.get("total_cells", 0)
    if not rows or not total_cells:
        return None
    cols = profile["column_profiles"]
    completeness = 1 - profile["missing_cells"] / total_cells
    uniqueness = 1 - profile["duplicate_rows"] / rows
    typed = [c for c in cols if c["non_missing"] > 0 and c.get("consistency") is not None]
    type_consistency = sum(c["consistency"] for c in typed) / len(typed) if typed else 1.0
    fmt_cols = [c for c in cols if c.get("format", {}).get("applicable") and c["non_missing"] > 0]
    shares = []
    for c in fmt_cols:
        f = c["format"]
        canonical = f["canonical_if_dates_resolved"] if c["name"] in resolved else f["canonical"]
        shares.append(max(0.0, min(1.0, canonical / c["non_missing"])))
    format_consistency = sum(shares) / len(shares) if shares else 1.0
    values = {
        "completeness": completeness,
        "uniqueness": uniqueness,
        "type_consistency": type_consistency,
        "format_consistency": format_consistency,
    }
    score = round(100 * sum(WEIGHTS[k] * v for k, v in values.items()))
    explain = {
        "completeness": f"{profile['missing_cells']:,} of {total_cells:,} cells are missing.",
        "uniqueness": f"{profile['duplicate_rows']:,} of {rows:,} rows are exact duplicates of an earlier row.",
        "type_consistency": f"Average share of values matching their column's type, over {len(typed)} column(s).",
        "format_consistency": (
            f"Average share of values in their column's standard format, over {len(shares)} column(s)."
            if shares
            else "No columns where format consistency applies; counted as 100%."
        ),
    }
    return {
        "score": score,
        "band": band(score),
        "components": [
            {
                "key": k,
                "value": round(v, 4),
                "weight": WEIGHTS[k],
                "points": round(100 * WEIGHTS[k] * v, 2),
                "explanation": explain[k],
            }
            for k, v in values.items()
        ],
        "formula": FORMULA,
        "limitations": LIMITATIONS,
    }


def finalize(profile: dict[str, Any], sensitive: list[str], date_rules: dict[str, Any]) -> dict[str, Any]:
    """Apply the session's choices (sensitive columns, confirmed date readings) to the stored profile."""
    resolved = {c for c in date_rules.get("columns", {})} if date_rules else set()
    if date_rules and date_rules.get("all_slash_dates"):
        resolved |= {c["name"] for c in profile["column_profiles"] if c.get("family") == "date"}
    issues = []
    for issue in profile.get("issues", []):
        if issue["code"] == "Q16" and issue["column"] in sensitive:
            continue
        if issue["code"] == "Q11" and issue["column"] in resolved:
            continue
        issues.append(issue)
    counts = {"high": 0, "medium": 0, "low": 0}
    for i in issues:
        counts[i["severity"]] += 1
    return {
        **profile,
        "issues": issues,
        "issue_counts": counts,
        "health": health_score(profile, resolved),
        "sensitive_columns": sensitive,
    }
