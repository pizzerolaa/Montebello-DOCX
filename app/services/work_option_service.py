from __future__ import annotations

import hashlib
import random
import re
from functools import lru_cache
from pathlib import Path

from app.models.equipment import Equipment


CONTENT_ROOT = Path(__file__).resolve().parents[1] / "document_content"
BULLET_RE = re.compile(r"^\s*(?:[•\-\*]+|â€¢)\s*(?P<text>.+)$")


def minisplit_work_for_equipment(equipment: Equipment) -> str | None:
    """Select one stable random minisplit corrective-work phrase."""
    options = _load_minisplit_options()
    if not options:
        return None
    return _stable_sample(options, equipment, 1)[0]


def package_work_for_equipment(equipment: Equipment, group_count: int = 6) -> list[str]:
    """Select stable random package bullet groups, preserving linked grouped items."""
    groups = _load_package_groups()
    if not groups:
        return []
    selected = _stable_sample(groups, equipment, min(group_count, len(groups)))
    flattened: list[str] = []
    for group in selected:
        flattened.extend(group)
    return flattened


def cold_room_work_for_equipment(equipment: Equipment, group_count: int = 3) -> list[str]:
    """Select stable random cold-room replacement pieces."""
    groups = _load_cold_room_groups()
    if not groups:
        return []
    selected = _stable_sample(groups, equipment, min(group_count, len(groups)))
    flattened: list[str] = []
    for group in selected:
        flattened.extend(group)
    return flattened


@lru_cache
def _load_minisplit_options() -> tuple[str, ...]:
    path = CONTENT_ROOT / "minisplit" / "work_options.txt"
    if not path.exists():
        return ()
    text = _read_text(path)
    return tuple(line.strip() for line in text.splitlines() if line.strip())


@lru_cache
def _load_package_groups() -> tuple[tuple[str, ...], ...]:
    path = CONTENT_ROOT / "package" / "work_options.txt"
    if not path.exists():
        return ()
    return _load_grouped_options(path)


@lru_cache
def _load_cold_room_groups() -> tuple[tuple[str, ...], ...]:
    path = CONTENT_ROOT / "cold_room" / "work_options.txt"
    if not path.exists():
        return ()
    return _load_grouped_options(path)


def _load_grouped_options(path: Path) -> tuple[tuple[str, ...], ...]:
    groups: list[tuple[str, ...]] = []
    grouped: list[str] = []
    in_group = False
    for raw_line in _read_text(path).splitlines():
        line = raw_line.strip()
        if not line:
            continue
        starts_group = "***" in line and not in_group
        ends_group = "***" in line and (in_group or line.count("***") >= 2)
        cleaned = _clean_package_line(line)
        if starts_group:
            in_group = True
            grouped = []
        if cleaned:
            if in_group:
                grouped.append(cleaned)
            else:
                groups.append((cleaned,))
        if ends_group and in_group:
            if grouped:
                groups.append(tuple(grouped))
            grouped = []
            in_group = False
    if grouped:
        groups.append(tuple(grouped))
    return tuple(groups)


def _stable_sample(options, equipment: Equipment, count: int):
    seed = _seed_for_equipment(equipment)
    rng = random.Random(seed)
    if count >= len(options):
        shuffled = list(options)
        rng.shuffle(shuffled)
        return shuffled
    return rng.sample(list(options), count)


def _seed_for_equipment(equipment: Equipment) -> int:
    key = "|".join(
        [
            equipment.id or "",
            str(equipment.sequence),
            equipment.equipment_type or "",
            equipment.zone or "",
            equipment.serial or "",
        ]
    )
    return int(hashlib.sha256(key.encode("utf-8")).hexdigest()[:16], 16)


def _clean_package_line(line: str) -> str:
    line = line.replace("***", "").strip()
    match = BULLET_RE.match(line)
    if match:
        line = match.group("text")
    return line.strip()


def _read_text(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        return path.read_text(encoding="latin-1")
