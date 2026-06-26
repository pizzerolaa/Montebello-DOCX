from __future__ import annotations

from datetime import UTC, datetime


def utc_now() -> datetime:
    """Return an aware UTC timestamp for ORM defaults."""
    return datetime.now(UTC)

