"""Typed parameters for every cleaning operation (SPEC §11). Validation happens before any data is touched."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

Columns = list[str]


class _P(BaseModel):
    model_config = ConfigDict(extra="forbid")


class RemoveExactDuplicates(_P):
    keep: Literal["first", "last"] = "first"


class KeyDuplicates(_P):
    key_columns: Columns = Field(min_length=1)
    mode: Literal["flag", "remove"] = "flag"
    keep: Literal["first", "last"] = "first"


class TextColumns(_P):
    columns: Columns = Field(default_factory=list, description="Empty means every column that contains text")


class StandardizeCase(TextColumns):
    style: Literal["upper", "lower", "title", "sentence"] = "title"


class NormalizeCategories(_P):
    column: str
    mapping: dict[str, str] = Field(min_length=1, description="variant spelling → label to use instead")

    @field_validator("mapping")
    @classmethod
    def _non_empty_targets(cls, v: dict[str, str]) -> dict[str, str]:
        if any(not t.strip() for t in v.values()):
            raise ValueError("replacement labels cannot be empty")
        return v


class ConvertNumeric(_P):
    columns: Columns = Field(min_length=1)
    decimal: Literal[".", ","] = "."
    percent: Literal["keep_number", "divide_by_100"] = "keep_number"
    parentheses_negative: bool = True
    on_failure: Literal["set_missing", "keep_raw_column"] = "set_missing"


class NormalizeDates(_P):
    column: str
    interpretation: Literal["DMY", "MDY", "YMD", "excel_serial_1900", "excel_serial_1904"]
    output: Literal["date", "datetime"] = "date"
    on_failure: Literal["set_missing", "keep_raw_column"] = "set_missing"


class IdentifyInvalidDates(_P):
    column: str


class DetectMissing(_P):
    columns: Columns = Field(default_factory=list)
    extra_null_tokens: list[str] = Field(default_factory=list, max_length=50)


class HandleMissing(_P):
    column: str
    strategy: Literal["leave", "drop_rows", "fixed", "median", "mean", "mode"]
    value: str | None = None


class Empty(_P):
    pass


class RenameColumns(_P):
    mapping: dict[str, str] = Field(min_length=1)


class ReorderColumns(_P):
    order: Columns = Field(min_length=1)


class RemoveColumns(_P):
    columns: Columns = Field(min_length=1)


class FlagOutliers(_P):
    column: str
    method: Literal["iqr", "zscore"] = "iqr"
    threshold: float | None = Field(default=None, gt=0, le=100)


class FlagTypes(_P):
    column: str
