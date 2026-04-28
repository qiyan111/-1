"""create upload tables

Revision ID: 20260428_0003
Revises: 20260428_0002
Create Date: 2026-04-28
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = "20260428_0003"
down_revision = "20260428_0002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "upload_batches",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(length=40), nullable=False),
        sa.Column("uploaded_by_user_id", sa.Integer(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["uploaded_by_user_id"], ["users.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_upload_batches_uploaded_by_user_id"),
        "upload_batches",
        ["uploaded_by_user_id"],
        unique=False,
    )

    op.create_table(
        "data_files",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("upload_batch_id", sa.Integer(), nullable=False),
        sa.Column("uploaded_by_user_id", sa.Integer(), nullable=False),
        sa.Column("original_filename", sa.String(length=255), nullable=False),
        sa.Column("file_extension", sa.String(length=20), nullable=False),
        sa.Column("content_type", sa.String(length=120), nullable=True),
        sa.Column("object_bucket", sa.String(length=120), nullable=False),
        sa.Column("object_key", sa.String(length=512), nullable=False),
        sa.Column("file_size", sa.BigInteger(), nullable=False),
        sa.Column("sha256", sa.String(length=64), nullable=False),
        sa.Column(
            "uploaded_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["upload_batch_id"], ["upload_batches.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["uploaded_by_user_id"], ["users.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_data_files_file_extension"), "data_files", ["file_extension"], unique=False)
    op.create_index(op.f("ix_data_files_object_key"), "data_files", ["object_key"], unique=True)
    op.create_index(op.f("ix_data_files_sha256"), "data_files", ["sha256"], unique=False)
    op.create_index(op.f("ix_data_files_upload_batch_id"), "data_files", ["upload_batch_id"], unique=False)
    op.create_index(op.f("ix_data_files_uploaded_by_user_id"), "data_files", ["uploaded_by_user_id"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_data_files_uploaded_by_user_id"), table_name="data_files")
    op.drop_index(op.f("ix_data_files_upload_batch_id"), table_name="data_files")
    op.drop_index(op.f("ix_data_files_sha256"), table_name="data_files")
    op.drop_index(op.f("ix_data_files_object_key"), table_name="data_files")
    op.drop_index(op.f("ix_data_files_file_extension"), table_name="data_files")
    op.drop_table("data_files")
    op.drop_index(op.f("ix_upload_batches_uploaded_by_user_id"), table_name="upload_batches")
    op.drop_table("upload_batches")

