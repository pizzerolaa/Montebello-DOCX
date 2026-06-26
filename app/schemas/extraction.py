from __future__ import annotations

from pydantic import BaseModel, ConfigDict


class ExtractionIssueRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    severity: str
    field_name: str | None = None
    message: str
    resolved: bool

