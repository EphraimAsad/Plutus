"""Date parsing and normalization utilities."""

from datetime import date, datetime
from typing import Any

import dateutil.parser


def parse_date(value: Any, format_str: str | None = None) -> date | None:
    """Parse a date from various formats.

    Args:
        value: The value to parse (string, date, datetime, or None)
        format_str: Optional explicit format string

    Returns:
        Parsed date or None if parsing fails
    """
    if value is None:
        return None

    if isinstance(value, date):
        return value

    if isinstance(value, datetime):
        return value.date()

    if isinstance(value, str):
        value = value.strip()
        if not value:
            return None

        try:
            if format_str:
                return datetime.strptime(value, format_str).date()
            else:
                # Use dateutil for flexible parsing
                return dateutil.parser.parse(value).date()
        except (ValueError, TypeError):
            return None

    return None


def normalize_date_to_iso(value: Any, format_str: str | None = None) -> str | None:
    """Normalize a date value to ISO format (YYYY-MM-DD).

    Args:
        value: The value to parse
        format_str: Optional explicit format string

    Returns:
        ISO formatted date string or None
    """
    parsed = parse_date(value, format_str)
    if parsed:
        return parsed.isoformat()
    return None


def date_difference_days(date1: date | None, date2: date | None) -> int | None:
    """Calculate the difference in days between two dates.

    Returns None if either date is None.
    """
    if date1 is None or date2 is None:
        return None
    return abs((date1 - date2).days)


def is_within_tolerance(
    date1: date | None,
    date2: date | None,
    tolerance_days: int,
) -> bool:
    """Check if two dates are within a tolerance.

    Returns True if either date is None (no date to compare).
    """
    diff = date_difference_days(date1, date2)
    if diff is None:
        return True
    return diff <= tolerance_days
