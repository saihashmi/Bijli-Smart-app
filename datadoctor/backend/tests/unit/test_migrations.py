from alembic.autogenerate import compare_metadata
from alembic.migration import MigrationContext
from sqlalchemy import inspect

from app import models  # noqa: F401
from app.db import Base, engine
from app.migrate import upgrade_to_head

EXPECTED_TABLES = {
    "workspaces",
    "datasets",
    "worksheets",
    "analysis_sessions",
    "cleaning_operations",
    "audit_events",
    "data_profiles",
    "dashboard_configurations",
    "export_jobs",
    "ai_interactions",
}


def test_migrations_create_full_schema_from_scratch():
    upgrade_to_head()
    tables = set(inspect(engine).get_table_names())
    assert EXPECTED_TABLES <= tables
    assert "alembic_version" in tables


def test_models_and_migrations_are_in_sync():
    upgrade_to_head()
    with engine.connect() as conn:
        diff = compare_metadata(MigrationContext.configure(conn), Base.metadata)
    assert diff == [], f"models changed without a migration: {diff}"


def test_upgrade_is_idempotent():
    upgrade_to_head()
    upgrade_to_head()
