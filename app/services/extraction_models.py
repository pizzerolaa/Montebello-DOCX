from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal


@dataclass(frozen=True)
class FieldCandidate:
    field_name: str
    value: str
    source_document_id: str
    confidence: float
    source_order: int


@dataclass
class ParsedWorkItem:
    title: str | None
    description: str
    source_text: str
    is_custom: bool = True


@dataclass
class ParsedEquipment:
    equipment_type: str
    lot_number: str | None
    zone: str | None
    brand: str | None
    capacity: str | None
    serial: str | None
    source_text: str
    source_document_id: str
    source_order: int
    confidence: float = 0.75
    work_items: list[ParsedWorkItem] = field(default_factory=list)


@dataclass
class ParsedDocument:
    source_document_id: str
    profile: str
    candidates: list[FieldCandidate]
    lot_numbers: list[str]
    equipment: list[ParsedEquipment]
    issues: list[tuple[Literal["INFO", "WARNING", "ERROR"], str, str | None, str | None]] = field(default_factory=list)

