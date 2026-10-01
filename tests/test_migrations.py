"""Alembic migration tests.

Runs the real migration chain against a throwaway SQLite database so the
upgrade/downgrade code paths are exercised in CI without needing Postgres.
(SQLite stands in for Postgres here; the migration itself is written with
portable SQLAlchemy constructs.)
"""
import os

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, inspect

EXPECTED_COLUMNS = {
    "run_id",
    "agent_id",
    "test_case_id",
    "overall_status",
    "overall_score",
    "reliability",
    "security",
    "metrics",
    "trace",
    "duration_ms",
    "total_tokens",
    "estimated_cost_usd",
    "llm_call_count",
    "tool_call_count",
    "tool_error_count",
    "repeated_tool_call_count",
    "important_failures",
    "metadata_json",
    "created_at",
}
EXPECTED_INDEXES = {"ix_run_reports_agent_id", "ix_run_reports_test_case_id"}


@pytest.fixture()
def alembic_config(tmp_path, monkeypatch):
    db_file = tmp_path / "migrations_test.db"
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{db_file}")
    cfg = Config("alembic.ini")
    cfg.set_main_option("script_location", "migrations")
    return cfg, f"sqlite:///{db_file}"


def test_upgrade_head_creates_run_reports(alembic_config):
    cfg, url = alembic_config
    command.upgrade(cfg, "head")

    inspector = inspect(create_engine(url))
    assert "run_reports" in inspector.get_table_names()
    columns = {c["name"] for c in inspector.get_columns("run_reports")}
    assert EXPECTED_COLUMNS <= columns
    indexes = {i["name"] for i in inspector.get_indexes("run_reports")}
    assert EXPECTED_INDEXES <= indexes


def test_downgrade_base_removes_run_reports(alembic_config):
    cfg, url = alembic_config
    command.upgrade(cfg, "head")
    command.downgrade(cfg, "base")

    inspector = inspect(create_engine(url))
    assert "run_reports" not in inspector.get_table_names()


def test_alembic_version_table_tracks_single_head(alembic_config):
    cfg, url = alembic_config
    command.upgrade(cfg, "head")
    # Re-running upgrade must be a no-op (idempotent).
    command.upgrade(cfg, "head")
    inspector = inspect(create_engine(url))
    assert "run_reports" in inspector.get_table_names()


EXPECTED_TEST_CASE_COLUMNS = {
    "id",
    "title",
    "agent_name",
    "category",
    "user_input",
    "expected_tool_calls",
    "expected_outcome",
    "security_expectation",
    "max_tool_calls",
    "max_latency_ms",
    "created_at",
    "updated_at",
}
EXPECTED_TEST_CASE_INDEXES = {"ix_test_cases_category"}


def test_upgrade_head_creates_test_cases(alembic_config):
    cfg, url = alembic_config
    command.upgrade(cfg, "head")

    inspector = inspect(create_engine(url))
    assert "test_cases" in inspector.get_table_names()
    columns = {c["name"] for c in inspector.get_columns("test_cases")}
    assert EXPECTED_TEST_CASE_COLUMNS <= columns
    indexes = {i["name"] for i in inspector.get_indexes("test_cases")}
    assert EXPECTED_TEST_CASE_INDEXES <= indexes


def test_downgrade_0002_removes_test_cases_but_keeps_run_reports(alembic_config):
    cfg, url = alembic_config
    command.upgrade(cfg, "head")
    command.downgrade(cfg, "0001")

    inspector = inspect(create_engine(url))
    tables = inspector.get_table_names()
    assert "test_cases" not in tables
    assert "run_reports" in tables
