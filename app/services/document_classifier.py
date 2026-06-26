from __future__ import annotations

from app.models.enums import DetectedProfile
from app.services.docx_reader import DocumentBlock, canonical_text


PROFILE_WEIGHTS = {
    DetectedProfile.ACTA.value: {
        "ACTA DE ENTREGA RECEPCION": 4,
        "DESGLOSE DE LOS MANTENIMIENTOS": 3,
        "SIN OTRO PARTICULAR": 2,
    },
    DetectedProfile.WORK_REPORT.value: {
        "REPORTE DE TRABAJO": 4,
        "NOMBRE DEL CLIENTE": 2,
        "TIPO DE UNIDAD": 3,
        "ACTIVIDADES REALIZADAS": 2,
    },
    DetectedProfile.ANNEX.value: {
        "ANEXO DEL REPORTE DE TRABAJO": 4,
        "DETALLE TECNICO DE LOS TRABAJOS": 3,
        "ATENTAMENTE": 1,
    },
}


def classify_document(blocks: list[DocumentBlock]) -> str:
    """Classify a source document using deterministic weighted phrase detection."""
    text = "\n".join(canonical_text(block.text) for block in blocks)
    scores: dict[str, int] = {}
    for profile, indicators in PROFILE_WEIGHTS.items():
        scores[profile] = sum(weight for phrase, weight in indicators.items() if phrase in text)

    has_acta = scores[DetectedProfile.ACTA.value] >= 4
    has_work = scores[DetectedProfile.WORK_REPORT.value] >= 4
    has_annex = scores[DetectedProfile.ANNEX.value] >= 4
    if sum([has_acta, has_work, has_annex]) >= 2:
        return DetectedProfile.MIXED.value
    best_profile, best_score = max(scores.items(), key=lambda item: item[1])
    return best_profile if best_score > 0 else DetectedProfile.UNKNOWN.value
