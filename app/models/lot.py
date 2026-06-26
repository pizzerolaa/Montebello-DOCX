from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base
from app.models.project import new_uuid


if TYPE_CHECKING:
    from app.models.equipment import Equipment
    from app.models.project import Project
    from app.models.source_document import SourceDocument


class Lot(Base):
    __tablename__ = "lots"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    project_id: Mapped[str] = mapped_column(ForeignKey("projects.id"), nullable=False, index=True)
    lot_number: Mapped[str] = mapped_column(String(100), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    source_document_id: Mapped[str | None] = mapped_column(ForeignKey("source_documents.id"), nullable=True)

    project: Mapped["Project"] = relationship(back_populates="lots")
    source_document: Mapped["SourceDocument | None"] = relationship(back_populates="lots")
    equipment: Mapped[list["Equipment"]] = relationship(back_populates="lot")
