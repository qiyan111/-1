"""create template tables

Revision ID: 20260428_0005
Revises: 20260428_0004
Create Date: 2026-04-28
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = "20260428_0005"
down_revision = "20260428_0004"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "analysis_templates",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column("project_code", sa.String(length=80), nullable=False),
        sa.Column("created_by_user_id", sa.Integer(), nullable=False),
        sa.Column("current_version", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["created_by_user_id"], ["users.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_analysis_templates_created_by_user_id"), "analysis_templates", ["created_by_user_id"], unique=False)
    op.create_index(op.f("ix_analysis_templates_name"), "analysis_templates", ["name"], unique=False)
    op.create_index(op.f("ix_analysis_templates_project_code"), "analysis_templates", ["project_code"], unique=False)

    op.create_table(
        "template_plots",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("template_id", sa.Integer(), nullable=False),
        sa.Column("title", sa.String(length=200), nullable=True),
        sa.Column("tube_no", sa.String(length=80), nullable=True),
        sa.Column("x_channel", sa.String(length=120), nullable=True),
        sa.Column("y_channel", sa.String(length=120), nullable=True),
        sa.Column("plot_type", sa.String(length=40), nullable=False),
        sa.Column("config", sa.JSON(), nullable=True),
        sa.Column("sort_order", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(["template_id"], ["analysis_templates.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_template_plots_plot_type"), "template_plots", ["plot_type"], unique=False)
    op.create_index(op.f("ix_template_plots_template_id"), "template_plots", ["template_id"], unique=False)
    op.create_index(op.f("ix_template_plots_tube_no"), "template_plots", ["tube_no"], unique=False)

    op.create_table(
        "template_gates",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("template_id", sa.Integer(), nullable=False),
        sa.Column("parent_gate_id", sa.Integer(), nullable=True),
        sa.Column("parent_gate_key", sa.String(length=120), nullable=True),
        sa.Column("gate_key", sa.String(length=120), nullable=False),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column("gate_type", sa.String(length=80), nullable=False),
        sa.Column("definition", sa.JSON(), nullable=False),
        sa.Column("sort_order", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(["parent_gate_id"], ["template_gates.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["template_id"], ["analysis_templates.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_template_gates_gate_key"), "template_gates", ["gate_key"], unique=False)
    op.create_index(op.f("ix_template_gates_gate_type"), "template_gates", ["gate_type"], unique=False)
    op.create_index(op.f("ix_template_gates_parent_gate_id"), "template_gates", ["parent_gate_id"], unique=False)
    op.create_index(op.f("ix_template_gates_parent_gate_key"), "template_gates", ["parent_gate_key"], unique=False)
    op.create_index(op.f("ix_template_gates_template_id"), "template_gates", ["template_id"], unique=False)

    op.create_table(
        "template_logic_gates",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("template_id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column("expression", sa.Text(), nullable=False),
        sa.Column("definition", sa.JSON(), nullable=True),
        sa.Column("sort_order", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(["template_id"], ["analysis_templates.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_template_logic_gates_template_id"), "template_logic_gates", ["template_id"], unique=False)

    op.create_table(
        "template_statistics",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("template_id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column("rule_type", sa.String(length=80), nullable=False),
        sa.Column("formula", sa.Text(), nullable=True),
        sa.Column("config", sa.JSON(), nullable=True),
        sa.Column("sort_order", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(["template_id"], ["analysis_templates.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_template_statistics_rule_type"), "template_statistics", ["rule_type"], unique=False)
    op.create_index(op.f("ix_template_statistics_template_id"), "template_statistics", ["template_id"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_template_statistics_template_id"), table_name="template_statistics")
    op.drop_index(op.f("ix_template_statistics_rule_type"), table_name="template_statistics")
    op.drop_table("template_statistics")
    op.drop_index(op.f("ix_template_logic_gates_template_id"), table_name="template_logic_gates")
    op.drop_table("template_logic_gates")
    op.drop_index(op.f("ix_template_gates_template_id"), table_name="template_gates")
    op.drop_index(op.f("ix_template_gates_parent_gate_key"), table_name="template_gates")
    op.drop_index(op.f("ix_template_gates_parent_gate_id"), table_name="template_gates")
    op.drop_index(op.f("ix_template_gates_gate_type"), table_name="template_gates")
    op.drop_index(op.f("ix_template_gates_gate_key"), table_name="template_gates")
    op.drop_table("template_gates")
    op.drop_index(op.f("ix_template_plots_tube_no"), table_name="template_plots")
    op.drop_index(op.f("ix_template_plots_template_id"), table_name="template_plots")
    op.drop_index(op.f("ix_template_plots_plot_type"), table_name="template_plots")
    op.drop_table("template_plots")
    op.drop_index(op.f("ix_analysis_templates_project_code"), table_name="analysis_templates")
    op.drop_index(op.f("ix_analysis_templates_name"), table_name="analysis_templates")
    op.drop_index(op.f("ix_analysis_templates_created_by_user_id"), table_name="analysis_templates")
    op.drop_table("analysis_templates")
