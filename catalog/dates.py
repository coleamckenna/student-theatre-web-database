"""Date parsing and ISO 8601 (YYYY-MM-DD) normalization."""

from __future__ import annotations

import re
from datetime import datetime, timedelta

_INPUT_FORMATS = (
    "%Y-%m-%d",
    "%d-%m-%Y",
    "%d/%m/%Y",
    "%d/%m/%y",
    "%m/%d/%Y",
)


def to_iso_date(value) -> str | None:
    """Convert Excel serial, datetime, or string to ISO 8601 date (YYYY-MM-DD)."""
    if value is None or value == "":
        return None

    if isinstance(value, datetime):
        return value.strftime("%Y-%m-%d")

    if isinstance(value, (int, float)):
        base = datetime(1899, 12, 30)
        try:
            dt = base + timedelta(days=float(value))
            return dt.strftime("%Y-%m-%d")
        except (OverflowError, ValueError):
            return None

    text = str(value).strip()
    if not text:
        return None

    if re.fullmatch(r"\d{4}-\d{2}-\d{2}", text):
        return text

    for fmt in _INPUT_FORMATS:
        try:
            return datetime.strptime(text, fmt).strftime("%Y-%m-%d")
        except ValueError:
            continue

    if re.fullmatch(r"\d+\.?\d*", text):
        return to_iso_date(float(text))

    return text
