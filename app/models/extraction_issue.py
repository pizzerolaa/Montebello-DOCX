from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, DateTime, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base
from app.models.enums import IssueSeverity
from app.models.project import new_uuid
from app.models.time import utc_now


if TYPE_CHECKING:
    from app.models.project import Project
    from app.models.source_document import SourceDocument


class ExtractionIssue(Base):
    __tablename__ = "extraction_issues"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    project_id: Mapped[str] = mapped_column(ForeignKey("projects.id"), nullable=False, index=True)
    source_document_id: Mapped[str | None] = mapped_column(ForeignKey("source_documents.id"), nullable=True)
    entity_type: Mapped[str | None] = mapped_column(String(80), nullable=True)
    entity_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    severity: Mapped[str] = mapped_column(String(40), default=IssueSeverity.WARNING.value, nullable=False)
    field_name: Mapped[str | None] = mapped_column(String(120), nullable=True)
    message: Mapped[str] = mapped_column(Text, nullable=False)
    detected_value: Mapped[str | None] = mapped_column(Text, nullable=True)
    resolved_value: Mapped[str | None] = mapped_column(Text, nullable=True)
    resolved: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now, nullable=False)

    project: Mapped["Project"] = relationship(back_populates="extraction_issues")
    source_document: Mapped["SourceDocument | None"] = relationship(back_populates="extraction_issues")
