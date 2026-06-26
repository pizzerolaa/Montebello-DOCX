from __future__ import annotations

from pydantic import BaseModel, ConfigDict


class LotRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    lot_number: str
    description: str | None = None

