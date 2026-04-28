from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import Any

from sqlalchemy import DateTime, ForeignKey, JSON, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class AnalysisStatus(StrEnum):
    PENDING = "PENDING"
    QUEUED = "QUEUED"
    RUNNING = "RUNNING"
    PAUSED = "PAUSED"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"


class AnalysisBatch(Base):
    __tablename__ = "analysis_batches"

    id: Mapped[int] = mapped_column(primary_key=True)
    upload_batch_id: Mapped[int] = mapped_column(
        ForeignKey("upload_batches.id", ondelete="RESTRICT"),
        index=True,
    )
    plan_id: Mapped[int | None] = mapped_column(
        ForeignKey("analysis_plans.id", ondelete="SET NULL"),
        index=True,
    )
    template_id: Mapped[int | None] = mapped_column(
        ForeignKey("analysis_templates.id", ondelete="SET NULL"),
        index=True,
    )
    requested_by_user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT"),
        index=True,
    )
    status: Mapped[str] = mapped_column(String(40), nullable=False, default=AnalysisStatus.QUEUED.value, index=True)
    total_jobs: Mapped[int] = mapped_column(nullable=False, default=0)
    completed_jobs: Mapped[int] = mapped_column(nullable=False, default=0)
    failed_jobs: Mapped[int] = mapped_column(nullable=False, default=0)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )

    jobs: Mapped[list[AnalysisJob]] = relationship(
        back_populates="batch",
        cascade="all, delete-orphan",
        lazy="selectin",
        order_by="AnalysisJob.id",
    )
    results: Mapped[list[AnalysisResult]] = relationship(
        back_populates="batch",
        cascade="all, delete-orphan",
        lazy="selectin",
        order_by="AnalysisResult.id",
    )


class AnalysisJob(Base):
    __tablename__ = "analysis_jobs"

    id: Mapped[int] = mapped_column(primary_key=True)
    analysis_batch_id: Mapped[int] = mapped_column(
        ForeignKey("analysis_batches.id", ondelete="CASCADE"),
        index=True,
    )
    data_file_id: Mapped[int] = mapped_column(
        ForeignKey("data_files.id", ondelete="RESTRICT"),
        index=True,
    )
    retry_of_job_id: Mapped[int | None] = mapped_column(
        ForeignKey("analysis_jobs.id", ondelete="SET NULL"),
        index=True,
    )
    status: Mapped[str] = mapped_column(String(40), nullable=False, default=AnalysisStatus.QUEUED.value, index=True)
    attempt: Mapped[int] = mapped_column(nullable=False, default=1)
    logs: Mapped[list[dict[str, Any]]] = mapped_column(JSON, nullable=False, default=list)
    error_message: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )

    batch: Mapped[AnalysisBatch] = relationship(back_populates="jobs")
    retry_of_job: Mapped[AnalysisJob | None] = relationship(remote_side=[id])
    result: Mapped[AnalysisResult | None] = relationship(
        back_populates="job",
        cascade="all, delete-orphan",
        lazy="selectin",
    )


class AnalysisResult(Base):
    __tablename__ = "analysis_results"

    id: Mapped[int] = mapped_column(primary_key=True)
    analysis_batch_id: Mapped[int] = mapped_column(
        ForeignKey("analysis_batches.id", ondelete="CASCADE"),
        index=True,
    )
    analysis_job_id: Mapped[int] = mapped_column(
        ForeignKey("analysis_jobs.id", ondelete="CASCADE"),
        unique=True,
        index=True,
    )
    data_file_id: Mapped[int] = mapped_column(
        ForeignKey("data_files.id", ondelete="RESTRICT"),
        index=True,
    )
    status: Mapped[str] = mapped_column(String(40), nullable=False, default=AnalysisStatus.PENDING.value, index=True)
    summary: Mapped[dict[str, Any] | None] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )

    batch: Mapped[AnalysisBatch] = relationship(back_populates="results")
    job: Mapped[AnalysisJob] = relationship(back_populates="result")
    confidence_scores: Mapped[list[ResultConfidenceScore]] = relationship(
        back_populates="result",
        cascade="all, delete-orphan",
        lazy="selectin",
        order_by="ResultConfidenceScore.id",
    )
    gates: Mapped[list[ResultGate]] = relationship(
        back_populates="result",
        cascade="all, delete-orphan",
        lazy="selectin",
        order_by="ResultGate.id",
    )
    statistics: Mapped[list[ResultStatistic]] = relationship(
        back_populates="result",
        cascade="all, delete-orphan",
        lazy="selectin",
        order_by="ResultStatistic.id",
    )


class ResultGate(Base):
    __tablename__ = "result_gates"

    id: Mapped[int] = mapped_column(primary_key=True)
    analysis_result_id: Mapped[int] = mapped_column(
        ForeignKey("analysis_results.id", ondelete="CASCADE"),
        index=True,
    )
    gate_key: Mapped[str] = mapped_column(String(120), index=True)
    gate_name: Mapped[str] = mapped_column(String(200))
    gate_type: Mapped[str] = mapped_column(String(80), index=True)
    definition: Mapped[dict[str, Any]] = mapped_column(JSON)
    event_count: Mapped[int] = mapped_column(nullable=False)
    parent_event_count: Mapped[int | None] = mapped_column()
    mask: Mapped[list[bool]] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )

    result: Mapped[AnalysisResult] = relationship(back_populates="gates")


class ResultStatistic(Base):
    __tablename__ = "result_statistics"

    id: Mapped[int] = mapped_column(primary_key=True)
    analysis_result_id: Mapped[int] = mapped_column(
        ForeignKey("analysis_results.id", ondelete="CASCADE"),
        index=True,
    )
    name: Mapped[str] = mapped_column(String(200), index=True)
    statistic_type: Mapped[str] = mapped_column(String(80), index=True)
    value: Mapped[dict[str, Any] | None] = mapped_column(JSON)
    unit: Mapped[str | None] = mapped_column(String(80))
    metadata_json: Mapped[dict[str, Any] | None] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )

    result: Mapped[AnalysisResult] = relationship(back_populates="statistics")


class ResultConfidenceScore(Base):
    __tablename__ = "result_confidence_scores"

    id: Mapped[int] = mapped_column(primary_key=True)
    analysis_result_id: Mapped[int] = mapped_column(
        ForeignKey("analysis_results.id", ondelete="CASCADE"),
        index=True,
    )
    level: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    score: Mapped[float | None] = mapped_column()
    reason: Mapped[str | None] = mapped_column(Text)
    metadata_json: Mapped[dict[str, Any] | None] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )

    result: Mapped[AnalysisResult] = relationship(back_populates="confidence_scores")
