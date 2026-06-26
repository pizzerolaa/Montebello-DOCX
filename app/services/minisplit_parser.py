from __future__ import annotations

from app.services.docx_reader import normalize_spaces
from app.services.extraction_models import ParsedWorkItem


def build_minisplit_work_items(source_text: str) -> list[ParsedWorkItem]:
    """Preserve minisplit corrective or activity text as custom work items for review."""
    text = normalize_spaces(source_text)
    if not text:
        return []
    return [ParsedWorkItem(title="Trabajo correctivo", description=text, source_text=source_text, is_custom=True)]
