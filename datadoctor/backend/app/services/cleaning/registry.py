"""Catalogue of cleaning operations: parameters, UI fields, and whether an operation is destructive."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from pydantic import BaseModel

from . import ops
from . import params as P


@dataclass(frozen=True)
class Spec:
    id: str
    title: str
    group: str
    description: str
    model: type[BaseModel]
    fn: Callable[..., ops.OpResult]
    fields: list[dict[str, Any]]
    destructive: Callable[[BaseModel], bool]


def _never(_: BaseModel) -> bool:
    return False


def _always(_: BaseModel) -> bool:
    return True


KEEP = {
    "name": "keep",
    "kind": "select",
    "label": "Keep",
    "default": "first",
    "options": [{"value": "first", "label": "First occurrence"}, {"value": "last", "label": "Last occurrence"}],
}
TEXT_COLS = {
    "name": "columns",
    "kind": "columns",
    "label": "Columns",
    "filter": "text",
    "optional": True,
    "help": "Leave empty to use every column that contains text.",
}

SPECS: list[Spec] = [
    Spec(
        "remove_exact_duplicates",
        "Remove exact duplicate rows",
        "Rows",
        "Removes rows that are identical to another row in every column.",
        P.RemoveExactDuplicates,
        ops.remove_exact_duplicates,
        [KEEP],
        _always,
    ),
    Spec(
        "key_duplicates",
        "Find duplicates by key columns",
        "Rows",
        "Finds rows that repeat the same value(s) in the columns you choose. A repeated ID is not always an "
        "error, so the default only flags them.",
        P.KeyDuplicates,
        ops.key_duplicates,
        [
            {"name": "key_columns", "kind": "columns", "label": "Key columns"},
            {
                "name": "mode",
                "kind": "select",
                "label": "What to do",
                "default": "flag",
                "options": [
                    {"value": "flag", "label": "Flag them in a new column"},
                    {"value": "remove", "label": "Remove the repeats"},
                ],
            },
            KEEP,
        ],
        lambda p: p.mode == "remove",
    ),
    Spec(
        "remove_empty_rows",
        "Remove completely empty rows",
        "Rows",
        "Removes rows where every cell is empty.",
        P.Empty,
        ops.remove_empty_rows,
        [],
        _always,
    ),
    Spec(
        "trim_whitespace",
        "Trim whitespace",
        "Text",
        "Removes spaces at the start and end of text values.",
        P.TextColumns,
        ops.trim_whitespace,
        [TEXT_COLS],
        _never,
    ),
    Spec(
        "normalize_spaces",
        "Normalise repeated spaces",
        "Text",
        "Replaces runs of spaces inside text with one space.",
        P.TextColumns,
        ops.normalize_spaces,
        [TEXT_COLS],
        _never,
    ),
    Spec(
        "standardize_case",
        "Standardise capitalisation",
        "Text",
        "Changes text to UPPER, lower, Title or Sentence case.",
        P.StandardizeCase,
        ops.standardize_case,
        [
            TEXT_COLS,
            {
                "name": "style",
                "kind": "select",
                "label": "Style",
                "default": "title",
                "options": [
                    {"value": "title", "label": "Title Case"},
                    {"value": "upper", "label": "UPPER CASE"},
                    {"value": "lower", "label": "lower case"},
                    {"value": "sentence", "label": "Sentence case"},
                ],
            },
        ],
        _never,
    ),
    Spec(
        "normalize_categories",
        "Normalise category labels",
        "Text",
        "Replaces different spellings of the same label (capitals, spaces) with the one you choose.",
        P.NormalizeCategories,
        ops.normalize_categories,
        [
            {"name": "column", "kind": "column", "label": "Column", "filter": "text"},
            {"name": "mapping", "kind": "category_mapping", "label": "Labels to merge"},
        ],
        _never,
    ),
    Spec(
        "convert_numeric",
        "Convert numeric text to numbers",
        "Types & dates",
        "Turns text such as “Rs 1,250”, “(250)” or “12%” into real numbers. Values that are not numbers are "
        "reported, never guessed.",
        P.ConvertNumeric,
        ops.convert_numeric,
        [
            {"name": "columns", "kind": "columns", "label": "Columns", "filter": "number"},
            {
                "name": "decimal",
                "kind": "select",
                "label": "Decimal separator",
                "default": ".",
                "options": [{"value": ".", "label": "Point: 1,234.56"}, {"value": ",", "label": "Comma: 1.234,56"}],
            },
            {
                "name": "percent",
                "kind": "select",
                "label": "Percentages",
                "default": "keep_number",
                "options": [
                    {"value": "keep_number", "label": "12% → 12"},
                    {"value": "divide_by_100", "label": "12% → 0.12"},
                ],
            },
            {"name": "parentheses_negative", "kind": "boolean", "label": "(250) means −250", "default": True},
            {
                "name": "on_failure",
                "kind": "select",
                "label": "Values that are not numbers",
                "default": "set_missing",
                "options": [
                    {"value": "set_missing", "label": "Make empty and list them in the report"},
                    {"value": "keep_raw_column", "label": "Also keep the original text in a “__raw” column"},
                ],
            },
        ],
        _never,
    ),
    Spec(
        "normalize_dates",
        "Normalise date formats",
        "Types & dates",
        "Turns date text into real dates using the reading you confirm. Ambiguous dates such as 03/04/2026 are "
        "never converted without your choice.",
        P.NormalizeDates,
        ops.normalize_dates,
        [
            {"name": "column", "kind": "column", "label": "Column", "filter": "date"},
            {"name": "interpretation", "kind": "date_interpretation", "label": "How should dates be read?"},
            {
                "name": "output",
                "kind": "select",
                "label": "Store as",
                "default": "date",
                "options": [{"value": "date", "label": "Date only"}, {"value": "datetime", "label": "Date and time"}],
            },
            {
                "name": "on_failure",
                "kind": "select",
                "label": "Values that are not dates",
                "default": "set_missing",
                "options": [
                    {"value": "set_missing", "label": "Make empty and list them in the report"},
                    {"value": "keep_raw_column", "label": "Also keep the original text in a “__raw” column"},
                ],
            },
        ],
        _never,
    ),
    Spec(
        "identify_invalid_dates",
        "Identify invalid dates",
        "Types & dates",
        "Adds a Yes/No column marking values that are not valid dates under any reading. Nothing else changes.",
        P.IdentifyInvalidDates,
        ops.identify_invalid_dates,
        [{"name": "column", "kind": "column", "label": "Column", "filter": "date"}],
        _never,
    ),
    Spec(
        "detect_missing",
        "Detect missing values",
        "Missing values",
        "Turns blank text and placeholders such as N/A, null or - into real empty cells, so they are counted "
        "consistently.",
        P.DetectMissing,
        ops.detect_missing,
        [
            TEXT_COLS,
            {
                "name": "extra_null_tokens",
                "kind": "tokens",
                "label": "Extra placeholders",
                "optional": True,
                "help": "Other words that mean “no value” in your file, e.g. TBD.",
            },
        ],
        _never,
    ),
    Spec(
        "handle_missing",
        "Handle missing values",
        "Missing values",
        "Choose explicitly what to do with missing values. Nothing is ever filled with zero unless you type 0.",
        P.HandleMissing,
        ops.handle_missing,
        [
            {"name": "column", "kind": "column", "label": "Column"},
            {
                "name": "strategy",
                "kind": "select",
                "label": "What to do",
                "default": "drop_rows",
                "options": [
                    {"value": "drop_rows", "label": "Remove rows where it is missing"},
                    {"value": "fixed", "label": "Fill with a value I type"},
                    {"value": "median", "label": "Fill with the median (numbers)"},
                    {"value": "mean", "label": "Fill with the mean (numbers)"},
                    {"value": "mode", "label": "Fill with the most common value (categories)"},
                    {"value": "leave", "label": "Leave unchanged"},
                ],
            },
            {"name": "value", "kind": "text", "label": "Fill value", "show_if": {"strategy": "fixed"}},
        ],
        lambda p: p.strategy != "leave",
    ),
    Spec(
        "rename_columns",
        "Rename columns",
        "Columns",
        "Gives columns clearer names.",
        P.RenameColumns,
        ops.rename_columns,
        [{"name": "mapping", "kind": "rename_mapping", "label": "New names"}],
        _never,
    ),
    Spec(
        "reorder_columns",
        "Reorder columns",
        "Columns",
        "Changes the order of columns.",
        P.ReorderColumns,
        ops.reorder_columns,
        [{"name": "order", "kind": "column_order", "label": "Column order"}],
        _never,
    ),
    Spec(
        "remove_columns",
        "Remove columns",
        "Columns",
        "Removes columns you do not need. Undo brings them back.",
        P.RemoveColumns,
        ops.remove_columns,
        [{"name": "columns", "kind": "columns", "label": "Columns to remove"}],
        _always,
    ),
    Spec(
        "flag_outliers",
        "Detect possible outliers",
        "Detection",
        "Adds a Yes/No column marking unusually large or small numbers. Nothing is removed.",
        P.FlagOutliers,
        ops.flag_outliers,
        [
            {"name": "column", "kind": "column", "label": "Column", "filter": "number"},
            {
                "name": "method",
                "kind": "select",
                "label": "Method",
                "default": "iqr",
                "options": [
                    {"value": "iqr", "label": "Interquartile range (default 3×)"},
                    {"value": "zscore", "label": "Robust z-score (default 3.5)"},
                ],
            },
            {"name": "threshold", "kind": "number", "label": "Threshold (optional)", "optional": True},
        ],
        _never,
    ),
    Spec(
        "flag_types",
        "Flag inconsistent data types",
        "Detection",
        "Adds a column describing each value's kind (number, date, text…) so you can find odd ones out.",
        P.FlagTypes,
        ops.flag_types,
        [{"name": "column", "kind": "column", "label": "Column"}],
        _never,
    ),
]

REGISTRY = {s.id: s for s in SPECS}
GROUP_ORDER = ["Rows", "Text", "Types & dates", "Missing values", "Columns", "Detection"]


def catalogue() -> list[dict[str, Any]]:
    return [
        {
            "id": s.id,
            "title": s.title,
            "group": s.group,
            "description": s.description,
            "fields": s.fields,
            "always_destructive": s.destructive is _always,
        }
        for s in SPECS
    ]
