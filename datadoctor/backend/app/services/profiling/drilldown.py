"""Row-level views of the data: which rows an issue affects, and per-cell flags for the grid.

Masks are recomputed from the current snapshot with the same classification the issue detector uses, so
the row list for an issue always has exactly as many rows as the issue reports (covered by tests).
"""

from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd

from .issues import CATEGORY_VARIANT_MAX_DISTINCT, _variant_groups
from .profile import FAMILY
from .values import _PLAIN_NUMBER, ColumnValues, classify

NO_ROW_VIEW = {"Q14", "Q15"}  # header and formula issues are not about particular data rows


def _family(cv: ColumnValues) -> str | None:
    present = ~cv.missing.to_numpy()
    if not present.any():
        return None
    counts: dict[str, int] = {}
    for cls, n in cv.classes[present].value_counts().items():
        fam = FAMILY.get(cls, "other")
        counts[fam] = counts.get(fam, 0) + int(n)
    return max(counts, key=lambda f: (counts[f], f == "text"))


def issue_mask(df: pd.DataFrame, code: str, column: str | None, context: dict[str, Any]) -> np.ndarray:
    """Boolean mask over df rows affected by the issue. Raises KeyError for unknown code/column."""
    n = len(df)
    if code == "Q01":
        return df.duplicated(keep="first").to_numpy()
    if code == "Q04" and column is None:
        if df.shape[1] == 0:
            return np.zeros(n, dtype=bool)
        return np.column_stack([classify(df[c]).missing.to_numpy() for c in df.columns]).all(axis=1)
    if column is None or column not in df.columns:
        raise KeyError(code)

    series = df[column]
    cv = classify(series)
    present = ~cv.missing.to_numpy()
    family = _family(cv)
    classes = cv.classes.to_numpy()

    if code == "Q03":
        return ~present
    if code == "Q04":
        return np.ones(n, dtype=bool)
    if code == "Q05":
        return cv.edge_ws.to_numpy() & present
    if code == "Q06":
        return cv.repeated_ws.to_numpy() & present
    if code == "Q07":
        mask = np.zeros(n, dtype=bool)
        if family == "text" and cv.str_index is not None and len(cv.str_index):
            sel = present[cv.str_index]
            u_present = np.zeros(len(cv.str_uniques), dtype=bool)
            u_present[cv.str_codes[sel]] = True
            if 0 < u_present.sum() <= CATEGORY_VARIANT_MAX_DISTINCT:
                u_counts = np.bincount(cv.str_codes[sel], minlength=len(cv.str_uniques))
                non_dom, _ = _variant_groups(pd.Series(u_counts[u_present], index=cv.str_uniques[u_present]))
                u_variant = np.array([str(u) in non_dom for u in cv.str_uniques], dtype=bool)
                mask[cv.str_index] = u_variant[cv.str_codes] & sel
        return mask
    if code == "Q08":
        text_nums = classes == "numeric_text"
        if context.get("file_type") == "csv":
            idx = np.flatnonzero(text_nums)
            plain = series.iloc[idx].map(lambda v: bool(_PLAIN_NUMBER.fullmatch(str(v).strip()))).to_numpy()
            text_nums = text_nums.copy()
            text_nums[idx[plain]] = False
        return text_nums
    if code == "Q09":
        return np.array([FAMILY.get(c, "") != family for c in classes]) & present
    if code in ("Q10", "Q11", "Q12"):
        if code == "Q11":
            return cv.row_ambiguous & present
        if code == "Q12":
            return cv.row_invalid_date & present
        fmts = pd.Series(cv.row_date_format[present])
        fmts = fmts[fmts != ""]
        if fmts.empty:
            return np.zeros(n, dtype=bool)
        # Same tie-break as the detector: the first format with the highest count in its ordering.
        order = {**cv.date_formats}
        native = int((cv.row_date_format == "Excel date").sum())
        if native:
            order["Excel date"] = native
        dominant = max(order, key=order.get)
        return (cv.row_date_format != "") & (cv.row_date_format != dominant) & present
    if code == "Q13":
        nums = cv.numbers.to_numpy()
        valid = ~np.isnan(nums)
        if valid.sum() < 20:
            return np.zeros(n, dtype=bool)
        q1, q3 = np.quantile(nums[valid], [0.25, 0.75])
        iqr = q3 - q1
        if iqr <= 0:
            return np.zeros(n, dtype=bool)
        return valid & ((nums < q1 - 3 * iqr) | (nums > q3 + 3 * iqr))
    if code == "Q16":
        return present
    raise KeyError(code)


def cell_flags(
    page: pd.DataFrame,
    families: dict[str, str | None],
    duplicate_rows: np.ndarray | None,
    original: pd.DataFrame | None,
    origins: dict[str, str],
) -> tuple[list[list[str]], list[str]]:
    """Flags for one page of rows. Cell flags: "m" missing, "i" invalid date, "c" changed since the original.
    Row flags: "d" exact duplicate of another row."""
    from ..cleaning.ops import _same

    n = len(page)
    grid = [["" for _ in page.columns] for _ in range(n)]
    for j, col in enumerate(page.columns):
        cv = classify(page[col])
        missing = cv.missing.to_numpy()
        invalid = cv.row_invalid_date if families.get(str(col)) == "date" else np.zeros(n, dtype=bool)
        src = origins.get(str(col)) if original is not None else None
        for i in range(n):
            f = ""
            if missing[i]:
                f += "m"
            if invalid[i]:
                f += "i"
            if src is not None:
                label = page.index[i]
                if label in original.index and not _same(original.at[label, src], page.iat[i, j]):
                    f += "c"
            grid[i][j] = f
    rows = ["d" if duplicate_rows is not None and duplicate_rows[i] else "" for i in range(n)]
    return grid, rows


_DUP_CACHE: dict[tuple[str, float], np.ndarray] = {}


def duplicate_mask(df: pd.DataFrame, cache_key: tuple[str, float]) -> np.ndarray:
    """Rows that are exact copies of another row (all occurrences), cached per snapshot file."""
    if cache_key not in _DUP_CACHE:
        if len(_DUP_CACHE) >= 4:
            _DUP_CACHE.pop(next(iter(_DUP_CACHE)))
        _DUP_CACHE[cache_key] = df.duplicated(keep=False).to_numpy()
    return _DUP_CACHE[cache_key]
