"""Data-quality issue detection (SPEC §10.1, codes Q01–Q16) and format-consistency inputs for the score.

Runs in the worker together with profiling, so it can use the per-cell classification. Every count is
exact. Example rows are given as spreadsheet row numbers (header row + data offset) so users can find them.
Q02 (duplicates by chosen key columns) is not automatic: it needs the user's choice of key columns and is
checked in the Cleaning Studio.
"""

from __future__ import annotations

import re
from collections import defaultdict
from typing import Any

import numpy as np
import pandas as pd

from .values import ColumnValues

SEVERITY_ORDER = {"high": 0, "medium": 1, "low": 2}
CATEGORY_VARIANT_MAX_DISTINCT = 200
EXAMPLES = 5

PII_NAME = re.compile(
    r"(?i)\b(cnic|nic|national\s*id|passport|phone|mobile|cell(?:\s*no)?|contact\s*no|e-?mail|patient|mrn|"
    r"medical\s*record|member\s*(?:id|no)|policy\s*holder|address|dob|date\s*of\s*birth|father|full\s*name|"
    r"customer\s*name|employee\s*name|(?<!file\s)(?<!sheet\s)(?<!product\s)(?<!company\s)(?<!branch\s)name)\b"
)
PII_PATTERNS = {
    "CNIC number": re.compile(r"\d{5}-?\d{7}-?\d"),
    "email address": re.compile(r"[^@\s]+@[^@\s]+\.[A-Za-z]{2,}"),
    "Pakistani mobile number": re.compile(r"(?:\+92|0092|92|0)?-?3\d{2}-?\d{7}"),
}

ACTIONS = {
    "Q01": ("remove_exact_duplicates", "Remove exact duplicate rows"),
    "Q03": ("handle_missing", "Choose how to handle missing values"),
    "Q04r": ("remove_empty_rows", "Remove completely empty rows"),
    "Q04c": ("remove_columns", "Remove the empty column"),
    "Q05": ("trim_whitespace", "Trim whitespace"),
    "Q06": ("normalize_spaces", "Normalise repeated spaces"),
    "Q07": ("normalize_categories", "Normalise category labels"),
    "Q08": ("convert_numeric", "Convert numeric text to numbers"),
    "Q09": ("flag_types", "Flag inconsistent data types"),
    "Q10": ("normalize_dates", "Normalise date formats"),
    "Q11": ("normalize_dates", "Choose how to read ambiguous dates"),
    "Q12": ("identify_invalid_dates", "Identify invalid dates"),
    "Q13": ("flag_outliers", "Flag possible outliers"),
    "Q14": ("rename_columns", "Rename the column"),
    "Q15": (None, "Open the file in Excel, recalculate (F9), save, and upload again"),
    "Q16": ("mark_sensitive", "Mark the column as sensitive"),
}


def _excel_row(i: int, header_row: int) -> int:
    return int(i) + header_row + 2


def _show(v: Any) -> str:
    from ..ingest.workbook import display_value

    return "(empty)" if v is None else display_value(v)


def _mask_pii(text: str) -> str:
    if len(text) <= 4:
        return "*" * len(text)
    return text[:2] + re.sub(r"[A-Za-z0-9]", "*", text[2:-1]) + text[-1]


class _Collector:
    def __init__(self, n_rows: int, header_row: int):
        self.items: list[dict[str, Any]] = []
        self.n_rows, self.header_row = n_rows, header_row

    def add(
        self,
        code: str,
        title: str,
        column: str | None,
        affected: int,
        severity: str,
        description: str,
        examples: list[dict[str, Any]] | None = None,
        action_key: str | None = None,
        details: dict[str, Any] | None = None,
    ) -> None:
        if affected <= 0:
            return
        op, label = ACTIONS.get(action_key or code, (None, ""))
        self.items.append(
            {
                "id": f"{code}:{column if column is not None else '*'}",
                "code": code,
                "title": title,
                "column": column,
                "affected_rows": int(affected),
                "affected_pct": round(affected / self.n_rows * 100, 2) if self.n_rows else 0.0,
                "severity": severity,
                "description": description,
                "examples": examples or [],
                "suggested_action": {"operation": op, "label": label},
                "details": details or {},
            }
        )

    def examples_at(self, series: pd.Series, mask: np.ndarray | pd.Series, mask_values: bool = False) -> list[dict]:
        idx = np.flatnonzero(np.asarray(mask))[:EXAMPLES]
        out = []
        for i in idx:
            v = _show(series.iloc[i])
            out.append({"row": _excel_row(i, self.header_row), "value": _mask_pii(v) if mask_values else v})
        return out


def _variant_groups(counts: pd.Series) -> tuple[dict[str, str], dict[str, list[tuple[str, int]]]]:
    """Distinct labels (index) with their row counts (values) that become equal after trimming, collapsing
    spaces and case-folding. Returns (label → dominant spelling) for non-dominant labels, and the groups."""
    groups: dict[str, list[tuple[str, int]]] = defaultdict(list)
    for label, c in counts.items():
        key = re.sub(r"\s+", " ", str(label)).strip().casefold()
        if key:
            groups[key].append((str(label), int(c)))
    non_dominant: dict[str, str] = {}
    variant_groups = {}
    for key, members in groups.items():
        if len(members) > 1:
            # Most frequent spelling wins; ties prefer no edge spaces, then Title Case, then alphabetical.
            members.sort(key=lambda m: (-m[1], m[0] != m[0].strip(), not m[0].strip().istitle(), m[0]))
            dominant = members[0][0]
            variant_groups[key] = members
            for label, _ in members[1:]:
                non_dominant[label] = dominant
    return non_dominant, variant_groups


def detect(
    df: pd.DataFrame, classified: dict[str, ColumnValues], profiles: list[dict[str, Any]], context: dict[str, Any]
) -> list[dict[str, Any]]:
    """Find issues and attach `format` (canonical counts for the health score) to each column profile."""
    n = len(df)
    header_row = int(context.get("header_row", 0))
    is_csv = context.get("file_type") == "csv"
    col = _Collector(n, header_row)
    by_name = {p["name"]: p for p in profiles}

    # ---------- dataset-level ----------
    if n:
        dup_mask = df.duplicated(keep="first").to_numpy()
        dups = int(dup_mask.sum())
        col.add(
            "Q01",
            "Exact duplicate rows",
            None,
            dups,
            "high" if dups > 0.01 * n else "medium",
            "These rows are identical to an earlier row in every column, so totals and counts include them twice.",
            [
                {"row": _excel_row(i, header_row), "value": " | ".join(_show(v) for v in df.iloc[i, :3])}
                for i in np.flatnonzero(dup_mask)[:EXAMPLES]
            ],
        )
        missing_matrix = (
            np.column_stack([classified[c].missing.to_numpy() for c in df.columns]) if len(df.columns) else None
        )
        if missing_matrix is not None:
            empty_rows = missing_matrix.all(axis=1)
            col.add(
                "Q04",
                "Completely empty rows",
                None,
                int(empty_rows.sum()),
                "low",
                "Rows with no values in any column.",
                [
                    {"row": _excel_row(i, header_row), "value": "(empty row)"}
                    for i in np.flatnonzero(empty_rows)[:EXAMPLES]
                ],
                action_key="Q04r",
            )
    for change in context.get("header_changes", []):
        if change["reason"] in ("blank", "duplicate"):
            what = "had no name" if change["reason"] == "blank" else f"repeated the name “{change['original']}”"
            col.add(
                "Q14",
                "Blank or duplicate column header",
                change["new"],
                n or 1,
                "low",
                f"Column {change['position']} {what}; it was named “{change['new']}”. "
                "Rename it to something meaningful.",
                details={"position": change["position"], "reason": change["reason"]},
            )
    formula_missing = int(context.get("formula_cells_without_cache", 0))
    if formula_missing:
        col.add(
            "Q15",
            "Formulas without saved results",
            None,
            formula_missing,
            "medium",
            f"{formula_missing} formula cell(s) in this sheet have no saved result, so they appear empty here. "
            "DataDoctor never calculates formulas.",
            details={"unit": "cells"},
        )

    # ---------- per column ----------
    for name in df.columns:
        name = str(name)
        series = df[name]
        cv = classified[name]
        prof = by_name[name]
        present = ~cv.missing.to_numpy()
        non_missing = int(present.sum())
        fmt = {"applicable": False, "canonical": non_missing, "canonical_if_dates_resolved": non_missing}
        prof["format"] = fmt
        if non_missing == 0:
            if n:
                col.add("Q04", "Empty column", name, n, "low", "This column has no values at all.", action_key="Q04c")
            continue

        family = prof.get("family")
        missing = n - non_missing
        if missing:
            pct = missing / n * 100
            kinds = prof["missing_kinds"]
            names = {
                "empty": ("empty cell", "empty cells"),
                "whitespace_only": ("cell with only spaces", "cells with only spaces"),
                "null_token": ("placeholder like N/A", "placeholders like N/A"),
                "excel_error": ("Excel error", "Excel errors"),
            }
            parts = [f"{v} {names[k][0] if v == 1 else names[k][1]}" for k, v in kinds.items() if v]
            col.add(
                "Q03",
                "Missing values",
                name,
                missing,
                "high" if pct > 20 else "medium" if pct >= 5 else "low",
                f"{pct:.1f}% of rows have no value ({', '.join(parts)}). DataDoctor never fills them in "
                "unless you choose how.",
                col.examples_at(series, ~present),
                details={"kinds": kinds},
            )

        # String rows, analysed per distinct value (codes/uniques come from classification).
        has_strs = cv.str_index is not None and len(cv.str_index) > 0
        if has_strs:
            u_present = np.zeros(len(cv.str_uniques), dtype=bool)
            u_present[cv.str_codes[present[cv.str_index]]] = True
            u_counts = np.bincount(cv.str_codes[present[cv.str_index]], minlength=len(cv.str_uniques))

        # Q05 / Q06 whitespace (masks already computed per distinct value)
        edge = cv.edge_ws.to_numpy() & present
        rep = cv.repeated_ws.to_numpy() & present

        # Q07 variants (text-like columns with a manageable number of labels)
        variant_rows = np.zeros(n, dtype=bool)
        if family == "text" and has_strs and 0 < u_present.sum() <= CATEGORY_VARIANT_MAX_DISTINCT:
            labels = pd.Series(np.repeat(cv.str_uniques[u_present], 1), index=np.flatnonzero(u_present), dtype=object)
            label_counts = pd.Series(u_counts[u_present], index=labels.to_numpy())
            non_dom, groups = _variant_groups(label_counts)
            if non_dom:
                u_variant = np.array([str(u) in non_dom for u in cv.str_uniques], dtype=bool)
                variant_rows[cv.str_index] = u_variant[cv.str_codes] & present[cv.str_index]
                ex = [
                    {"row": None, "value": " / ".join(f"“{lbl}” ({c})" for lbl, c in members[:4])}
                    for members in list(groups.values())[:EXAMPLES]
                ]
                col.add(
                    "Q07",
                    "Inconsistent category labels",
                    name,
                    int(variant_rows.sum()),
                    "medium",
                    f"{len(groups)} label(s) are spelled in more than one way (differences in capitals or spaces). "
                    "Each would be counted as a separate category.",
                    ex,
                    details={"groups": len(groups)},
                )
        splits = family == "text" and bool((edge & variant_rows).any())
        col.add(
            "Q05",
            "Leading or trailing spaces",
            name,
            int(edge.sum()),
            "medium" if splits else "low",
            "Values start or end with spaces" + (", which splits some categories in two." if splits else "."),
            col.examples_at(series, edge),
        )
        col.add(
            "Q06",
            "Repeated spaces inside values",
            name,
            int(rep.sum()),
            "low",
            "Values contain two or more spaces in a row.",
            col.examples_at(series, rep),
        )

        # Q08 numbers stored as text
        classes = cv.classes.to_numpy()
        if family == "number":
            numeric_share = prof["family_counts"].get("number", 0) / non_missing
            text_nums = classes == "numeric_text"
            if is_csv:  # in a CSV every value is text; only formatted numbers need converting
                formatted = text_nums.copy()
                plain_idx = np.flatnonzero(text_nums)
                plain = series.iloc[plain_idx].map(lambda v: bool(re.fullmatch(r"-?\d+(?:\.\d+)?", str(v).strip())))
                formatted[plain_idx[plain.to_numpy()]] = False
                to_convert = formatted
            else:
                to_convert = text_nums
            if numeric_share >= 0.8:
                col.add(
                    "Q08",
                    "Numbers stored as text",
                    name,
                    int(to_convert.sum()),
                    "medium",
                    "These look like numbers but are stored as text (currency symbols, separators, brackets or %), "
                    "so they cannot be added up or averaged until converted.",
                    col.examples_at(series, to_convert),
                )
            fmt.update(applicable=True, canonical=int(non_missing - to_convert.sum()))
            fmt["canonical_if_dates_resolved"] = fmt["canonical"]

        # Q09 mixed types
        if prof.get("mixed"):
            fam_of = {
                "native_number": "number",
                "numeric_text": "number",
                "native_date": "date",
                "date_text": "date",
                "native_bool": "boolean",
                "bool_text": "boolean",
                "text": "text",
                "other": "other",
            }
            off = np.array([fam_of.get(c, "") != family for c in classes]) & present
            col.add(
                "Q09",
                "Mixed data types",
                name,
                int(off.sum()),
                "medium",
                f"Most values are {family}, but {int(off.sum())} are a different kind of value.",
                col.examples_at(series, off),
                details={"consistency": prof.get("consistency")},
            )

        # Q10 / Q11 / Q12 dates
        if family == "date":
            d = prof["date"]
            fmts = dict(d["formats"])
            if d["native"]:
                fmts["Excel date"] = d["native"]
            dominant = max(fmts, key=fmts.get) if fmts else None
            amb_in_dom = cv.date_ambiguous_by_format.get(dominant, 0) if dominant else 0
            fmt.update(
                applicable=True,
                canonical=int(fmts.get(dominant, 0) - amb_in_dom),
                canonical_if_dates_resolved=int(fmts.get(dominant, 0)),
                dominant_format=dominant,
            )
            if len(fmts) > 1:
                outside = int(sum(fmts.values()) - fmts[dominant])
                col.add(
                    "Q10",
                    "Several date formats",
                    name,
                    outside,
                    "medium",
                    f"Dates are written in {len(fmts)} formats: "
                    + ", ".join(f"{k} ({v})" for k, v in sorted(fmts.items(), key=lambda x: -x[1]))
                    + ".",
                    details={"formats": fmts},
                )
            if d["ambiguous"]:
                ev = d["evidence"]
                col.add(
                    "Q11",
                    "Ambiguous dates",
                    name,
                    d["ambiguous"],
                    "high",
                    f"{d['ambiguous']} date(s) such as 03/04/2026 could mean 3 April or 4 March. "
                    f"Evidence in this column: {ev.get('dmy_only', 0)} value(s) only make sense as DD/MM, "
                    f"{ev.get('mdy_only', 0)} only as MM/DD. You will be asked which one applies; "
                    "DataDoctor never guesses.",
                    details={"evidence": ev},
                )
            if d["invalid"]:
                col.add(
                    "Q12",
                    "Invalid dates",
                    name,
                    d["invalid"],
                    "medium",
                    "These look like dates but are impossible under any reading (for example 31/02/2026).",
                )

        # Q13 outliers
        if family == "number":
            nums = cv.numbers.to_numpy()
            valid = ~np.isnan(nums)
            if valid.sum() >= 20:
                q1, q3 = np.quantile(nums[valid], [0.25, 0.75])
                iqr = q3 - q1
                if iqr > 0:
                    lo, hi = q1 - 3 * iqr, q3 + 3 * iqr
                    out = valid & ((nums < lo) | (nums > hi))
                    col.add(
                        "Q13",
                        "Possible outliers",
                        name,
                        int(out.sum()),
                        "low",
                        f"Values far outside the typical range ({lo:,.2f} to {hi:,.2f}, 3× the interquartile "
                        "range). They may be errors or genuine; nothing is removed automatically.",
                        col.examples_at(series, out),
                        details={"lower": float(lo), "upper": float(hi)},
                    )

        # Text-like format consistency for the score
        if family == "text":
            non_canonical = edge | rep | variant_rows
            fmt.update(applicable=True, canonical=int(non_missing - non_canonical.sum()))
            fmt["canonical_if_dates_resolved"] = fmt["canonical"]

        # Q16 personal identifiers
        reasons = []
        if PII_NAME.search(name):
            reasons.append("the column name")
        if has_strs and u_present.any():
            uniq = pd.Series(cv.str_uniques[u_present], dtype=object).astype(str).str.strip()
            weights = u_counts[u_present]
            total_str = int(weights.sum())
            for label, pat in PII_PATTERNS.items():
                hits = int(weights[uniq.str.fullmatch(pat).to_numpy()].sum())
                if hits >= 3 and hits >= 0.5 * total_str:
                    reasons.append(f"values that look like a {label}")
                    break
        if reasons:
            col.add(
                "Q16",
                "Possible personal information",
                name,
                non_missing,
                "medium",
                f"Flagged because of {' and '.join(reasons)}. Mark it as sensitive to keep its name and values away "
                "from AI features.",
                col.examples_at(series, present, mask_values=True),
                details={"reasons": reasons},
            )

    col.items.sort(key=lambda i: (SEVERITY_ORDER[i["severity"]], -i["affected_rows"]))
    return col.items
