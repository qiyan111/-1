"""create template versions

Revision ID: 20260428_0006
Revises: 20260428_0005
Create Date: 2026-04-28
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = "20260428_0006"
down_revision = "20260428_0005"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "analysis_template_versions",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("template_id", sa.Integer(), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("snapshot_json", sa.JSON(), nullable=False),
        sa.Column("change_note", sa.Text(), nullable=False),
        sa.Column("created_by", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["created_by"], ["users.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["template_id"], ["analysis_templates.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("template_id", "version"),
    )
    op.create_index(op.f("ix_analysis_template_versions_created_by"), "analysis_template_versions", ["created_by"], unique=False)
    op.create_index(op.f("ix_analysis_template_versions_template_id"), "analysis_template_versions", ["template_id"], unique=False)
    op.create_index(op.f("ix_analysis_template_versions_version"), "analysis_template_versions", ["version"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_analysis_template_versions_version"), table_name="analysis_template_versions")
    op.drop_index(op.f("ix_analysis_template_versions_template_id"), table_name="analysis_template_versions")
    op.drop_index(op.f("ix_analysis_template_versions_created_by"), table_name="analysis_template_versions")
    op.drop_table("analysis_template_versions")
