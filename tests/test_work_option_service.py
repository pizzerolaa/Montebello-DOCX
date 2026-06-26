from __future__ import annotations

from app.models.equipment import Equipment
from app.services.work_option_service import (
    _load_package_groups,
    cold_room_work_for_equipment,
    minisplit_work_for_equipment,
    package_work_for_equipment,
)


def test_minisplit_work_options_select_stable_phrase() -> None:
    equipment = Equipment(id="eq-1", sequence=1, equipment_type="MINISPLIT", zone="A", serial="S1")
    first = minisplit_work_for_equipment(equipment)
    second = minisplit_work_for_equipment(equipment)
    assert first
    assert first == second


def test_package_options_keep_txv_and_filter_group_together() -> None:
    groups = _load_package_groups()
    linked = [
        group
        for group in groups
        if any("TXV" in item for item in group) and any("FILTRO DESHIDRATADOR" in item for item in group)
    ]
    assert linked
    assert len(linked[0]) == 2


def test_cold_room_work_options_select_three_stable_pieces() -> None:
    equipment = Equipment(id="eq-3", sequence=3, equipment_type="COLD_ROOM", zone="CAMARA FRIA 01", serial="CF1")
    first = cold_room_work_for_equipment(equipment)
    second = cold_room_work_for_equipment(equipment)
    assert len(first) == 3
    assert first == second
    assert all(":" in item for item in first)


def test_package_work_options_return_bullet_text_without_marker() -> None:
    equipment = Equipment(id="eq-2", sequence=2, equipment_type="PACKAGE", zone="EQUIPO 01", serial="P1")
    items = package_work_for_equipment(equipment, group_count=3)
    assert items
    assert all(not item.startswith(("•", "â€¢")) for item in items)
