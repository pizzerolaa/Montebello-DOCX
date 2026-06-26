from __future__ import annotations

from pydantic import BaseModel, ConfigDict


class EquipmentRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    sequence: int
    equipment_type: str
    zone: str | None = None
    brand: str | None = None
    capacity: str | None = None
    serial: str | None = None

