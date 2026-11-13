"""Typed views of snapshot columns for analytics.

Snapshots keep raw cell values (mixed types). Analytics needs numbers, dates and group labels, and uses exactly
the same per-cell classification as profiling (`profiling.values.classify`), so a figure on a dashboard always
agrees with what the Data Health Center says about the column. Nothing is guessed: text that is not a number is
not counted as zero, an ambiguous date is not placed in a month. Such cells are left out and counted.
"""

from __future__ import annotations

import threading
from collections import OrderedDict
from dataclasses import dataclass

import numpy as np
import pandas as pd

from ..ingest.workbook import display_value
from ..profiling.profile import CATEGORY_MAX_UNIQUE, FAMILY
from ..profiling.values import classify

MISSING_LABEL = "(missing)"


@dataclass
class TypedColumn:
    name: str
    kind: str  # number | date | boolean | category | text | empty | other
    n: int
    missing: np.ndarray  # bool per row
    numbers: np.ndarray  # float per row, NaN where the cell is not a number
    dates: np.ndarray  # datetime64[ns] per row, NaT where the cell is not an unambiguous date
    codes: np.ndarray  # int per row: index into `labels`, -1 where missing
    labels: list[str]  # display text of each distinct raw value
    unique: int
    not_numeric: int  # present cells that are not numbers
    not_dated: int  # present cells that are not usable dates (text, ambiguous or impossible dates)
    has_time: bool


def build(name: str, series: pd.Series) -> TypedColumn:
    cv = classify(series)
    missing = cv.missing.to_numpy(dtype=bool)
    present = ~missing
    n_present = int(present.sum())

    family_counts: dict[str, int] = {}
    for cls, cnt in cv.classes[cv.classes != ""].value_counts().items():
        fam = FAMILY.get(cls, "other")
        family_counts[fam] = family_counts.get(fam, 0) + int(cnt)

    codes = np.full(len(series), -1, dtype=np.int64)
    labels: list[str] = []
    if n_present:
        raw_codes, uniques = pd.factorize(series[present], use_na_sentinel=True)
        # Two raw values can share one display text (1 and 1.0); merge them so a label appears once.
        merged: dict[str, int] = {}
        remap = np.empty(len(uniques), dtype=np.int64)
        for i, u in enumerate(uniques):
            text = display_value(u)
            remap[i] = merged.setdefault(text, len(merged))
        labels = list(merged)
        codes[present] = np.where(raw_codes >= 0, remap[raw_codes], -1)

    numbers = cv.numbers.to_numpy(dtype=float)
    dates = cv.dates.to_numpy(dtype="datetime64[ns]")
    unique = len(labels)

    if n_present == 0:
        kind = "empty"
    else:
        family = max(family_counts, key=lambda f: (family_counts[f], f == "text"))
        if family in ("number", "date", "boolean", "other"):
            kind = family
        else:
            kind = "category" if unique <= CATEGORY_MAX_UNIQUE and unique <= 0.8 * n_present else "text"

    return TypedColumn(
        name=name,
        kind=kind,
        n=len(series),
        missing=missing,
        numbers=numbers,
        dates=dates,
        codes=codes,
        labels=labels,
        unique=unique,
        not_numeric=int((present & np.isnan(numbers)).sum()),
        not_dated=int((present & np.isnat(dates)).sum()),
        has_time=cv.has_time,
    )


class TypedFrame:
    """Lazily typed columns of one snapshot. Safe to share between request threads."""

    def __init__(self, df: pd.DataFrame):
        self.df = df
        self.columns = [str(c) for c in df.columns]
        self._cols: dict[str, TypedColumn] = {}
        self._lock = threading.Lock()

    def __len__(self) -> int:
        return len(self.df)

    def has(self, name: str) -> bool:
        return name in self.columns

    def col(self, name: str) -> TypedColumn:
        with self._lock:
            got = self._cols.get(name)
        if got is None:
            got = build(name, self.df[name])
            with self._lock:
                self._cols.setdefault(name, got)
        return got


_CACHE: OrderedDict[int, tuple[pd.DataFrame, TypedFrame]] = OrderedDict()
_CACHE_LOCK = threading.Lock()
_CACHE_SIZE = 2


def typed(df: pd.DataFrame) -> TypedFrame:
    """Typed view for a cached snapshot frame (keyed by the frame object, which `snapshots.load` reuses)."""
    key = id(df)
    with _CACHE_LOCK:
        hit = _CACHE.get(key)
        if hit is not None and hit[0] is df:
            _CACHE.move_to_end(key)
            return hit[1]
        tf = TypedFrame(df)
        _CACHE[key] = (df, tf)
        while len(_CACHE) > _CACHE_SIZE:
            _CACHE.popitem(last=False)
        return tf
