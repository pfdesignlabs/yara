"""Shared helpers for tool wrappers."""

from datetime import datetime


def parse_iso(value: str) -> datetime:
    """Parse an ISO 8601 datetime string into a `datetime`.

    Accepts both bare dates ("2026-06-15") and full timestamps
    ("2026-06-15T14:00:00Z"). The trailing "Z" is normalised to
    "+00:00" because `datetime.fromisoformat` only learned to handle
    "Z" in Python 3.11.
    """
    return datetime.fromisoformat(value.replace("Z", "+00:00"))
