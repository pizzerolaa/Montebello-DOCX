from __future__ import annotations

from app.services.docx_reader import DocumentBlock
from app.services.general_parser import parse_general_candidates


def _blocks(*texts: str) -> list[DocumentBlock]:
    return [DocumentBlock("paragraph", text, index, "general.docx") for index, text in enumerate(texts)]


def test_extracts_location_order_lot_contract_client_and_center() -> None:
    candidates, lots = parse_general_candidates(
        _blocks(
            "TAPACHULA, CHIAPAS A 10 DE JUNIO DE 2026",
            "ACTA DE ENTREGA RECEPCION DEL PEDIDO",
            "HOSPITAL GENERAL",
            "PEDIDO: ABC-123",
            "LOTE: 02",
            "DE FECHA 01 DE JUNIO DE 2026, CELEBRADO",
            "NOMBRE DEL CLIENTE: IMSS",
        ),
        "doc-id",
    )
    values = {(candidate.field_name, candidate.value) for candidate in candidates}
    assert ("location", "TAPACHULA") in values
    assert ("service_date_raw", "10 DE JUNIO DE 2026") in values
    assert ("order_number", "ABC-123") in values
    assert ("lot_number", "02") in values
    assert ("contract_date_raw", "01 DE JUNIO DE 2026") in values
    assert ("client_name", "IMSS") in values
    assert lots == ["02"]

