from __future__ import annotations

from datetime import datetime

from sqlalchemy import BigInteger, DateTime, ForeignKey, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class UploadBatch(Base):
    __tablename__ = "upload_batches"

    id: Mapped[int] = mapped_column(primary_key=True)
    status: Mapped[str] = mapped_column(String(40), nullable=False, default="completed")
    uploaded_by_user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT"),
        index=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )

    files: Mapped[list[DataFile]] = relationship(
        back_populates="batch",
        cascade="all, delete-orphan",
        lazy="selectin",
    )


class DataFile(Base):
    __tablename__ = "data_files"

    id: Mapped[int] = mapped_column(primary_key=True)
    upload_batch_id: Mapped[int] = mapped_column(
        ForeignKey("upload_batches.id", ondelete="CASCADE"),
        index=True,
    )
    tube_id: Mapped[int | None] = mapped_column(
        ForeignKey("tubes.id", ondelete="SET NULL"),
        index=True,
    )
    uploaded_by_user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT"),
        index=True,
    )
    original_filename: Mapped[str] = mapped_column(String(255))
    file_extension: Mapped[str] = mapped_column(String(20), index=True)
    content_type: Mapped[str | None] = mapped_column(String(120))
    object_bucket: Mapped[str] = mapped_column(String(120))
    object_key: Mapped[str] = mapped_column(String(512), unique=True, index=True)
    file_size: Mapped[int] = mapped_column(BigInteger)
    sha256: Mapped[str] = mapped_column(String(64), index=True)
    uploaded_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )

    batch: Mapped[UploadBatch] = relationship(back_populates="files")
    tube: Mapped[Tube | None] = relationship("Tube", back_populates="data_files")
