from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base
from app.models.enums import EquipmentType
from app.models.project import new_uuid
from app.models.time import utc_now


if TYPE_CHECKING:
    from app.models.lot import Lot
    from app.models.project import Project
    from app.models.source_document import SourceDocument
    from app.models.work_item import EquipmentWorkItem


class Equipment(Base):
    __tablename__ = "equipment"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    project_id: Mapped[str] = mapped_column(ForeignKey("projects.id"), nullable=False, index=True)
    lot_id: Mapped[str | None] = mapped_column(ForeignKey("lots.id"), nullable=True)
    source_document_id: Mapped[str | None] = mapped_column(ForeignKey("source_documents.id"), nullable=True)
    sequence: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    equipment_type: Mapped[str] = mapped_column(String(40), default=EquipmentType.UNKNOWN.value, nullable=False)
    zone: Mapped[str | None] = mapped_column(String(500), nullable=True)
    brand: Mapped[str | None] = mapped_column(String(255), nullable=True)
    capacity: Mapped[str | None] = mapped_column(String(255), nullable=True)
    serial: Mapped[str | None] = mapped_column(String(255), nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    extraction_confidence: Mapped[float | None] = mapped_column(Float, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=utc_now, onupdate=utc_now, nullable=False
    )

    project: Mapped["Project"] = relationship(back_populates="equipment")
    lot: Mapped["Lot | None"] = relationship(back_populates="equipment")
    source_document: Mapped["SourceDocument | None"] = relationship(back_populates="equipment")
    work_items: Mapped[list["EquipmentWorkItem"]] = relationship(
        back_populates="equipment", cascade="all, delete-orphan"
    )
