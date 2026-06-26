from __future__ import annotations

from app.services.docx_reader import DocumentBlock
from app.services.work_report_parser import extract_equipment, normalize_capacity, normalize_equipment_type


def _blocks(*texts: str) -> list[DocumentBlock]:
    return [DocumentBlock("paragraph", text, index, "mini.docx") for index, text in enumerate(texts)]


def test_normalize_equipment_type_minisplit_package_unknown() -> None:
    assert normalize_equipment_type("TIPO MINISPLIT") == "MINISPLIT"
    assert normalize_equipment_type("tipo paquete") == "PACKAGE"
    assert normalize_equipment_type("evaporador") == "UNKNOWN"


def test_normalize_capacity_compacts_tonnage() -> None:
    assert normalize_capacity("DE 20 TON. REFRIGERACION, MCA. YORK") == "20 TON"
    assert normalize_capacity("1 TONELADA") == "1 TON"
    assert normalize_capacity("01 TONELADAS") == "1 TON"


def test_extracts_minisplit_equipment_block() -> None:
    equipment = extract_equipment(
        _blocks(
            "REPORTE DE TRABAJO",
            "LOTE: 01",
            "TIPO DE UNIDAD: MINISPLIT",
            "ZONA: CONSULTORIO 1",
            "MARCA: YORK",
            "CAPACIDAD: 1 TON",
            "SERIE: MS123",
            "ACTIVIDADES REALIZADAS",
            "Cambio de capacitor.",
        ),
        "doc-id",
    )
    assert len(equipment) == 1
    assert equipment[0].equipment_type == "MINISPLIT"
    assert equipment[0].zone == "CONSULTORIO 1"
    assert equipment[0].serial == "MS123"
    assert equipment[0].work_items[0].description == "Cambio de capacitor."
