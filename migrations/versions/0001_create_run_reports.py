"""create run_reports table

Revision ID: 0001
Revises:
Create Date: 2026-09-29

Initial schema for the run report store. Mirrors
``src.reporting.history.postgres.RunReportRow`` exactly (including the
``created_at`` server default), so a fresh database built by this migration
is identical to one built by the legacy ``Base.metadata.create_all()`` path.

Databases created before Alembic was introduced should run
``alembic stamp 0001`` once instead of ``upgrade``.
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision: str = "0001"
down_revision: str | None = None
branch_labels: str | tuple[str, ...] | None = None
depends_on: str | tuple[str, ...] | None = None


def upgrade() -> None:
    op.create_table(
        "run_reports",
        sa.Column("run_id", sa.String(), primary_key=True),
        sa.Column("agent_id", sa.String(), nullable=False),
        sa.Column("test_case_id", sa.String(), nullable=False),
        sa.Column("overall_status", sa.String(), nullable=False),
        sa.Column("overall_score", sa.Float(), nullable=False),
        sa.Column("reliability", sa.JSON(), nullable=False),
        sa.Column("security", sa.JSON(), nullable=False),
        sa.Column("metrics", sa.JSON(), nullable=False),
        sa.Column("trace", sa.JSON(), nullable=True),
        sa.Column("duration_ms", sa.Float(), nullable=True),
        sa.Column("total_tokens", sa.Integer(), nullable=True),
        sa.Column("estimated_cost_usd", sa.Float(), nullable=True),
        sa.Column("llm_call_count", sa.Integer(), nullable=True),
        sa.Column("tool_call_count", sa.Integer(), nullable=True),
        sa.Column("tool_error_count", sa.Integer(), nullable=True),
        sa.Column("repeated_tool_call_count", sa.Integer(), nullable=True),
        sa.Column("important_failures", sa.JSON(), nullable=False),
        sa.Column("metadata_json", sa.JSON(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )
    op.create_index(
        "ix_run_reports_agent_id", "run_reports", ["agent_id"]
    )
    op.create_index(
        "ix_run_reports_test_case_id", "run_reports", ["test_case_id"]
    )


def downgrade() -> None:
    op.drop_index("ix_run_reports_test_case_id", table_name="run_reports")
    op.drop_index("ix_run_reports_agent_id", table_name="run_reports")
    op.drop_table("run_reports")
