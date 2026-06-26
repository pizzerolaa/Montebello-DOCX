from __future__ import annotations

import re

from app.services.docx_reader import canonical_text, clean_label_value, normalize_spaces
from app.services.extraction_models import ParsedWorkItem


BULLET_RE = re.compile(r"^\s*(?:[•\-*]|\d+[.)])\s*(?P<text>.+)$")
COMPONENT_RE = re.compile(r"^\s*(?P<title>[A-ZÁÉÍÓÚÜÑ0-9 /\-]{4,})\s*:\s*(?P<description>.+)$")


def build_package_work_items(source_text: str) -> list[ParsedWorkItem]:
    """Split package corrective work text into list-style work items when possible."""
    raw_lines = [line.strip() for line in source_text.splitlines() if normalize_spaces(line)]
    items: list[ParsedWorkItem] = []
    pending_title: str | None = None

    for line in raw_lines:
        key = canonical_text(line)
        if any(stop in key for stop in ["PIEZAS SUSTITUIDAS", "CORRECCIONES REALIZADAS"]):
            continue
        bullet = BULLET_RE.match(line)
        component = COMPONENT_RE.match(line)
        if bullet:
            text = clean_label_value(bullet.group("text"))
            title, description = _split_component_sentence(text)
            items.append(ParsedWorkItem(title=title, description=description, source_text=line, is_custom=True))
            pending_title = None
            continue
        if component:
            items.append(
                ParsedWorkItem(
                    title=clean_label_value(component.group("title")),
                    description=clean_label_value(component.group("description")),
                    source_text=line,
                    is_custom=True,
                )
            )
            pending_title = None
            continue
        if _looks_like_component(line):
            pending_title = clean_label_value(line)
            continue
        if pending_title:
            items.append(
                ParsedWorkItem(
                    title=pending_title,
                    description=clean_label_value(line),
                    source_text=f"{pending_title}\n{line}",
                    is_custom=True,
                )
            )
            pending_title = None

    if items:
        return items
    fallback = normalize_spaces(source_text)
    if fallback:
        return [ParsedWorkItem(title="Trabajo correctivo", description=fallback, source_text=source_text, is_custom=True)]
    return []


def _looks_like_component(line: str) -> bool:
    key = canonical_text(line)
    letters = [char for char in key if char.isalpha()]
    return len(key) <= 80 and len(letters) >= 4 and key == key.upper() and not key.endswith(".")


def _split_component_sentence(text: str) -> tuple[str | None, str]:
    if ":" in text:
        title, description = text.split(":", 1)
        return clean_label_value(title), clean_label_value(description)
    return None, text
