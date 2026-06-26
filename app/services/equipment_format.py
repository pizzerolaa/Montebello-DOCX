from __future__ import annotations


def normalize_serial(value: str | None) -> str:
    """Normalize serial placeholders and punctuation from source reports."""
    serial = (value or "").strip().rstrip(".")
    if serial.upper() == "S/S":
        return "S/N"
    return serial
