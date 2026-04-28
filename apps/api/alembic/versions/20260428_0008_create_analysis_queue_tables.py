"""create analysis queue tables

Revision ID: 20260428_0008
Revises: 20260428_0007
Create Date: 2026-04-28
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = "20260428_0008"
down_revision = "20260428_0007"
branch_labels = None
depends_on = None

ANALYSIS_STATUSES = ("PENDING", "QUEUED", "RUNNING", "PAUSED", "COMPLETED", "FAILED", "CANCELLED")


def upgrade() -> None:
    op.create_table(
        "analysis_batches",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("upload_batch_id", sa.Integer(), nullable=False),
        sa.Column("plan_id", sa.Integer(), nullable=True),
        sa.Column("template_id", sa.Integer(), nullable=True),
        sa.Column("requested_by_user_id", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(length=40), nullable=False),
        sa.Column("total_jobs", sa.Integer(), nullable=False),
        sa.Column("completed_jobs", sa.Integer(), nullable=False),
        sa.Column("failed_jobs", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint(f"status IN {ANALYSIS_STATUSES}", name="ck_analysis_batches_status"),
        sa.ForeignKeyConstraint(["plan_id"], ["analysis_plans.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["requested_by_user_id"], ["users.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["template_id"], ["analysis_templates.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["upload_batch_id"], ["upload_batches.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_analysis_batches_plan_id"), "analysis_batches", ["plan_id"], unique=False)
    op.create_index(op.f("ix_analysis_batches_requested_by_user_id"), "analysis_batches", ["requested_by_user_id"], unique=False)
    op.create_index(op.f("ix_analysis_batches_status"), "analysis_batches", ["status"], unique=False)
    op.create_index(op.f("ix_analysis_batches_template_id"), "analysis_batches", ["template_id"], unique=False)
    op.create_index(op.f("ix_analysis_batches_upload_batch_id"), "analysis_batches", ["upload_batch_id"], unique=False)

    op.create_table(
        "analysis_jobs",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("analysis_batch_id", sa.Integer(), nullable=False),
        sa.Column("data_file_id", sa.Integer(), nullable=False),
        sa.Column("retry_of_job_id", sa.Integer(), nullable=True),
        sa.Column("status", sa.String(length=40), nullable=False),
        sa.Column("attempt", sa.Integer(), nullable=False),
        sa.Column("logs", sa.JSON(), nullable=False),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint(f"status IN {ANALYSIS_STATUSES}", name="ck_analysis_jobs_status"),
        sa.ForeignKeyConstraint(["analysis_batch_id"], ["analysis_batches.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["data_file_id"], ["data_files.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["retry_of_job_id"], ["analysis_jobs.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_analysis_jobs_analysis_batch_id"), "analysis_jobs", ["analysis_batch_id"], unique=False)
    op.create_index(op.f("ix_analysis_jobs_data_file_id"), "analysis_jobs", ["data_file_id"], unique=False)
    op.create_index(op.f("ix_analysis_jobs_retry_of_job_id"), "analysis_jobs", ["retry_of_job_id"], unique=False)
    op.create_index(op.f("ix_analysis_jobs_status"), "analysis_jobs", ["status"], unique=False)

    op.create_table(
        "analysis_results",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("analysis_batch_id", sa.Integer(), nullable=False),
        sa.Column("analysis_job_id", sa.Integer(), nullable=False),
        sa.Column("data_file_id", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(length=40), nullable=False),
        sa.Column("summary", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint(f"status IN {ANALYSIS_STATUSES}", name="ck_analysis_results_status"),
        sa.ForeignKeyConstraint(["analysis_batch_id"], ["analysis_batches.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["analysis_job_id"], ["analysis_jobs.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["data_file_id"], ["data_files.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_analysis_results_analysis_batch_id"), "analysis_results", ["analysis_batch_id"], unique=False)
    op.create_index(op.f("ix_analysis_results_analysis_job_id"), "analysis_results", ["analysis_job_id"], unique=True)
    op.create_index(op.f("ix_analysis_results_data_file_id"), "analysis_results", ["data_file_id"], unique=False)
    op.create_index(op.f("ix_analysis_results_status"), "analysis_results", ["status"], unique=False)

    op.create_table(
        "result_confidence_scores",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("analysis_result_id", sa.Integer(), nullable=False),
        sa.Column("level", sa.String(length=20), nullable=False),
        sa.Column("score", sa.Float(), nullable=True),
        sa.Column("reason", sa.Text(), nullable=True),
        sa.Column("metadata_json", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint("level IN ('RED', 'YELLOW', 'GREEN')", name="ck_result_confidence_scores_level"),
        sa.ForeignKeyConstraint(["analysis_result_id"], ["analysis_results.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_result_confidence_scores_analysis_result_id"), "result_confidence_scores", ["analysis_result_id"], unique=False)
    op.create_index(op.f("ix_result_confidence_scores_level"), "result_confidence_scores", ["level"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_result_confidence_scores_level"), table_name="result_confidence_scores")
    op.drop_index(op.f("ix_result_confidence_scores_analysis_result_id"), table_name="result_confidence_scores")
    op.drop_table("result_confidence_scores")
    op.drop_index(op.f("ix_analysis_results_status"), table_name="analysis_results")
    op.drop_index(op.f("ix_analysis_results_data_file_id"), table_name="analysis_results")
    op.drop_index(op.f("ix_analysis_results_analysis_job_id"), table_name="analysis_results")
    op.drop_index(op.f("ix_analysis_results_analysis_batch_id"), table_name="analysis_results")
    op.drop_table("analysis_results")
    op.drop_index(op.f("ix_analysis_jobs_status"), table_name="analysis_jobs")
    op.drop_index(op.f("ix_analysis_jobs_retry_of_job_id"), table_name="analysis_jobs")
    op.drop_index(op.f("ix_analysis_jobs_data_file_id"), table_name="analysis_jobs")
    op.drop_index(op.f("ix_analysis_jobs_analysis_batch_id"), table_name="analysis_jobs")
    op.drop_table("analysis_jobs")
    op.drop_index(op.f("ix_analysis_batches_upload_batch_id"), table_name="analysis_batches")
    op.drop_index(op.f("ix_analysis_batches_template_id"), table_name="analysis_batches")
    op.drop_index(op.f("ix_analysis_batches_status"), table_name="analysis_batches")
    op.drop_index(op.f("ix_analysis_batches_requested_by_user_id"), table_name="analysis_batches")
    op.drop_index(op.f("ix_analysis_batches_plan_id"), table_name="analysis_batches")
    op.drop_table("analysis_batches")
