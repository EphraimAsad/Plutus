"""Validation service for raw records."""

from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal, InvalidOperation
from typing import Any

from app.utils.dates import parse_date
from app.utils.money import parse_amount, normalize_currency_code


@dataclass
class ValidationError:
    """A single validation error."""

    field: str
    code: str
    message: str

    def to_dict(self) -> dict:
        return {
            "field": self.field,
            "code": self.code,
            "message": self.message,
        }


@dataclass
class ValidationWarning:
    """A single validation warning."""

    field: str
    code: str
    message: str

    def to_dict(self) -> dict:
        return {
            "field": self.field,
            "code": self.code,
            "message": self.message,
        }


@dataclass
class ValidationResult:
    """Result of validating a single record."""

    is_valid: bool
    errors: list[ValidationError] = field(default_factory=list)
    warnings: list[ValidationWarning] = field(default_factory=list)
    normalized_data: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "is_valid": self.is_valid,
            "errors": [e.to_dict() for e in self.errors],
            "warnings": [w.to_dict() for w in self.warnings],
        }


class RecordValidator:
    """Validates and normalizes raw records according to schema mapping."""

    # Required canonical fields
    REQUIRED_FIELDS = ["external_record_id", "record_date", "amount"]

    # Optional canonical fields
    OPTIONAL_FIELDS = [
        "account_id",
        "entity_id",
        "settlement_date",
        "currency",
        "reference_code",
        "description",
        "counterparty",
    ]

    def __init__(
        self,
        field_mappings: dict[str, str],
        date_format: str | None = None,
        decimal_separator: str = ".",
        thousands_separator: str = ",",
    ):
        """Initialize validator with schema mapping.

        Args:
            field_mappings: Map from source column names to canonical field names
            date_format: Expected date format (e.g., "%Y-%m-%d")
            decimal_separator: Character used for decimal point
            thousands_separator: Character used for thousands grouping
        """
        self.field_mappings = field_mappings
        self.date_format = date_format
        self.decimal_separator = decimal_separator
        self.thousands_separator = thousands_separator

        # Reverse mapping: canonical field -> source column
        self.reverse_mappings = {v: k for k, v in field_mappings.items()}

    def validate_record(self, raw_data: dict[str, Any]) -> ValidationResult:
        """Validate and normalize a single raw record.

        Args:
            raw_data: Raw record data with source column names

        Returns:
            ValidationResult with errors, warnings, and normalized data
        """
        errors: list[ValidationError] = []
        warnings: list[ValidationWarning] = []
        normalized: dict[str, Any] = {}

        # Map source columns to canonical fields
        mapped_data = self._map_fields(raw_data)

        # Validate required fields
        for field in self.REQUIRED_FIELDS:
            value = mapped_data.get(field)
            if value is None or (isinstance(value, str) and not value.strip()):
                errors.append(
                    ValidationError(
                        field=field,
                        code="MISSING_REQUIRED_FIELD",
                        message=f"Required field '{field}' is missing or empty",
                    )
                )

        # Validate and normalize external_record_id
        if "external_record_id" in mapped_data:
            ext_id = mapped_data["external_record_id"]
            if ext_id:
                normalized["external_record_id"] = str(ext_id).strip()
            else:
                normalized["external_record_id"] = None

        # Validate and normalize dates
        for date_field in ["record_date", "settlement_date"]:
            if date_field in mapped_data:
                value = mapped_data[date_field]
                if value:
                    parsed = parse_date(value, self.date_format)
                    if parsed is None:
                        errors.append(
                            ValidationError(
                                field=date_field,
                                code="INVALID_DATE",
                                message=f"Cannot parse date value: {value}",
                            )
                        )
                    else:
                        normalized[date_field] = parsed

                        # Validate date is reasonable
                        if parsed.year < 2000:
                            warnings.append(
                                ValidationWarning(
                                    field=date_field,
                                    code="SUSPICIOUS_DATE",
                                    message=f"Date {parsed} is before year 2000",
                                )
                            )
                        elif parsed > date.today():
                            warnings.append(
                                ValidationWarning(
                                    field=date_field,
                                    code="FUTURE_DATE",
                                    message=f"Date {parsed} is in the future",
                                )
                            )
                else:
                    normalized[date_field] = None

        # Validate and normalize amount
        if "amount" in mapped_data:
            value = mapped_data["amount"]
            if value is not None:
                parsed = parse_amount(
                    value,
                    decimal_separator=self.decimal_separator,
                    thousands_separator=self.thousands_separator,
                )
                if parsed is None:
                    errors.append(
                        ValidationError(
                            field="amount",
                            code="INVALID_AMOUNT",
                            message=f"Cannot parse amount value: {value}",
                        )
                    )
                else:
                    normalized["amount"] = parsed

                    # Warn about unusual amounts
                    if abs(parsed) > Decimal("1000000"):
                        warnings.append(
                            ValidationWarning(
                                field="amount",
                                code="LARGE_AMOUNT",
                                message=f"Amount {parsed} is unusually large",
                            )
                        )
                    elif parsed == Decimal("0"):
                        warnings.append(
                            ValidationWarning(
                                field="amount",
                                code="ZERO_AMOUNT",
                                message="Amount is zero",
                            )
                        )

        # Validate and normalize currency
        if "currency" in mapped_data:
            value = mapped_data["currency"]
            if value:
                currency = normalize_currency_code(value)
                if currency is None:
                    warnings.append(
                        ValidationWarning(
                            field="currency",
                            code="INVALID_CURRENCY",
                            message=f"Invalid currency code: {value}",
                        )
                    )
                    normalized["currency"] = str(value).upper()[:3]
                else:
                    normalized["currency"] = currency
            else:
                normalized["currency"] = "USD"  # Default currency

        # Normalize string fields
        for field in ["account_id", "entity_id", "reference_code", "description", "counterparty"]:
            if field in mapped_data:
                value = mapped_data[field]
                if value is not None:
                    normalized[field] = str(value).strip()
                else:
                    normalized[field] = None

        is_valid = len(errors) == 0

        return ValidationResult(
            is_valid=is_valid,
            errors=errors,
            warnings=warnings,
            normalized_data=normalized,
        )

    def _map_fields(self, raw_data: dict[str, Any]) -> dict[str, Any]:
        """Map source column names to canonical field names.

        Args:
            raw_data: Raw record with source column names

        Returns:
            Record with canonical field names
        """
        mapped = {}

        for source_col, canonical_field in self.field_mappings.items():
            if source_col in raw_data:
                mapped[canonical_field] = raw_data[source_col]

        return mapped


def validate_records(
    records: list[dict[str, Any]],
    field_mappings: dict[str, str],
    date_format: str | None = None,
) -> tuple[list[ValidationResult], int, int]:
    """Validate a batch of records.

    Args:
        records: List of raw record dictionaries
        field_mappings: Schema mapping configuration
        date_format: Expected date format

    Returns:
        Tuple of (validation results, valid count, invalid count)
    """
    validator = RecordValidator(
        field_mappings=field_mappings,
        date_format=date_format,
    )

    results = []
    valid_count = 0
    invalid_count = 0

    for record in records:
        result = validator.validate_record(record)
        results.append(result)

        if result.is_valid:
            valid_count += 1
        else:
            invalid_count += 1

    return results, valid_count, invalid_count
