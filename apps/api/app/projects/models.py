from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import DateTime, ForeignKey, JSON, String, Text, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class Project(Base):
    __tablename__ = "projects"

    id: Mapped[int] = mapped_column(primary_key=True)
    code: Mapped[str] = mapped_column(String(80), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(200))
    description: Mapped[str | None] = mapped_column(Text)
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

    experiments: Mapped[list[Experiment]] = relationship(
        back_populates="project",
        cascade="all, delete-orphan",
        lazy="selectin",
    )


class Experiment(Base):
    __tablename__ = "experiments"

    id: Mapped[int] = mapped_column(primary_key=True)
    project_id: Mapped[int] = mapped_column(
        ForeignKey("projects.id", ondelete="RESTRICT"),
        index=True,
    )
    experiment_no: Mapped[str] = mapped_column(String(120), unique=True, index=True)
    name: Mapped[str | None] = mapped_column(String(200))
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

    project: Mapped[Project] = relationship(back_populates="experiments")
    samples: Mapped[list[Sample]] = relationship(
        back_populates="experiment",
        cascade="all, delete-orphan",
        lazy="selectin",
    )


class Sample(Base):
    __tablename__ = "samples"
    __table_args__ = (UniqueConstraint("experiment_id", "sample_no"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    experiment_id: Mapped[int] = mapped_column(
        ForeignKey("experiments.id", ondelete="RESTRICT"),
        index=True,
    )
    sample_no: Mapped[str] = mapped_column(String(120), index=True)
    subject_identifier: Mapped[str | None] = mapped_column(String(120))
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

    experiment: Mapped[Experiment] = relationship(back_populates="samples")
    tubes: Mapped[list[Tube]] = relationship(
        back_populates="sample",
        cascade="all, delete-orphan",
        lazy="selectin",
    )


class Tube(Base):
    __tablename__ = "tubes"
    __table_args__ = (UniqueConstraint("sample_id", "tube_no"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    sample_id: Mapped[int] = mapped_column(
        ForeignKey("samples.id", ondelete="RESTRICT"),
        index=True,
    )
    tube_no: Mapped[str] = mapped_column(String(80), index=True)
    group_name: Mapped[str | None] = mapped_column(String(120))
    experimental_condition: Mapped[str | None] = mapped_column(Text)
    antibody_info: Mapped[dict[str, Any] | None] = mapped_column(JSON)
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

    sample: Mapped[Sample] = relationship(back_populates="tubes")
    channels: Mapped[list[Channel]] = relationship(
        back_populates="tube",
        cascade="all, delete-orphan",
        lazy="selectin",
    )
    marker_mappings: Mapped[list[MarkerMapping]] = relationship(
        back_populates="tube",
        cascade="all, delete-orphan",
        lazy="selectin",
    )
    compensation_matrices: Mapped[list[CompensationMatrix]] = relationship(
        back_populates="tube",
        cascade="all, delete-orphan",
        lazy="selectin",
    )
    data_files: Mapped[list[DataFile]] = relationship(
        "DataFile",
        back_populates="tube",
        lazy="selectin",
    )


class Channel(Base):
    __tablename__ = "channels"
    __table_args__ = (UniqueConstraint("tube_id", "name"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    tube_id: Mapped[int] = mapped_column(
        ForeignKey("tubes.id", ondelete="CASCADE"),
        index=True,
    )
    name: Mapped[str] = mapped_column(String(120), index=True)
    detector: Mapped[str | None] = mapped_column(String(120))
    fluorochrome: Mapped[str | None] = mapped_column(String(120))
    marker: Mapped[str | None] = mapped_column(String(120))
    channel_index: Mapped[int | None] = mapped_column()

    tube: Mapped[Tube] = relationship(back_populates="channels")


class MarkerMapping(Base):
    __tablename__ = "marker_mappings"
    __table_args__ = (UniqueConstraint("tube_id", "marker", "channel_name"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    tube_id: Mapped[int] = mapped_column(
        ForeignKey("tubes.id", ondelete="CASCADE"),
        index=True,
    )
    marker: Mapped[str] = mapped_column(String(120), index=True)
    channel_name: Mapped[str] = mapped_column(String(120), index=True)
    fluorochrome: Mapped[str | None] = mapped_column(String(120))

    tube: Mapped[Tube] = relationship(back_populates="marker_mappings")


class CompensationMatrix(Base):
    __tablename__ = "compensation_matrices"
    __table_args__ = (UniqueConstraint("tube_id", "version"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    tube_id: Mapped[int] = mapped_column(
        ForeignKey("tubes.id", ondelete="CASCADE"),
        index=True,
    )
    version: Mapped[int] = mapped_column()
    matrix: Mapped[dict[str, Any]] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )

    tube: Mapped[Tube] = relationship(back_populates="compensation_matrices")
