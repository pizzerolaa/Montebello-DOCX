from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import Boolean, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base
from app.models.project import new_uuid


if TYPE_CHECKING:
    from app.models.equipment import Equipment


class WorkCatalogItem(Base):
    __tablename__ = "work_catalog_items"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    code: Mapped[str] = mapped_column(String(40), unique=True, nullable=False)
    equipment_type: Mapped[str] = mapped_column(String(40), nullable=False)
    component: Mapped[str] = mapped_column(String(255), nullable=False)
    default_description: Mapped[str] = mapped_column(Text, nullable=False)
    active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    equipment_work_items: Mapped[list["EquipmentWorkItem"]] = relationship(back_populates="catalog_item")


class EquipmentWorkItem(Base):
    __tablename__ = "equipment_work_items"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    equipment_id: Mapped[str] = mapped_column(ForeignKey("equipment.id"), nullable=False, index=True)
    catalog_item_id: Mapped[str | None] = mapped_column(ForeignKey("work_catalog_items.id"), nullable=True)
    sequence: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    title: Mapped[str | None] = mapped_column(String(255), nullable=True)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    source_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_custom: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    equipment: Mapped["Equipment"] = relationship(back_populates="work_items")
    catalog_item: Mapped["WorkCatalogItem | None"] = relationship(back_populates="equipment_work_items")
