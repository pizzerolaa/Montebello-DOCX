from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base
from app.models.enums import DetectedProfile, ProcessingStatus
from app.models.project import new_uuid
from app.models.time import utc_now


if TYPE_CHECKING:
    from app.models.equipment import Equipment
    from app.models.extraction_issue import ExtractionIssue
    from app.models.lot import Lot
    from app.models.project import Project


class SourceDocument(Base):
    __tablename__ = "source_documents"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    project_id: Mapped[str] = mapped_column(ForeignKey("projects.id"), nullable=False, index=True)
    original_filename: Mapped[str] = mapped_column(String(500), nullable=False)
    safe_filename: Mapped[str] = mapped_column(String(500), nullable=False)
    stored_path: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    sha256: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    file_size: Mapped[int | None] = mapped_column(Integer, nullable=True)
    detected_profile: Mapped[str] = mapped_column(String(40), default=DetectedProfile.UNKNOWN.value, nullable=False)
    processing_status: Mapped[str] = mapped_column(
        String(40), default=ProcessingStatus.UPLOADED.value, nullable=False
    )
    parser_version: Mapped[str] = mapped_column(String(40), default="phase-1", nullable=False)
    uploaded_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now, nullable=False)

    project: Mapped["Project"] = relationship(back_populates="source_documents")
    lots: Mapped[list["Lot"]] = relationship(back_populates="source_document")
    equipment: Mapped[list["Equipment"]] = relationship(back_populates="source_document")
    extraction_issues: Mapped[list["ExtractionIssue"]] = relationship(back_populates="source_document")
