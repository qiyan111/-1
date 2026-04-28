from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import DateTime, ForeignKey, JSON, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class AnalysisTemplate(Base):
    __tablename__ = "analysis_templates"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(200), index=True)
    project_code: Mapped[str] = mapped_column(String(80), index=True)
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

    plots: Mapped[list[TemplatePlot]] = relationship(
        back_populates="template",
        cascade="all, delete-orphan",
        lazy="selectin",
        order_by="TemplatePlot.sort_order",
    )
    gates: Mapped[list[TemplateGate]] = relationship(
        back_populates="template",
        cascade="all, delete-orphan",
        foreign_keys="TemplateGate.template_id",
        lazy="selectin",
        order_by="TemplateGate.sort_order",
    )
    logic_gates: Mapped[list[TemplateLogicGate]] = relationship(
        back_populates="template",
        cascade="all, delete-orphan",
        lazy="selectin",
        order_by="TemplateLogicGate.sort_order",
    )
    statistics: Mapped[list[TemplateStatistic]] = relationship(
        back_populates="template",
        cascade="all, delete-orphan",
        lazy="selectin",
        order_by="TemplateStatistic.sort_order",
    )


class TemplatePlot(Base):
    __tablename__ = "template_plots"

    id: Mapped[int] = mapped_column(primary_key=True)
    template_id: Mapped[int] = mapped_column(
        ForeignKey("analysis_templates.id", ondelete="CASCADE"),
        index=True,
    )
    title: Mapped[str | None] = mapped_column(String(200))
    tube_no: Mapped[str | None] = mapped_column(String(80), index=True)
    x_channel: Mapped[str | None] = mapped_column(String(120))
    y_channel: Mapped[str | None] = mapped_column(String(120))
    plot_type: Mapped[str] = mapped_column(String(40), index=True)
    config: Mapped[dict[str, Any] | None] = mapped_column(JSON)
    sort_order: Mapped[int] = mapped_column(nullable=False, default=0)

    template: Mapped[AnalysisTemplate] = relationship(back_populates="plots")


class TemplateGate(Base):
    __tablename__ = "template_gates"

    id: Mapped[int] = mapped_column(primary_key=True)
    template_id: Mapped[int] = mapped_column(
        ForeignKey("analysis_templates.id", ondelete="CASCADE"),
        index=True,
    )
    parent_gate_id: Mapped[int | None] = mapped_column(
        ForeignKey("template_gates.id", ondelete="SET NULL"),
        index=True,
    )
    parent_gate_key: Mapped[str | None] = mapped_column(String(120), index=True)
    gate_key: Mapped[str] = mapped_column(String(120), index=True)
    name: Mapped[str] = mapped_column(String(200))
    gate_type: Mapped[str] = mapped_column(String(80), index=True)
    definition: Mapped[dict[str, Any]] = mapped_column(JSON)
    sort_order: Mapped[int] = mapped_column(nullable=False, default=0)

    template: Mapped[AnalysisTemplate] = relationship(
        back_populates="gates",
        foreign_keys=[template_id],
    )
    parent_gate: Mapped[TemplateGate | None] = relationship(
        remote_side=[id],
        foreign_keys=[parent_gate_id],
    )


class TemplateLogicGate(Base):
    __tablename__ = "template_logic_gates"

    id: Mapped[int] = mapped_column(primary_key=True)
    template_id: Mapped[int] = mapped_column(
        ForeignKey("analysis_templates.id", ondelete="CASCADE"),
        index=True,
    )
    name: Mapped[str] = mapped_column(String(200))
    expression: Mapped[str] = mapped_column(Text)
    definition: Mapped[dict[str, Any] | None] = mapped_column(JSON)
    sort_order: Mapped[int] = mapped_column(nullable=False, default=0)

    template: Mapped[AnalysisTemplate] = relationship(back_populates="logic_gates")


class TemplateStatistic(Base):
    __tablename__ = "template_statistics"

    id: Mapped[int] = mapped_column(primary_key=True)
    template_id: Mapped[int] = mapped_column(
        ForeignKey("analysis_templates.id", ondelete="CASCADE"),
        index=True,
    )
    name: Mapped[str] = mapped_column(String(200))
    rule_type: Mapped[str] = mapped_column(String(80), index=True)
    formula: Mapped[str | None] = mapped_column(Text)
    config: Mapped[dict[str, Any] | None] = mapped_column(JSON)
    sort_order: Mapped[int] = mapped_column(nullable=False, default=0)

    template: Mapped[AnalysisTemplate] = relationship(back_populates="statistics")
