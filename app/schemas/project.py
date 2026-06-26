from __future__ import annotations

from pydantic import BaseModel, ConfigDict


class ProjectCreate(BaseModel):
    name: str
    center_name: str | None = None


class ProjectRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    name: str
    center_name: str | None = None
    status: str

