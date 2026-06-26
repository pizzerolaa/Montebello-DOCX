from __future__ import annotations

from pydantic import BaseModel, ConfigDict


class EquipmentWorkItemRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    sequence: int
    title: str | None = None
    description: str
    is_custom: bool

