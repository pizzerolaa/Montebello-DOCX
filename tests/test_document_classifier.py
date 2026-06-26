from __future__ import annotations

from app.services.docx_reader import DocumentBlock
from app.services.document_classifier import classify_document


def _blocks(*texts: str) -> list[DocumentBlock]:
    return [DocumentBlock("paragraph", text, index, "test.docx") for index, text in enumerate(texts)]


def test_classifies_work_report_with_accents() -> None:
    profile = classify_document(_blocks("REPORTE DE TRABAJO", "TIPO DE UNIDAD", "ACTIVIDADES REALIZADAS"))
    assert profile == "WORK_REPORT"


def test_classifies_mixed_document() -> None:
    profile = classify_document(
        _blocks("ACTA DE ENTREGA RECEPCION", "DESGLOSE DE LOS MANTENIMIENTOS", "REPORTE DE TRABAJO")
    )
    assert profile == "MIXED"

