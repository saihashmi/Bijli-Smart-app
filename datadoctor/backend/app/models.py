"""Database tables, exactly as approved in SPEC.md §8. Metadata only: datasets live as files in storage."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import JSON, DateTime, ForeignKey, Integer, String, Text, TypeDecorator, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .db import Base


def new_id() -> str:
    return str(uuid.uuid4())


def utcnow() -> datetime:
    return datetime.now(UTC)


class UTCDateTime(TypeDecorator):
    """Stores UTC; always returns timezone-aware UTC datetimes (SQLite drops tzinfo on its own)."""

    impl = DateTime(timezone=True)
    cache_ok = True

    def process_bind_param(self, value, dialect):
        if value is not None and value.tzinfo is None:
            value = value.replace(tzinfo=UTC)
        return value.astimezone(UTC) if value is not None else None

    def process_result_value(self, value, dialect):
        if value is not None and value.tzinfo is None:
            value = value.replace(tzinfo=UTC)
        return value


UUID = String(36)
TS = UTCDateTime()


class Workspace(Base):
    """Local-mode ownership scope, identified by a signed cookie. Not authentication."""

    __tablename__ = "workspaces"
    id: Mapped[str] = mapped_column(UUID, primary_key=True, default=new_id)
    created_at: Mapped[datetime] = mapped_column(TS, default=utcnow)
    last_seen_at: Mapped[datetime] = mapped_column(TS, default=utcnow)
    settings_json: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)

    datasets: Mapped[list[Dataset]] = relationship(back_populates="workspace", cascade="all, delete-orphan")


class Dataset(Base):
    __tablename__ = "datasets"
    id: Mapped[str] = mapped_column(UUID, primary_key=True, default=new_id)
    workspace_id: Mapped[str] = mapped_column(UUID, ForeignKey("workspaces.id", ondelete="CASCADE"), index=True)
    original_filename: Mapped[str] = mapped_column(String(255))  # sanitised, display only
    file_type: Mapped[str] = mapped_column(String(8))  # xlsx | xls | csv
    file_size: Mapped[int] = mapped_column(Integer)
    sha256: Mapped[str] = mapped_column(String(64))
    storage_reference: Mapped[str] = mapped_column(String(128))  # generated name, never a client path
    uploaded_at: Mapped[datetime] = mapped_column(TS, default=utcnow)
    expires_at: Mapped[datetime] = mapped_column(TS)
    status: Mapped[str] = mapped_column(String(16), default="uploaded")  # uploaded|parsed|failed|deleted

    workspace: Mapped[Workspace] = relationship(back_populates="datasets")
    worksheets: Mapped[list[Worksheet]] = relationship(back_populates="dataset", cascade="all, delete-orphan")
    sessions: Mapped[list[AnalysisSession]] = relationship(back_populates="dataset", cascade="all, delete-orphan")


class Worksheet(Base):
    __tablename__ = "worksheets"
    id: Mapped[str] = mapped_column(UUID, primary_key=True, default=new_id)
    dataset_id: Mapped[str] = mapped_column(UUID, ForeignKey("datasets.id", ondelete="CASCADE"), index=True)
    sheet_name: Mapped[str] = mapped_column(String(255))
    sheet_index: Mapped[int] = mapped_column(Integer)
    visibility: Mapped[str] = mapped_column(String(16), default="visible")  # visible|hidden|very_hidden
    row_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    column_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    formula_cells_without_cache: Mapped[int] = mapped_column(Integer, default=0)

    dataset: Mapped[Dataset] = relationship(back_populates="worksheets")


class AnalysisSession(Base):
    __tablename__ = "analysis_sessions"
    id: Mapped[str] = mapped_column(UUID, primary_key=True, default=new_id)
    dataset_id: Mapped[str] = mapped_column(UUID, ForeignKey("datasets.id", ondelete="CASCADE"), index=True)
    worksheet_id: Mapped[str | None] = mapped_column(
        UUID, ForeignKey("worksheets.id", ondelete="CASCADE"), nullable=True
    )
    header_row: Mapped[int] = mapped_column(Integer, default=0)
    date_rules_json: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    sensitive_columns_json: Mapped[list[str]] = mapped_column(JSON, default=list)
    created_at: Mapped[datetime] = mapped_column(TS, default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(TS, default=utcnow, onupdate=utcnow)
    status: Mapped[str] = mapped_column(String(16), default="active")  # active|archived|expired

    dataset: Mapped[Dataset] = relationship(back_populates="sessions")
    operations: Mapped[list[CleaningOperation]] = relationship(
        back_populates="session", cascade="all, delete-orphan", order_by="CleaningOperation.sequence_number"
    )


class CleaningOperation(Base):
    __tablename__ = "cleaning_operations"
    __table_args__ = (UniqueConstraint("session_id", "sequence_number", name="uq_operation_sequence"),)
    id: Mapped[str] = mapped_column(UUID, primary_key=True, default=new_id)
    session_id: Mapped[str] = mapped_column(UUID, ForeignKey("analysis_sessions.id", ondelete="CASCADE"), index=True)
    sequence_number: Mapped[int] = mapped_column(Integer)
    operation_type: Mapped[str] = mapped_column(String(64))
    parameters_json: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    affected_rows: Mapped[int] = mapped_column(Integer, default=0)
    status: Mapped[str] = mapped_column(String(16), default="active")  # active|undone
    created_at: Mapped[datetime] = mapped_column(TS, default=utcnow)
    undone_at: Mapped[datetime | None] = mapped_column(TS, nullable=True)

    session: Mapped[AnalysisSession] = relationship(back_populates="operations")


class AuditEvent(Base):
    __tablename__ = "audit_events"
    id: Mapped[str] = mapped_column(UUID, primary_key=True, default=new_id)
    session_id: Mapped[str] = mapped_column(UUID, ForeignKey("analysis_sessions.id", ondelete="CASCADE"), index=True)
    event_type: Mapped[str] = mapped_column(String(32))  # undo|reset|export|delete|ai_opt_in...
    details_json: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(TS, default=utcnow)


class DataProfile(Base):
    __tablename__ = "data_profiles"
    id: Mapped[str] = mapped_column(UUID, primary_key=True, default=new_id)
    session_id: Mapped[str] = mapped_column(UUID, ForeignKey("analysis_sessions.id", ondelete="CASCADE"), index=True)
    version_hash: Mapped[str] = mapped_column(String(64))
    profile_json: Mapped[dict[str, Any]] = mapped_column(JSON)
    calculated_at: Mapped[datetime] = mapped_column(TS, default=utcnow)


class DashboardConfiguration(Base):
    __tablename__ = "dashboard_configurations"
    id: Mapped[str] = mapped_column(UUID, primary_key=True, default=new_id)
    session_id: Mapped[str] = mapped_column(
        UUID, ForeignKey("analysis_sessions.id", ondelete="CASCADE"), index=True, unique=True
    )
    configuration_json: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    updated_at: Mapped[datetime] = mapped_column(TS, default=utcnow, onupdate=utcnow)


class ExportJob(Base):
    __tablename__ = "export_jobs"
    id: Mapped[str] = mapped_column(UUID, primary_key=True, default=new_id)
    session_id: Mapped[str] = mapped_column(UUID, ForeignKey("analysis_sessions.id", ondelete="CASCADE"), index=True)
    export_type: Mapped[str] = mapped_column(String(8))  # xlsx|pdf
    status: Mapped[str] = mapped_column(String(16), default="pending")  # pending|running|done|failed|expired
    storage_reference: Mapped[str | None] = mapped_column(String(128), nullable=True)
    options_json: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(TS, default=utcnow)
    completed_at: Mapped[datetime | None] = mapped_column(TS, nullable=True)
    expires_at: Mapped[datetime | None] = mapped_column(TS, nullable=True)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)


class AIInteraction(Base):
    __tablename__ = "ai_interactions"
    id: Mapped[str] = mapped_column(UUID, primary_key=True, default=new_id)
    session_id: Mapped[str] = mapped_column(UUID, ForeignKey("analysis_sessions.id", ondelete="CASCADE"), index=True)
    question: Mapped[str] = mapped_column(Text)
    operation_type: Mapped[str | None] = mapped_column(String(64), nullable=True)
    parameters_json: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    result_summary: Mapped[str] = mapped_column(Text, default="")
    provider: Mapped[str] = mapped_column(String(16), default="local")  # local|groq
    explanation_status: Mapped[str] = mapped_column(String(16), default="none")  # none|verified|rejected
    created_at: Mapped[datetime] = mapped_column(TS, default=utcnow)
