"""Normalization service for converting raw records to canonical format."""

from datetime import date, datetime
from decimal import Decimal
from typing import Any

from app.utils.dates import parse_date, normalize_date_to_iso
from app.utils.money import parse_amount, normalize_currency_code


class NormalizationService:
    """Service for normalizing raw record data to canonical format."""

    def __init__(
        self,
        field_mappings: dict[str, str],
        date_format: str | None = None,
        decimal_separator: str = ".",
        thousands_separator: str = ",",
    ):
        """Initialize normalizer with field mappings.

        Args:
            field_mappings: Map from source column names to canonical field names
            date_format: Expected date format string
            decimal_separator: Character used for decimal point
            thousands_separator: Character used for thousands grouping
        """
        self.field_mappings = field_mappings
        self.date_format = date_format
        self.decimal_separator = decimal_separator
        self.thousands_separator = thousands_separator
        self.reverse_mappings = {v: k for k, v in field_mappings.items()}

    def normalize_record(self, raw_data: dict[str, Any]) -> dict[str, Any]:
        """Normalize a raw record to canonical format.

        Args:
            raw_data: Raw record with source column names

        Returns:
            Normalized record with canonical field names and standardized values
        """
        # First, map fields to canonical names
        mapped = self._map_fields(raw_data)

        # Then normalize each field type
        normalized = {}

        # String fields - trim whitespace, normalize to uppercase for IDs
        for field in ["external_record_id", "reference_code"]:
            if field in mapped and mapped[field]:
                normalized[field] = self._normalize_identifier(mapped[field])

        # String fields - preserve case
        for field in ["description", "counterparty"]:
            if field in mapped and mapped[field]:
                normalized[field] = str(mapped[field]).strip()

        # ID fields
        for field in ["account_id", "entity_id"]:
            if field in mapped and mapped[field]:
                normalized[field] = str(mapped[field]).strip()

        # Date fields
        for field in ["record_date", "settlement_date"]:
            if field in mapped and mapped[field]:
                parsed = parse_date(mapped[field], self.date_format)
                if parsed:
                    normalized[field] = parsed

        # Amount field
        if "amount" in mapped and mapped["amount"] is not None:
            parsed = parse_amount(
                mapped["amount"],
                decimal_separator=self.decimal_separator,
                thousands_separator=self.thousands_separator,
            )
            if parsed is not None:
                normalized["amount"] = parsed

        # Currency field
        if "currency" in mapped:
            currency = normalize_currency_code(mapped["currency"])
            normalized["currency"] = currency or "USD"
        else:
            normalized["currency"] = "USD"

        return normalized

    def _map_fields(self, raw_data: dict[str, Any]) -> dict[str, Any]:
        """Map source column names to canonical field names."""
        mapped = {}
        for source_col, canonical_field in self.field_mappings.items():
            if source_col in raw_data:
                mapped[canonical_field] = raw_data[source_col]
        return mapped

    def _normalize_identifier(self, value: Any) -> str:
        """Normalize an identifier value.

        - Strip whitespace
        - Convert to uppercase
        - Remove special characters except hyphen and underscore
        """
        s = str(value).strip().upper()
        # Keep alphanumeric, hyphen, underscore
        return "".join(c for c in s if c.isalnum() or c in "-_")


def compute_record_hash(normalized_data: dict[str, Any]) -> str:
    """Compute a stable hash for a normalized record.

    Uses key fields to create a deterministic hash for deduplication.
    """
    import hashlib

    # Key fields for hashing
    key_fields = [
        "external_record_id",
        "record_date",
        "amount",
        "currency",
        "account_id",
    ]

    hash_parts = []
    for field in key_fields:
        value = normalized_data.get(field)
        if value is not None:
            if isinstance(value, date):
                hash_parts.append(value.isoformat())
            elif isinstance(value, Decimal):
                hash_parts.append(str(value))
            else:
                hash_parts.append(str(value))
        else:
            hash_parts.append("")

    hash_str = "|".join(hash_parts)
    return hashlib.sha256(hash_str.encode()).hexdigest()
