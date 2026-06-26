from __future__ import annotations

from app.services.docx_reader import DocumentBlock
from app.services.merge_service import extract_declared_counts
from app.services.work_report_parser import extract_equipment, normalize_equipment_type


def _blocks(*texts: str) -> list[DocumentBlock]:
    return [DocumentBlock("paragraph", text, index, "cold-room.docx") for index, text in enumerate(texts)]


def test_normalize_equipment_type_cold_room_variants() -> None:
    assert normalize_equipment_type("CAMARA FRIA 01") == "COLD_ROOM"
    assert normalize_equipment_type("CAMARA DE REFRIGERACION 02") == "COLD_ROOM"
    assert normalize_equipment_type("CAMARA DE REFRIGERACION (PRECAMARA)") == "COLD_ROOM"


def test_extracts_cold_room_using_unit_type_as_zone_when_zone_is_missing() -> None:
    equipment = extract_equipment(
        _blocks(
            "REPORTE DE TRABAJO",
            "TIPO DE UNIDAD: CAMARA DE REFRIGERACION (PRECAMARA).",
            "MARCA: BOHN",
            "SERIE: M21K00323",
            "SE PROCEDE A REALIZAR EL MANTENIMIENTO A LA PRECAMARA.",
        ),
        "doc-id",
    )

    assert len(equipment) == 1
    assert equipment[0].equipment_type == "COLD_ROOM"
    assert equipment[0].zone == "CAMARA DE REFRIGERACION (PRECAMARA)"
    assert equipment[0].brand == "BOHN"
    assert equipment[0].serial == "M21K00323"


def test_declared_counts_include_cold_rooms_in_mixed_summary() -> None:
    blocks = _blocks(
        "MANTENIMIENTO CORRECTIVO (10 EQUIPOS TIPO MINISPLIT, 02 TIPO PAQUETE Y 02 CAMARAS FRIAS), QUE INCLUYE:",
        "REPORTE DE TRABAJO",
        "TIPO DE UNIDAD: CAMARA FRIA 01.",
    )

    assert extract_declared_counts(blocks) == {
        "MINISPLIT": {10},
        "PACKAGE": {2},
        "COLD_ROOM": {2},
    }
