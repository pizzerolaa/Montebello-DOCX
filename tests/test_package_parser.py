from __future__ import annotations

from app.services.docx_reader import DocumentBlock
from app.services.package_parser import build_package_work_items
from app.services.merge_service import consolidate_parsed_equipment, extract_declared_counts
from app.services.work_report_parser import extract_equipment


def _blocks(*texts: str) -> list[DocumentBlock]:
    return [DocumentBlock("paragraph", text, index, "package.docx") for index, text in enumerate(texts)]


def test_package_bullet_parsing_from_component_lines() -> None:
    items = build_package_work_items(
        "PIEZAS SUSTITUIDAS Y CORRECCIONES REALIZADAS\n"
        "BANDA DE TRANSMISION\n"
        "SUSTITUIDA DEBIDO AL DESGASTE FISICO.\n"
        "- FILTROS: SUSTITUIDOS POR SATURACION."
    )
    assert len(items) == 2
    assert items[0].title == "BANDA DE TRANSMISION"
    assert items[1].title == "FILTROS"


def test_extracts_package_equipment_block() -> None:
    equipment = extract_equipment(
        _blocks(
            "REPORTE DE TRABAJO",
            "LOTE: 02",
            "TIPO DE UNIDAD: TIPO PAQUETE",
            "ZONA DE EQUIPO 02",
            "MARCA: TRANE",
            "CAPACIDAD: 20 TON.",
            "SERIE: PK999",
            "PIEZAS SUSTITUIDAS Y CORRECCIONES REALIZADAS",
            "BANDA DE TRANSMISION: SUSTITUIDA POR DESGASTE.",
        ),
        "doc-id",
    )
    assert len(equipment) == 1
    assert equipment[0].equipment_type == "PACKAGE"
    assert equipment[0].zone == "EQUIPO 02"
    assert equipment[0].capacity == "20 TON"
    assert equipment[0].work_items[0].title == "BANDA DE TRANSMISION"


def test_extracts_package_from_realistic_header_without_zone_colon() -> None:
    equipment = extract_equipment(
        _blocks(
            "REPORTE DE TRABAJO",
            "NOMBRE DEL CLIENTE: LA SECRETARIA DE SALUD. PEDIDO: OTRF-010-25. LOTE: 3.",
            "DIRECCION: CENTRO DE SALUD CON HOSPITALIZACION NUEVA CONCORDIA.",
            "FECHA: 19 DE DICIEMBRE DE 2025.",
            "TIPO DE UNIDAD: TIPO PAQUETE",
            "CAPACIDAD: DE 20 TON. REFRIGERACION, MCA. YORK, CARRIER O LG, CONSISTENTE EN REPARACION.",
            "ZONA DE EQUIPO 01",
            "MARCA: YORK",
            "SERIE: PK001",
        ),
        "doc-id",
    )
    assert len(equipment) == 1
    assert equipment[0].equipment_type == "PACKAGE"
    assert equipment[0].lot_number == "3"
    assert equipment[0].zone == "EQUIPO 01"
    assert equipment[0].capacity == "20 TON"


def test_package_header_and_detail_rows_consolidate_to_one_equipment() -> None:
    header = extract_equipment(
        _blocks(
            "REPORTE DE TRABAJO",
            "TIPO DE UNIDAD: TIPO PAQUETE",
            "CAPACIDAD: 20 TON.",
            "ZONA DE EQUIPO 03.",
        ),
        "doc-id",
    )
    detail = extract_equipment(
        _blocks(
            "SE PRESENTA PERSONAL EN LA ZONA DE EQUIPO 03 DE TIPO PAQUETE.",
            "MARCA: CARRIER",
            "CAPACIDAD: 20 TON.",
            "SERIE: 1121P13091.",
        ),
        "doc-id",
    )
    equipment = consolidate_parsed_equipment([*header, *detail])
    assert len(equipment) == 1
    assert equipment[0].equipment_type == "PACKAGE"
    assert equipment[0].zone == "EQUIPO 03"
    assert equipment[0].brand == "CARRIER"
    assert equipment[0].serial == "1121P13091"


def test_package_numbered_activity_zone_merges_with_heading() -> None:
    header = extract_equipment(
        _blocks(
            "REPORTE DE TRABAJO",
            "TIPO DE UNIDAD: TIPO PAQUETE",
            "CAPACIDAD: 20 TON.",
            "ZONA DE EQUIPO 01",
        ),
        "doc-id",
    )
    detail = extract_equipment(
        _blocks(
            "SE PRESENTA PERSONAL EN LA ZONA DE EQUIPO 01 DE 1 EQUIPO TIPO PAQUETE.",
            "MARCA: CARRIER",
            "CAPACIDAD: 20 TON.",
            "SERIE: S/N",
        ),
        "doc-id",
    )

    equipment = consolidate_parsed_equipment([*header, *detail])

    assert len(equipment) == 1
    assert equipment[0].zone == "EQUIPO 01"
    assert equipment[0].brand == "CARRIER"
    assert equipment[0].serial == "S/N"


def test_serial_placeholder_s_s_normalizes_to_s_n() -> None:
    equipment = extract_equipment(
        _blocks(
            "REPORTE DE TRABAJO",
            "TIPO DE UNIDAD: TIPO MINISPLIT",
            "ZONA: CONSULTORIO",
            "MARCA: CARRIER",
            "CAPACIDAD: 1 TON",
            "SERIE: S/S.",
        ),
        "doc-id",
    )
    assert equipment[0].serial == "S/N"


def test_declared_counts_ignore_per_equipment_work_report_counts() -> None:
    blocks = _blocks(
        "MANTENIMIENTO CORRECTIVO (20 EQUIPOS TIPO MINISPLIT Y 02 TIPO PAQUETE), QUE INCLUYE:",
        "REPORTE DE TRABAJO",
        "SE PRESENTA PERSONAL EN LA ZONA A 1 EQUIPO MINISPLIT",
    )
    assert extract_declared_counts(blocks) == {"MINISPLIT": {20}, "PACKAGE": {2}, "COLD_ROOM": set()}
