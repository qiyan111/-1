"""create result gate and statistic tables

Revision ID: 20260428_0009
Revises: 20260428_0008
Create Date: 2026-04-28
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = "20260428_0009"
down_revision = "20260428_0008"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "result_gates",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("analysis_result_id", sa.Integer(), nullable=False),
        sa.Column("gate_key", sa.String(length=120), nullable=False),
        sa.Column("gate_name", sa.String(length=200), nullable=False),
        sa.Column("gate_type", sa.String(length=80), nullable=False),
        sa.Column("definition", sa.JSON(), nullable=False),
        sa.Column("event_count", sa.Integer(), nullable=False),
        sa.Column("parent_event_count", sa.Integer(), nullable=True),
        sa.Column("mask", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["analysis_result_id"], ["analysis_results.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_result_gates_analysis_result_id"), "result_gates", ["analysis_result_id"], unique=False)
    op.create_index(op.f("ix_result_gates_gate_key"), "result_gates", ["gate_key"], unique=False)
    op.create_index(op.f("ix_result_gates_gate_type"), "result_gates", ["gate_type"], unique=False)

    op.create_table(
        "result_statistics",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("analysis_result_id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column("statistic_type", sa.String(length=80), nullable=False),
        sa.Column("value", sa.JSON(), nullable=True),
        sa.Column("unit", sa.String(length=80), nullable=True),
        sa.Column("metadata_json", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["analysis_result_id"], ["analysis_results.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_result_statistics_analysis_result_id"), "result_statistics", ["analysis_result_id"], unique=False)
    op.create_index(op.f("ix_result_statistics_name"), "result_statistics", ["name"], unique=False)
    op.create_index(op.f("ix_result_statistics_statistic_type"), "result_statistics", ["statistic_type"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_result_statistics_statistic_type"), table_name="result_statistics")
    op.drop_index(op.f("ix_result_statistics_name"), table_name="result_statistics")
    op.drop_index(op.f("ix_result_statistics_analysis_result_id"), table_name="result_statistics")
    op.drop_table("result_statistics")
    op.drop_index(op.f("ix_result_gates_gate_type"), table_name="result_gates")
    op.drop_index(op.f("ix_result_gates_gate_key"), table_name="result_gates")
    op.drop_index(op.f("ix_result_gates_analysis_result_id"), table_name="result_gates")
    op.drop_table("result_gates")
