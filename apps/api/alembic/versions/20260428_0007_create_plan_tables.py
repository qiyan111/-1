"""create plan tables

Revision ID: 20260428_0007
Revises: 20260428_0006
Create Date: 2026-04-28
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = "20260428_0007"
down_revision = "20260428_0006"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "analysis_plans",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column("project_id", sa.Integer(), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("created_by_user_id", sa.Integer(), nullable=False),
        sa.Column("current_version", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["created_by_user_id"], ["users.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_analysis_plans_created_by_user_id"), "analysis_plans", ["created_by_user_id"], unique=False)
    op.create_index(op.f("ix_analysis_plans_name"), "analysis_plans", ["name"], unique=False)
    op.create_index(op.f("ix_analysis_plans_project_id"), "analysis_plans", ["project_id"], unique=False)

    op.create_table(
        "analysis_plan_versions",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("plan_id", sa.Integer(), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("snapshot_json", sa.JSON(), nullable=False),
        sa.Column("change_note", sa.Text(), nullable=False),
        sa.Column("created_by", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["created_by"], ["users.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["plan_id"], ["analysis_plans.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("plan_id", "version"),
    )
    op.create_index(op.f("ix_analysis_plan_versions_created_by"), "analysis_plan_versions", ["created_by"], unique=False)
    op.create_index(op.f("ix_analysis_plan_versions_plan_id"), "analysis_plan_versions", ["plan_id"], unique=False)
    op.create_index(op.f("ix_analysis_plan_versions_version"), "analysis_plan_versions", ["version"], unique=False)

    op.create_table(
        "plan_template_bindings",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("plan_id", sa.Integer(), nullable=False),
        sa.Column("template_id", sa.Integer(), nullable=False),
        sa.Column("experiment_no", sa.String(length=120), nullable=True),
        sa.Column("tube_no", sa.String(length=80), nullable=False),
        sa.Column("config", sa.JSON(), nullable=True),
        sa.Column("sort_order", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(["plan_id"], ["analysis_plans.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["template_id"], ["analysis_templates.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("plan_id", "experiment_no", "tube_no", "template_id"),
    )
    op.create_index(op.f("ix_plan_template_bindings_experiment_no"), "plan_template_bindings", ["experiment_no"], unique=False)
    op.create_index(op.f("ix_plan_template_bindings_plan_id"), "plan_template_bindings", ["plan_id"], unique=False)
    op.create_index(op.f("ix_plan_template_bindings_template_id"), "plan_template_bindings", ["template_id"], unique=False)
    op.create_index(op.f("ix_plan_template_bindings_tube_no"), "plan_template_bindings", ["tube_no"], unique=False)

    op.create_table(
        "cell_label_nodes",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("plan_id", sa.Integer(), nullable=False),
        sa.Column("parent_node_id", sa.Integer(), nullable=True),
        sa.Column("code", sa.String(length=120), nullable=False),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("sort_order", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(["parent_node_id"], ["cell_label_nodes.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["plan_id"], ["analysis_plans.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("plan_id", "code"),
    )
    op.create_index(op.f("ix_cell_label_nodes_code"), "cell_label_nodes", ["code"], unique=False)
    op.create_index(op.f("ix_cell_label_nodes_parent_node_id"), "cell_label_nodes", ["parent_node_id"], unique=False)
    op.create_index(op.f("ix_cell_label_nodes_plan_id"), "cell_label_nodes", ["plan_id"], unique=False)

    op.create_table(
        "marker_thresholds",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("plan_id", sa.Integer(), nullable=False),
        sa.Column("label_node_id", sa.Integer(), nullable=True),
        sa.Column("marker", sa.String(length=120), nullable=False),
        sa.Column("channel_name", sa.String(length=120), nullable=False),
        sa.Column("threshold_type", sa.String(length=80), nullable=False),
        sa.Column("threshold_value", sa.Float(), nullable=False),
        sa.Column("config", sa.JSON(), nullable=True),
        sa.ForeignKeyConstraint(["label_node_id"], ["cell_label_nodes.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["plan_id"], ["analysis_plans.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("plan_id", "marker", "channel_name", "threshold_type"),
    )
    op.create_index(op.f("ix_marker_thresholds_channel_name"), "marker_thresholds", ["channel_name"], unique=False)
    op.create_index(op.f("ix_marker_thresholds_label_node_id"), "marker_thresholds", ["label_node_id"], unique=False)
    op.create_index(op.f("ix_marker_thresholds_marker"), "marker_thresholds", ["marker"], unique=False)
    op.create_index(op.f("ix_marker_thresholds_plan_id"), "marker_thresholds", ["plan_id"], unique=False)
    op.create_index(op.f("ix_marker_thresholds_threshold_type"), "marker_thresholds", ["threshold_type"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_marker_thresholds_threshold_type"), table_name="marker_thresholds")
    op.drop_index(op.f("ix_marker_thresholds_plan_id"), table_name="marker_thresholds")
    op.drop_index(op.f("ix_marker_thresholds_marker"), table_name="marker_thresholds")
    op.drop_index(op.f("ix_marker_thresholds_label_node_id"), table_name="marker_thresholds")
    op.drop_index(op.f("ix_marker_thresholds_channel_name"), table_name="marker_thresholds")
    op.drop_table("marker_thresholds")
    op.drop_index(op.f("ix_cell_label_nodes_plan_id"), table_name="cell_label_nodes")
    op.drop_index(op.f("ix_cell_label_nodes_parent_node_id"), table_name="cell_label_nodes")
    op.drop_index(op.f("ix_cell_label_nodes_code"), table_name="cell_label_nodes")
    op.drop_table("cell_label_nodes")
    op.drop_index(op.f("ix_plan_template_bindings_tube_no"), table_name="plan_template_bindings")
    op.drop_index(op.f("ix_plan_template_bindings_template_id"), table_name="plan_template_bindings")
    op.drop_index(op.f("ix_plan_template_bindings_plan_id"), table_name="plan_template_bindings")
    op.drop_index(op.f("ix_plan_template_bindings_experiment_no"), table_name="plan_template_bindings")
    op.drop_table("plan_template_bindings")
    op.drop_index(op.f("ix_analysis_plan_versions_version"), table_name="analysis_plan_versions")
    op.drop_index(op.f("ix_analysis_plan_versions_plan_id"), table_name="analysis_plan_versions")
    op.drop_index(op.f("ix_analysis_plan_versions_created_by"), table_name="analysis_plan_versions")
    op.drop_table("analysis_plan_versions")
    op.drop_index(op.f("ix_analysis_plans_project_id"), table_name="analysis_plans")
    op.drop_index(op.f("ix_analysis_plans_name"), table_name="analysis_plans")
    op.drop_index(op.f("ix_analysis_plans_created_by_user_id"), table_name="analysis_plans")
    op.drop_table("analysis_plans")
