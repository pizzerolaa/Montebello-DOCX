from __future__ import annotations

import re
from dataclasses import dataclass

from app.services.docx_reader import DocumentBlock, canonical_text, clean_label_value, normalize_spaces
from app.services.equipment_format import normalize_serial
from app.services.extraction_models import ParsedEquipment
from app.services.minisplit_parser import build_minisplit_work_items
from app.services.package_parser import build_package_work_items


LABEL_PATTERNS = {
    "lot_number": re.compile(r"\bLOTE\s*:?\s*(?P<value>[A-Z0-9.-]+)", re.IGNORECASE),
    "equipment_type": re.compile(r"TIPO\s+DE\s+UNIDAD\s*:?\s*(?P<value>.+)", re.IGNORECASE),
    "zone": re.compile(r"ZONA(?:\s+DE\s+EQUIPO)?\s*:?\s*(?P<value>.+)", re.IGNORECASE),
    "brand": re.compile(r"MARCA\s*:?\s*(?P<value>.+)", re.IGNORECASE),
    "capacity": re.compile(r"CAPACIDAD\s*:?\s*(?P<value>.+)", re.IGNORECASE),
    "serial": re.compile(r"SERIE\s*:?\s*(?P<value>.+)", re.IGNORECASE),
}


STOP_HEADINGS = {
    "REPORTE FOTOGRAFICO",
    "SIN OTRO PARTICULAR",
    "ATENTAMENTE",
    "ENTREGA",
    "RECIBIO",
}


@dataclass
class EquipmentTextBlock:
    lines: list[str]
    source_order: int

    @property
    def source_text(self) -> str:
        return "\n".join(self.lines)


def normalize_equipment_type(value: str | None) -> str:
    """Normalize known equipment type labels."""
    canonical = canonical_text(value or "")
    if "CAMARA" in canonical and ("FRIA" in canonical or "REFRIGERACION" in canonical):
        return "COLD_ROOM"
    if "PAQUETE" in canonical or "PACKAGE" in canonical:
        return "PACKAGE"
    if "MINISPLIT" in canonical or "MINI SPLIT" in canonical:
        return "MINISPLIT"
    return "UNKNOWN"


def normalize_zone(line: str, value: str | None) -> str | None:
    """Normalize zone labels, including package headings like ZONA DE EQUIPO 01."""
    cleaned = clean_label_value(value or "")
    if not cleaned:
        return None
    cleaned = re.sub(r"^DE\s+", "", cleaned, flags=re.IGNORECASE).strip()
    cleaned = re.sub(r"\s+DE\s+TIPO\s+PAQUETE\.?$", "", cleaned, flags=re.IGNORECASE).strip(" .")
    if "ZONA DE EQUIPO" in canonical_text(line):
        equipment_number = re.match(r"(?P<number>\d{1,3})\b", cleaned)
        if equipment_number:
            return f"EQUIPO {equipment_number.group('number')}"
        if "EQUIPO" in canonical_text(cleaned):
            return cleaned
        return f"EQUIPO {cleaned}"
    return cleaned


def normalize_capacity(value: str | None) -> str | None:
    """Reduce capacity text to a compact tonnage value such as 20 TON or 1 TON."""
    cleaned = clean_label_value(value or "")
    if not cleaned:
        return None
    match = re.search(r"(?:\bDE\s+)?(?P<number>\d+(?:[.,]\d+)?)\s*(?:TONELADAS?|TON\.?)\b", cleaned, re.IGNORECASE)
    if not match:
        return cleaned
    number = match.group("number").replace(",", ".")
    if "." in number:
        number = number.rstrip("0").rstrip(".")
    else:
        number = str(int(number))
    return f"{number} TON"


def extract_equipment(blocks: list[DocumentBlock], source_document_id: str) -> list[ParsedEquipment]:
    """Extract equipment records from work-report style text blocks."""
    text_blocks = split_equipment_blocks(blocks)
    equipment: list[ParsedEquipment] = []
    for text_block in text_blocks:
        parsed = parse_equipment_block(text_block, source_document_id)
        if parsed:
            equipment.append(parsed)
    return equipment


def split_equipment_blocks(blocks: list[DocumentBlock]) -> list[EquipmentTextBlock]:
    """Split ordered text into probable equipment blocks."""
    results: list[EquipmentTextBlock] = []
    current: list[str] = []
    current_order = 0
    has_equipment_label = False

    for block in blocks:
        text = normalize_spaces(block.text)
        if not text:
            continue
        key = canonical_text(text)
        starts_report = "REPORTE DE TRABAJO" in key
        if starts_report and current:
            if has_equipment_label and _has_report(current) and _block_complete(current):
                results.append(EquipmentTextBlock(lines=current, source_order=current_order))
            current = []
            has_equipment_label = False

        starts_type = "TIPO DE UNIDAD" in key and has_equipment_label
        starts_heading = bool(re.search(r"\bZONA\s+DE\s+EQUIPO\s+\d+", key) and _block_complete(current))
        stop = any(heading in key for heading in STOP_HEADINGS)

        if (starts_type or starts_heading or stop) and current and has_equipment_label:
            results.append(EquipmentTextBlock(lines=current, source_order=current_order))
            current = []
            has_equipment_label = False
        if stop:
            continue
        if not current:
            current_order = block.order
        current.append(text)
        if "TIPO DE UNIDAD" in key or "SERIE" in key or "MARCA" in key:
            has_equipment_label = True

    if current and has_equipment_label:
        results.append(EquipmentTextBlock(lines=current, source_order=current_order))
    return results


def _block_complete(lines: list[str]) -> bool:
    joined = canonical_text("\n".join(lines))
    return "TIPO DE UNIDAD" in joined and ("SERIE" in joined or "ACTIVIDADES REALIZADAS" in joined)


def _has_report(lines: list[str]) -> bool:
    return "REPORTE DE TRABAJO" in canonical_text("\n".join(lines))


def parse_equipment_block(block: EquipmentTextBlock, source_document_id: str) -> ParsedEquipment | None:
    fields: dict[str, str] = {}
    for line in block.lines:
        for field_name, pattern in LABEL_PATTERNS.items():
            match = pattern.search(line)
            if match and field_name not in fields:
                fields[field_name] = _normalize_field_value(field_name, line, match.group("value"))

    equipment_type = normalize_equipment_type(fields.get("equipment_type"))
    if equipment_type == "UNKNOWN":
        equipment_type = normalize_equipment_type(block.source_text)
    if equipment_type == "UNKNOWN" and not any(fields.get(field) for field in ("zone", "brand", "serial")):
        return None

    activity_text = _section_text(
        block.lines,
        start_labels=["ACTIVIDADES REALIZADAS", "MANTENIMIENTO REALIZADO", "TRABAJOS REALIZADOS"],
        stop_labels=["PIEZAS SUSTITUIDAS", "FINALMENTE", "ATENTAMENTE"],
    )
    corrective_text = _section_text(
        block.lines,
        start_labels=["PIEZAS SUSTITUIDAS", "CORRECCIONES REALIZADAS", "SE MENCIONAN A CONTINUACION"],
        stop_labels=["FINALMENTE", "ATENTAMENTE", "REPORTE DE TRABAJO"],
    )

    if equipment_type == "COLD_ROOM" and not fields.get("zone") and fields.get("equipment_type"):
        fields["zone"] = fields["equipment_type"].rstrip(".")

    work_source = corrective_text or activity_text or block.source_text
    if equipment_type in {"PACKAGE", "COLD_ROOM"}:
        work_items = build_package_work_items(work_source)
    else:
        work_items = build_minisplit_work_items(work_source)

    confidence = 0.9 if fields.get("serial") and equipment_type != "UNKNOWN" else 0.65
    return ParsedEquipment(
        equipment_type=equipment_type,
        lot_number=fields.get("lot_number"),
        zone=fields.get("zone"),
        brand=fields.get("brand"),
        capacity=fields.get("capacity"),
        serial=fields.get("serial"),
        source_text=block.source_text,
        source_document_id=source_document_id,
        source_order=block.source_order,
        confidence=confidence,
        work_items=work_items,
    )


def _normalize_field_value(field_name: str, line: str, value: str) -> str:
    if field_name == "zone":
        return normalize_zone(line, value) or ""
    if field_name == "capacity":
        return normalize_capacity(value) or ""
    if field_name == "serial":
        return normalize_serial(clean_label_value(value))
    if field_name == "lot_number":
        return clean_label_value(value).rstrip(".")
    return clean_label_value(value)


def _section_text(lines: list[str], start_labels: list[str], stop_labels: list[str]) -> str:
    collecting = False
    collected: list[str] = []
    for line in lines:
        key = canonical_text(line)
        if not collecting and any(label in key for label in start_labels):
            collecting = True
            value = line.split(":", 1)[1] if ":" in line else ""
            if clean_label_value(value):
                collected.append(clean_label_value(value))
            continue
        if collecting and any(label in key for label in stop_labels):
            break
        if collecting:
            collected.append(line)
    return "\n".join(line for line in collected if normalize_spaces(line))
