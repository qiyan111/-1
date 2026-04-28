"""create metadata tables

Revision ID: 20260428_0004
Revises: 20260428_0003
Create Date: 2026-04-28
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = "20260428_0004"
down_revision = "20260428_0003"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "projects",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("code", sa.String(length=80), nullable=False),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_projects_code"), "projects", ["code"], unique=True)

    op.create_table(
        "experiments",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("project_id", sa.Integer(), nullable=False),
        sa.Column("experiment_no", sa.String(length=120), nullable=False),
        sa.Column("name", sa.String(length=200), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_experiments_experiment_no"), "experiments", ["experiment_no"], unique=True)
    op.create_index(op.f("ix_experiments_project_id"), "experiments", ["project_id"], unique=False)

    op.create_table(
        "samples",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("experiment_id", sa.Integer(), nullable=False),
        sa.Column("sample_no", sa.String(length=120), nullable=False),
        sa.Column("subject_identifier", sa.String(length=120), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["experiment_id"], ["experiments.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("experiment_id", "sample_no"),
    )
    op.create_index(op.f("ix_samples_experiment_id"), "samples", ["experiment_id"], unique=False)
    op.create_index(op.f("ix_samples_sample_no"), "samples", ["sample_no"], unique=False)

    op.create_table(
        "tubes",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("sample_id", sa.Integer(), nullable=False),
        sa.Column("tube_no", sa.String(length=80), nullable=False),
        sa.Column("group_name", sa.String(length=120), nullable=True),
        sa.Column("experimental_condition", sa.Text(), nullable=True),
        sa.Column("antibody_info", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["sample_id"], ["samples.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("sample_id", "tube_no"),
    )
    op.create_index(op.f("ix_tubes_sample_id"), "tubes", ["sample_id"], unique=False)
    op.create_index(op.f("ix_tubes_tube_no"), "tubes", ["tube_no"], unique=False)

    op.create_table(
        "channels",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("tube_id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column("detector", sa.String(length=120), nullable=True),
        sa.Column("fluorochrome", sa.String(length=120), nullable=True),
        sa.Column("marker", sa.String(length=120), nullable=True),
        sa.Column("channel_index", sa.Integer(), nullable=True),
        sa.ForeignKeyConstraint(["tube_id"], ["tubes.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("tube_id", "name"),
    )
    op.create_index(op.f("ix_channels_name"), "channels", ["name"], unique=False)
    op.create_index(op.f("ix_channels_tube_id"), "channels", ["tube_id"], unique=False)

    op.create_table(
        "marker_mappings",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("tube_id", sa.Integer(), nullable=False),
        sa.Column("marker", sa.String(length=120), nullable=False),
        sa.Column("channel_name", sa.String(length=120), nullable=False),
        sa.Column("fluorochrome", sa.String(length=120), nullable=True),
        sa.ForeignKeyConstraint(["tube_id"], ["tubes.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("tube_id", "marker", "channel_name"),
    )
    op.create_index(op.f("ix_marker_mappings_channel_name"), "marker_mappings", ["channel_name"], unique=False)
    op.create_index(op.f("ix_marker_mappings_marker"), "marker_mappings", ["marker"], unique=False)
    op.create_index(op.f("ix_marker_mappings_tube_id"), "marker_mappings", ["tube_id"], unique=False)

    op.create_table(
        "compensation_matrices",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("tube_id", sa.Integer(), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("matrix", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["tube_id"], ["tubes.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("tube_id", "version"),
    )
    op.create_index(op.f("ix_compensation_matrices_tube_id"), "compensation_matrices", ["tube_id"], unique=False)

    with op.batch_alter_table("data_files") as batch_op:
        batch_op.add_column(sa.Column("tube_id", sa.Integer(), nullable=True))
        batch_op.create_foreign_key("fk_data_files_tube_id_tubes", "tubes", ["tube_id"], ["id"], ondelete="SET NULL")
        batch_op.create_index(op.f("ix_data_files_tube_id"), ["tube_id"], unique=False)


def downgrade() -> None:
    with op.batch_alter_table("data_files") as batch_op:
        batch_op.drop_index(op.f("ix_data_files_tube_id"))
        batch_op.drop_constraint("fk_data_files_tube_id_tubes", type_="foreignkey")
        batch_op.drop_column("tube_id")

    op.drop_index(op.f("ix_compensation_matrices_tube_id"), table_name="compensation_matrices")
    op.drop_table("compensation_matrices")
    op.drop_index(op.f("ix_marker_mappings_tube_id"), table_name="marker_mappings")
    op.drop_index(op.f("ix_marker_mappings_marker"), table_name="marker_mappings")
    op.drop_index(op.f("ix_marker_mappings_channel_name"), table_name="marker_mappings")
    op.drop_table("marker_mappings")
    op.drop_index(op.f("ix_channels_tube_id"), table_name="channels")
    op.drop_index(op.f("ix_channels_name"), table_name="channels")
    op.drop_table("channels")
    op.drop_index(op.f("ix_tubes_tube_no"), table_name="tubes")
    op.drop_index(op.f("ix_tubes_sample_id"), table_name="tubes")
    op.drop_table("tubes")
    op.drop_index(op.f("ix_samples_sample_no"), table_name="samples")
    op.drop_index(op.f("ix_samples_experiment_id"), table_name="samples")
    op.drop_table("samples")
    op.drop_index(op.f("ix_experiments_project_id"), table_name="experiments")
    op.drop_index(op.f("ix_experiments_experiment_no"), table_name="experiments")
    op.drop_table("experiments")
    op.drop_index(op.f("ix_projects_code"), table_name="projects")
    op.drop_table("projects")
