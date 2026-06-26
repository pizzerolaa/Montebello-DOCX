from __future__ import annotations

import re
from collections import defaultdict

from app.models.extraction_issue import ExtractionIssue
from app.models.lot import Lot
from app.models.project import Project
from app.services.docx_reader import DocumentBlock, canonical_text, clean_label_value, normalize_spaces
from app.services.extraction_models import FieldCandidate


LOCATION_DATE_RE = re.compile(r"(?P<location>.+?),\s*(?P<state>CHIAPAS)\s+A\s+(?P<date>.+)", re.IGNORECASE)
ORDER_RE = re.compile(r"(?:PEDIDO|CONTRATO)\s*:?\s*(?P<order>[A-Z0-9-]+)", re.IGNORECASE)
LOT_RE = re.compile(r"\bLOTE\s*:?\s*(?P<lot>[A-Z0-9.-]+)", re.IGNORECASE)
CONTRACT_DATE_RE = re.compile(r"DE\s+FECHA\s+(?P<date>.+?),\s+CELEBRADO", re.IGNORECASE)
CLIENT_RE = re.compile(r"NOMBRE\s+DEL\s+CLIENTE\s*:?\s*(?P<client>.+)", re.IGNORECASE)


def _candidate(field_name: str, value: str, source_document_id: str, confidence: float, order: int) -> FieldCandidate | None:
    cleaned = clean_label_value(value)
    if not cleaned:
        return None
    return FieldCandidate(field_name, cleaned, source_document_id, confidence, order)


def parse_general_candidates(blocks: list[DocumentBlock], source_document_id: str) -> tuple[list[FieldCandidate], list[str]]:
    """Extract general metadata candidates and lot numbers from ordered blocks."""
    candidates: list[FieldCandidate] = []
    lots: list[str] = []
    canonical_blocks = [canonical_text(block.text) for block in blocks]

    for block in blocks:
        text = normalize_spaces(block.text)
        location_match = LOCATION_DATE_RE.search(text)
        if location_match:
            for field_name, value in (
                ("location", location_match.group("location")),
                ("state", location_match.group("state")),
                ("service_date_raw", location_match.group("date")),
            ):
                item = _candidate(field_name, value, source_document_id, 0.9, block.order)
                if item:
                    candidates.append(item)

        order_match = ORDER_RE.search(text)
        if order_match:
            item = _candidate("order_number", order_match.group("order"), source_document_id, 0.85, block.order)
            if item:
                candidates.append(item)

        lot_match = LOT_RE.search(text)
        if lot_match:
            lot = clean_label_value(lot_match.group("lot"))
            if lot and lot not in lots:
                lots.append(lot)
                candidates.append(FieldCandidate("lot_number", lot, source_document_id, 0.8, block.order))

        contract_match = CONTRACT_DATE_RE.search(text)
        if contract_match:
            item = _candidate("contract_date_raw", contract_match.group("date"), source_document_id, 0.8, block.order)
            if item:
                candidates.append(item)

        client_match = CLIENT_RE.search(text)
        if client_match:
            item = _candidate("client_name", client_match.group("client"), source_document_id, 0.75, block.order)
            if item:
                candidates.append(item)

        if "ACTA DE ENTREGA RECEPCION" in canonical_text(text):
            next_text = _next_meaningful_text(blocks, block.order)
            item = _candidate("center_name", next_text or "", source_document_id, 0.6, block.order + 1)
            if item:
                candidates.append(item)

    if not any("ACTA DE ENTREGA RECEPCION" in item for item in canonical_blocks):
        center = _label_after(blocks, "NOMBRE DEL CLIENTE")
        item = _candidate("center_name", center or "", source_document_id, 0.55, 0)
        if item:
            candidates.append(item)

    return candidates, lots


def _next_meaningful_text(blocks: list[DocumentBlock], order: int) -> str | None:
    for block in blocks:
        if block.order > order and normalize_spaces(block.text):
            text = normalize_spaces(block.text)
            if len(text) > 3:
                return text
    return None


def _label_after(blocks: list[DocumentBlock], label: str) -> str | None:
    label_key = canonical_text(label)
    for index, block in enumerate(blocks):
        current = canonical_text(block.text)
        if label_key in current:
            value = block.text.split(":", 1)[1] if ":" in block.text else ""
            if clean_label_value(value):
                return value
            if index + 1 < len(blocks):
                return blocks[index + 1].text
    return None


def apply_general_candidates(project: Project, candidates: list[FieldCandidate]) -> list[ExtractionIssue]:
    """Merge general candidates into a project and return conflict/missing issues."""
    issues: list[ExtractionIssue] = []
    grouped: dict[str, list[FieldCandidate]] = defaultdict(list)
    for candidate in candidates:
        grouped[candidate.field_name].append(candidate)

    for field_name in [
        "location",
        "state",
        "service_date_raw",
        "contract_date_raw",
        "order_number",
        "center_name",
        "client_name",
    ]:
        values = grouped.get(field_name, [])
        if not values:
            issues.append(
                ExtractionIssue(
                    project_id=project.id,
                    severity="WARNING",
                    entity_type="Project",
                    field_name=field_name,
                    message=f"No se detecto el campo {field_name}.",
                )
            )
            continue
        selected, conflict = _select_candidate(values)
        setattr(project, field_name, selected.value)
        if conflict:
            issues.append(
                ExtractionIssue(
                    project_id=project.id,
                    source_document_id=selected.source_document_id,
                    severity="WARNING",
                    entity_type="Project",
                    field_name=field_name,
                    message=f"Valores conflictivos detectados para {field_name}.",
                    detected_value=" | ".join(sorted({candidate.value for candidate in values})),
                    resolved_value=selected.value,
                )
            )

    project.service_date = None
    project.contract_date = None
    return issues


def _select_candidate(candidates: list[FieldCandidate]) -> tuple[FieldCandidate, bool]:
    buckets: dict[str, list[FieldCandidate]] = defaultdict(list)
    for candidate in candidates:
        buckets[canonical_text(candidate.value)].append(candidate)
    selected_bucket = max(buckets.values(), key=lambda bucket: (len(bucket), max(item.confidence for item in bucket)))
    selected = sorted(selected_bucket, key=lambda item: (-item.confidence, item.source_order))[0]
    return selected, len(buckets) > 1


def sync_lots(project: Project, lot_numbers: list[str]) -> dict[str, Lot]:
    """Ensure detected lots exist and return them by normalized lot number."""
    existing = {canonical_text(lot.lot_number): lot for lot in project.lots}
    for lot_number in lot_numbers:
        key = canonical_text(lot_number)
        if key not in existing:
            lot = Lot(project_id=project.id, lot_number=lot_number)
            project.lots.append(lot)
            existing[key] = lot
    return existing
