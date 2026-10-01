"""create test_cases table

Revision ID: 0002
Revises: 0001
Create Date: 2026-09-29

Persistent library of reusable evaluation test cases. Mirrors
``src.reporting.history.postgres.TestCaseRow`` exactly (including the
server-default timestamps), so a fresh database built by this migration
is identical to one built by the legacy ``Base.metadata.create_all()`` path.
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision: str = "0002"
down_revision: str | None = "0001"
branch_labels: str | tuple[str, ...] | None = None
depends_on: str | tuple[str, ...] | None = None


def upgrade() -> None:
    op.create_table(
        "test_cases",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("title", sa.String(), nullable=True),
        sa.Column("agent_name", sa.String(), nullable=False),
        sa.Column("category", sa.String(), nullable=False),
        sa.Column("user_input", sa.Text(), nullable=False),
        sa.Column("expected_tool_calls", sa.JSON(), nullable=False),
        sa.Column("expected_outcome", sa.Text(), nullable=True),
        sa.Column("security_expectation", sa.JSON(), nullable=False),
        sa.Column("max_tool_calls", sa.Integer(), nullable=True),
        sa.Column("max_latency_ms", sa.Integer(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )
    op.create_index("ix_test_cases_category", "test_cases", ["category"])


def downgrade() -> None:
    op.drop_index("ix_test_cases_category", table_name="test_cases")
    op.drop_table("test_cases")
