from __future__ import annotations

from collections import Counter
from pathlib import Path
import re

from sqlalchemy.orm import Session

from app.models.enums import ProjectStatus
from app.models.equipment import Equipment
from app.models.extraction_issue import ExtractionIssue
from app.models.project import Project
from app.models.work_item import EquipmentWorkItem
from app.services.docx_reader import canonical_text, read_docx_blocks
from app.services.document_classifier import classify_document
from app.services.extraction_models import ParsedDocument, ParsedEquipment
from app.services.general_parser import apply_general_candidates, parse_general_candidates, sync_lots
from app.services.work_report_parser import extract_equipment


COUNT_RE = re.compile(
    r"(?P<count>\d{1,3})\s+(?:EQUIPOS?\s+)?(?:DE\s+AIRE\s+ACONDICIONADO\s+)?(?:TIPO\s+)?(?P<type>MINISPLIT|PAQUETE|CAMARAS?\s+FRIAS?|CAMARA\s+DE\s+REFRIGERACION)",
    re.IGNORECASE,
)


def analyze_project(db: Session, project: Project) -> list[ExtractionIssue]:
    """Analyze all uploaded documents for a project and persist phase-2 extraction results."""
    _clear_previous_extraction(project)
    parsed_documents: list[ParsedDocument] = []
    all_candidates = []
    all_lots: list[str] = []
    all_equipment: list[ParsedEquipment] = []
    all_declared_counts: dict[str, set[int]] = {"MINISPLIT": set(), "PACKAGE": set(), "COLD_ROOM": set()}

    for document in project.source_documents:
        if not document.stored_path:
            continue
        try:
            blocks = read_docx_blocks(Path(document.stored_path), document.original_filename)
            profile = classify_document(blocks)
            candidates, lots = parse_general_candidates(blocks, document.id)
            equipment = extract_equipment(blocks, document.id)
            declared_counts = extract_declared_counts(blocks)
            document.detected_profile = profile
            document.processing_status = "ANALYZED"
            parsed_documents.append(ParsedDocument(document.id, profile, candidates, lots, equipment))
            all_candidates.extend(candidates)
            all_lots.extend(lots)
            all_equipment.extend(equipment)
            for equipment_type, values in declared_counts.items():
                all_declared_counts[equipment_type].update(values)
        except Exception as exc:  # noqa: BLE001 - keep project alive when one source fails.
            document.processing_status = "FAILED"
            project.extraction_issues.append(
                ExtractionIssue(
                    project_id=project.id,
                    source_document_id=document.id,
                    severity="ERROR",
                    entity_type="SourceDocument",
                    entity_id=document.id,
                    message=f"No se pudo analizar el documento: {exc}",
                )
            )

    issues = apply_general_candidates(project, all_candidates)
    for issue in issues:
        project.extraction_issues.append(issue)

    lot_map = sync_lots(project, [])
    consolidated_equipment = consolidate_parsed_equipment(all_equipment)
    _record_count_conflicts(project, all_declared_counts, consolidated_equipment)
    _persist_equipment(project, lot_map, consolidated_equipment)
    _create_equipment_issues(project)
    project.status = ProjectStatus.NEEDS_REVIEW.value if project.extraction_issues else ProjectStatus.ANALYZED.value
    db.commit()
    db.refresh(project)
    return project.extraction_issues


def extract_declared_counts(blocks) -> dict[str, set[int]]:
    """Extract declared equipment counts from ACTA-like text."""
    counts: dict[str, set[int]] = {"MINISPLIT": set(), "PACKAGE": set(), "COLD_ROOM": set()}
    first_report_order = next((block.order for block in blocks if "REPORTE DE TRABAJO" in canonical_text(block.text)), None)
    for block in blocks:
        if first_report_order is not None and block.order >= first_report_order:
            continue
        for match in COUNT_RE.finditer(block.text):
            equipment_type = _count_equipment_type(match.group("type"))
            counts[equipment_type].add(int(match.group("count")))
    return counts


def _count_equipment_type(value: str) -> str:
    canonical = canonical_text(value)
    if "CAMARA" in canonical:
        return "COLD_ROOM"
    if "PAQUETE" in canonical:
        return "PACKAGE"
    return "MINISPLIT"


def _record_count_conflicts(
    project: Project,
    declared_counts: dict[str, set[int]],
    equipment: list[ParsedEquipment],
) -> None:
    actual = {
        "MINISPLIT": sum(1 for item in equipment if item.equipment_type == "MINISPLIT"),
        "PACKAGE": sum(1 for item in equipment if item.equipment_type == "PACKAGE"),
        "COLD_ROOM": sum(1 for item in equipment if item.equipment_type == "COLD_ROOM"),
    }
    for equipment_type, declared in declared_counts.items():
        if not declared:
            continue
        if len(declared) > 1:
            project.extraction_issues.append(
                ExtractionIssue(
                    project_id=project.id,
                    severity="WARNING",
                    entity_type="Project",
                    field_name=f"declared_{equipment_type.lower()}_count",
                    message=f"Se detectaron conteos declarados conflictivos para {equipment_type}: {sorted(declared)}.",
                    detected_value=", ".join(str(value) for value in sorted(declared)),
                )
            )
        if actual[equipment_type] and actual[equipment_type] not in declared:
            project.extraction_issues.append(
                ExtractionIssue(
                    project_id=project.id,
                    severity="WARNING",
                    entity_type="Project",
                    field_name=f"declared_{equipment_type.lower()}_count",
                    message=f"Conteo declarado {equipment_type}: {sorted(declared)}; equipos extraidos: {actual[equipment_type]}.",
                    detected_value=", ".join(str(value) for value in sorted(declared)),
                    resolved_value=str(actual[equipment_type]),
                )
            )


def _clear_previous_extraction(project: Project) -> None:
    project.equipment.clear()
    project.lots.clear()
    project.extraction_issues.clear()


def consolidate_parsed_equipment(parsed_equipment: list[ParsedEquipment]) -> list[ParsedEquipment]:
    """Merge header-only/detail duplicate records before persisting reviewed equipment."""
    consolidated: list[ParsedEquipment] = []
    for item in parsed_equipment:
        match = next((existing for existing in consolidated if _should_merge_parsed(existing, item)), None)
        if match is None:
            consolidated.append(item)
        else:
            _merge_parsed_equipment(match, item)
    for index, item in enumerate(consolidated):
        item.source_order = index
    return consolidated


def _should_merge_parsed(left: ParsedEquipment, right: ParsedEquipment) -> bool:
    if left.equipment_type != right.equipment_type:
        return False
    left_zone = canonical_text(left.zone or "")
    right_zone = canonical_text(right.zone or "")
    left_capacity = canonical_text(left.capacity or "")
    right_capacity = canonical_text(right.capacity or "")
    if left.serial and right.serial:
        return canonical_text(left.serial) == canonical_text(right.serial) and (left_zone == right_zone or not left_zone or not right_zone)
    same_position = left_zone and left_zone == right_zone and left_capacity and left_capacity == right_capacity
    one_is_header_only = not left.serial or not right.serial or not left.brand or not right.brand
    return bool(same_position and one_is_header_only)


def _merge_parsed_equipment(target: ParsedEquipment, source: ParsedEquipment) -> None:
    for field_name in ["lot_number", "zone", "brand", "capacity", "serial"]:
        if not getattr(target, field_name) and getattr(source, field_name):
            setattr(target, field_name, getattr(source, field_name))
    target.source_text = f"{target.source_text}\n\n{source.source_text}".strip()
    target.confidence = max(target.confidence, source.confidence)
    if len(source.work_items) > len(target.work_items):
        target.work_items = source.work_items
    elif source.work_items:
        existing = {work.source_text for work in target.work_items}
        target.work_items.extend(work for work in source.work_items if work.source_text not in existing)


def _persist_equipment(project: Project, lot_map: dict[str, object], parsed_equipment: list[ParsedEquipment]) -> None:
    for index, item in enumerate(parsed_equipment, start=1):
        lot = lot_map.get(canonical_text(item.lot_number or "")) if item.lot_number else None
        equipment = Equipment(
            project_id=project.id,
            lot=lot,
            source_document_id=item.source_document_id,
            sequence=index,
            equipment_type=item.equipment_type,
            zone=item.zone,
            brand=item.brand,
            capacity=item.capacity,
            serial=item.serial,
            notes=item.source_text,
            extraction_confidence=item.confidence,
        )
        for work_index, work in enumerate(item.work_items, start=1):
            equipment.work_items.append(
                EquipmentWorkItem(
                    sequence=work_index,
                    title=work.title,
                    description=work.description,
                    source_text=work.source_text,
                    is_custom=work.is_custom,
                )
            )
        project.equipment.append(equipment)


def _create_equipment_issues(project: Project) -> None:
    if not project.equipment:
        project.extraction_issues.append(
            ExtractionIssue(
                project_id=project.id,
                severity="ERROR",
                entity_type="Project",
                field_name="equipment",
                message="No se detectaron equipos en los documentos cargados.",
            )
        )
        return

    for equipment in project.equipment:
        required_fields = ["equipment_type", "zone", "brand", "serial"]
        if equipment.equipment_type != "COLD_ROOM":
            required_fields.append("capacity")
        for field_name in required_fields:
            value = getattr(equipment, field_name)
            if not value or value == "UNKNOWN":
                project.extraction_issues.append(
                    ExtractionIssue(
                        project_id=project.id,
                        source_document_id=equipment.source_document_id,
                        entity_type="Equipment",
                        entity_id=equipment.id,
                        severity="WARNING" if field_name != "equipment_type" else "ERROR",
                        field_name=field_name,
                        message=f"El equipo {equipment.sequence} requiere revisar {field_name}.",
                    )
                )

    duplicate_keys = [_dedupe_key(equipment) for equipment in project.equipment]
    counts = Counter(key for key in duplicate_keys if key)
    for equipment, key in zip(project.equipment, duplicate_keys, strict=True):
        if key and counts[key] > 1:
            project.extraction_issues.append(
                ExtractionIssue(
                    project_id=project.id,
                    source_document_id=equipment.source_document_id,
                    entity_type="Equipment",
                    entity_id=equipment.id,
                    severity="WARNING",
                    field_name="duplicate",
                    message="Possible duplicate equipment",
                    detected_value=key,
                )
            )


def _dedupe_key(equipment: Equipment) -> str | None:
    if equipment.serial:
        return f"{canonical_text(equipment.equipment_type)}|SERIAL|{canonical_text(equipment.serial)}"
    parts = [equipment.equipment_type, equipment.zone, equipment.brand, equipment.capacity]
    if all(parts):
        return "|".join(canonical_text(part or "") for part in parts)
    return None
