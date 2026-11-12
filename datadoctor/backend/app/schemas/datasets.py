from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field


class SheetOut(BaseModel):
    index: int
    name: str
    visibility: str
    rows: int
    columns: int
    formula_cells_without_cache: int
    kind: str = "worksheet"
    selectable: bool
    problem: str | None = None


class CsvInfo(BaseModel):
    encoding: str
    delimiter: str
    delimiter_label: str
    replaced_characters: int


class SessionBrief(BaseModel):
    id: str
    sheet_index: int | None
    sheet_name: str | None
    header_row: int
    status: str
    created_at: datetime
    updated_at: datetime


class DatasetOut(BaseModel):
    id: str
    original_filename: str
    file_type: str
    file_size: int
    uploaded_at: datetime
    expires_at: datetime
    status: str
    sheets: list[SheetOut]
    csv: CsvInfo | None = None
    warnings: list[str] = []
    sessions: list[SessionBrief] = []


class PeekOut(BaseModel):
    sheet_index: int
    rows: list[list[str]]
    total_rows: int
    total_columns: int
    truncated_columns: bool


class SessionCreate(BaseModel):
    sheet_index: int = Field(ge=0)
    header_row: int = Field(default=0, ge=0, le=50, description="0-based row number holding the column names")


class HeaderChange(BaseModel):
    position: int
    original: str
    new: str
    reason: str


class SessionOut(BaseModel):
    id: str
    dataset_id: str
    original_filename: str
    file_type: str
    file_size: int
    sheet_index: int | None
    sheet_name: str | None
    header_row: int
    rows: int | None = Field(description="Data rows below the header row")
    columns: int | None
    column_names: list[str] = []
    header_changes: list[HeaderChange] = []
    warnings: list[str] = []
    version: int = 0
    status: str
    created_at: datetime
    updated_at: datetime
    expires_at: datetime


class RowsOut(BaseModel):
    view: str
    version: int
    offset: int
    total: int
    columns: list[str]
    rows: list[list[str | None]]
    row_numbers: list[int] = []


class SensitiveColumnsIn(BaseModel):
    columns: list[str] = Field(max_length=500)


class CleaningRequest(BaseModel):
    operation_type: str = Field(max_length=64)
    parameters: dict = Field(default_factory=dict)
    confirm: bool = False


class OperationOut(BaseModel):
    id: str
    sequence_number: int
    operation_type: str
    title: str
    parameters: dict
    affected_rows: int
    status: str
    created_at: datetime
    undone_at: datetime | None = None
    summary: str | None = None
