"""Money and currency utilities."""

import re
from decimal import Decimal, InvalidOperation
from typing import Any


def parse_amount(
    value: Any,
    decimal_separator: str = ".",
    thousands_separator: str = ",",
) -> Decimal | None:
    """Parse an amount from various formats.

    Args:
        value: The value to parse
        decimal_separator: Character used for decimal point
        thousands_separator: Character used for thousands grouping

    Returns:
        Parsed Decimal or None if parsing fails
    """
    if value is None:
        return None

    if isinstance(value, Decimal):
        return value

    if isinstance(value, (int, float)):
        return Decimal(str(value))

    if isinstance(value, str):
        value = value.strip()
        if not value:
            return None

        # Remove currency symbols and whitespace
        value = re.sub(r"[^\d.,\-+]", "", value)

        # Handle negative amounts in parentheses: (100.00) -> -100.00
        if value.startswith("(") and value.endswith(")"):
            value = "-" + value[1:-1]

        # Normalize separators
        if decimal_separator != ".":
            # Replace thousands separator with nothing
            value = value.replace(thousands_separator, "")
            # Replace decimal separator with standard decimal point
            value = value.replace(decimal_separator, ".")
        else:
            # Remove thousands separator
            value = value.replace(thousands_separator, "")

        try:
            return Decimal(value)
        except InvalidOperation:
            return None

    return None


def normalize_currency_code(value: Any) -> str | None:
    """Normalize a currency code to ISO 4217 format.

    Args:
        value: The currency code to normalize

    Returns:
        Uppercase 3-letter currency code or None
    """
    if value is None:
        return None

    if isinstance(value, str):
        value = value.strip().upper()
        # Validate it's a 3-letter code
        if len(value) == 3 and value.isalpha():
            return value

    return None


def amount_difference(
    amount1: Decimal | None,
    amount2: Decimal | None,
) -> Decimal | None:
    """Calculate the absolute difference between two amounts.

    Returns None if either amount is None.
    """
    if amount1 is None or amount2 is None:
        return None
    return abs(amount1 - amount2)


def amount_difference_percent(
    amount1: Decimal | None,
    amount2: Decimal | None,
) -> float | None:
    """Calculate the percentage difference between two amounts.

    Returns the difference as a fraction of the larger amount.
    Returns None if either amount is None.
    """
    if amount1 is None or amount2 is None:
        return None

    diff = abs(amount1 - amount2)
    max_amount = max(abs(amount1), abs(amount2))

    if max_amount == 0:
        return 0.0 if diff == 0 else None

    return float(diff / max_amount)


def is_within_tolerance(
    amount1: Decimal | None,
    amount2: Decimal | None,
    tolerance_percent: float,
) -> bool:
    """Check if two amounts are within a percentage tolerance.

    Returns True if either amount is None (no amount to compare).
    """
    pct_diff = amount_difference_percent(amount1, amount2)
    if pct_diff is None:
        return True
    return pct_diff <= tolerance_percent


def format_amount(
    value: Decimal | None,
    currency: str | None = None,
    decimal_places: int = 2,
) -> str:
    """Format an amount for display.

    Args:
        value: The amount to format
        currency: Optional currency code
        decimal_places: Number of decimal places

    Returns:
        Formatted amount string
    """
    if value is None:
        return ""

    formatted = f"{value:,.{decimal_places}f}"

    if currency:
        return f"{currency} {formatted}"

    return formatted
