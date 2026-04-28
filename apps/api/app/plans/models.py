from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import DateTime, Float, ForeignKey, JSON, String, Text, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class AnalysisPlan(Base):
    __tablename__ = "analysis_plans"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(200), index=True)
    project_id: Mapped[int] = mapped_column(
        ForeignKey("projects.id", ondelete="RESTRICT"),
        index=True,
    )
    description: Mapped[str | None] = mapped_column(Text)
    created_by_user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT"),
        index=True,
    )
    current_version: Mapped[int] = mapped_column(nullable=False, default=1)
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

    template_bindings: Mapped[list[PlanTemplateBinding]] = relationship(
        back_populates="plan",
        cascade="all, delete-orphan",
        lazy="selectin",
        order_by="PlanTemplateBinding.sort_order",
    )
    cell_label_nodes: Mapped[list[CellLabelNode]] = relationship(
        back_populates="plan",
        cascade="all, delete-orphan",
        foreign_keys="CellLabelNode.plan_id",
        lazy="selectin",
        order_by="CellLabelNode.sort_order",
    )
    marker_thresholds: Mapped[list[MarkerThreshold]] = relationship(
        back_populates="plan",
        cascade="all, delete-orphan",
        lazy="selectin",
        order_by="MarkerThreshold.id",
    )
    versions: Mapped[list[AnalysisPlanVersion]] = relationship(
        back_populates="plan",
        cascade="all, delete-orphan",
        lazy="selectin",
        order_by="AnalysisPlanVersion.version",
    )


class AnalysisPlanVersion(Base):
    __tablename__ = "analysis_plan_versions"
    __table_args__ = (UniqueConstraint("plan_id", "version"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    plan_id: Mapped[int] = mapped_column(
        ForeignKey("analysis_plans.id", ondelete="CASCADE"),
        index=True,
    )
    version: Mapped[int] = mapped_column(nullable=False, index=True)
    snapshot_json: Mapped[dict[str, Any]] = mapped_column(JSON)
    change_note: Mapped[str] = mapped_column(Text)
    created_by: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT"),
        index=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )

    plan: Mapped[AnalysisPlan] = relationship(back_populates="versions")


class PlanTemplateBinding(Base):
    __tablename__ = "plan_template_bindings"
    __table_args__ = (UniqueConstraint("plan_id", "experiment_no", "tube_no", "template_id"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    plan_id: Mapped[int] = mapped_column(
        ForeignKey("analysis_plans.id", ondelete="CASCADE"),
        index=True,
    )
    template_id: Mapped[int] = mapped_column(
        ForeignKey("analysis_templates.id", ondelete="RESTRICT"),
        index=True,
    )
    experiment_no: Mapped[str | None] = mapped_column(String(120), index=True)
    tube_no: Mapped[str] = mapped_column(String(80), index=True)
    config: Mapped[dict[str, Any] | None] = mapped_column(JSON)
    sort_order: Mapped[int] = mapped_column(nullable=False, default=0)

    plan: Mapped[AnalysisPlan] = relationship(back_populates="template_bindings")


class CellLabelNode(Base):
    __tablename__ = "cell_label_nodes"
    __table_args__ = (UniqueConstraint("plan_id", "code"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    plan_id: Mapped[int] = mapped_column(
        ForeignKey("analysis_plans.id", ondelete="CASCADE"),
        index=True,
    )
    parent_node_id: Mapped[int | None] = mapped_column(
        ForeignKey("cell_label_nodes.id", ondelete="SET NULL"),
        index=True,
    )
    code: Mapped[str] = mapped_column(String(120), index=True)
    name: Mapped[str] = mapped_column(String(200))
    description: Mapped[str | None] = mapped_column(Text)
    sort_order: Mapped[int] = mapped_column(nullable=False, default=0)

    plan: Mapped[AnalysisPlan] = relationship(
        back_populates="cell_label_nodes",
        foreign_keys=[plan_id],
    )
    parent_node: Mapped[CellLabelNode | None] = relationship(
        remote_side=[id],
        foreign_keys=[parent_node_id],
    )


class MarkerThreshold(Base):
    __tablename__ = "marker_thresholds"
    __table_args__ = (UniqueConstraint("plan_id", "marker", "channel_name", "threshold_type"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    plan_id: Mapped[int] = mapped_column(
        ForeignKey("analysis_plans.id", ondelete="CASCADE"),
        index=True,
    )
    label_node_id: Mapped[int | None] = mapped_column(
        ForeignKey("cell_label_nodes.id", ondelete="SET NULL"),
        index=True,
    )
    marker: Mapped[str] = mapped_column(String(120), index=True)
    channel_name: Mapped[str] = mapped_column(String(120), index=True)
    threshold_type: Mapped[str] = mapped_column(String(80), index=True)
    threshold_value: Mapped[float] = mapped_column(Float)
    config: Mapped[dict[str, Any] | None] = mapped_column(JSON)

    plan: Mapped[AnalysisPlan] = relationship(back_populates="marker_thresholds")
