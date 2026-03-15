"""CSV and Excel file parsing utilities."""

import csv
import hashlib
import io
from pathlib import Path
from typing import Any, Iterator

import pandas as pd


def compute_file_hash(file_content: bytes) -> str:
    """Compute SHA-256 hash of file content."""
    return hashlib.sha256(file_content).hexdigest()


def compute_row_hash(row_data: dict) -> str:
    """Compute hash of a single row for deduplication."""
    # Sort keys for consistent hashing
    sorted_items = sorted(row_data.items())
    row_str = str(sorted_items)
    return hashlib.sha256(row_str.encode()).hexdigest()


def parse_csv(
    file_content: bytes,
    encoding: str = "utf-8",
    skip_rows: int = 0,
    delimiter: str = ",",
) -> Iterator[dict[str, Any]]:
    """Parse CSV file and yield rows as dictionaries.

    Args:
        file_content: Raw file bytes
        encoding: File encoding
        skip_rows: Number of header rows to skip
        delimiter: CSV delimiter character

    Yields:
        Dictionary for each row with column names as keys
    """
    text_content = file_content.decode(encoding)
    reader = csv.DictReader(
        io.StringIO(text_content),
        delimiter=delimiter,
    )

    for i, row in enumerate(reader):
        if i < skip_rows:
            continue
        # Clean up whitespace in values
        cleaned_row = {k: v.strip() if isinstance(v, str) else v for k, v in row.items()}
        yield cleaned_row


def parse_excel(
    file_content: bytes,
    sheet_name: str | int = 0,
    skip_rows: int = 0,
) -> Iterator[dict[str, Any]]:
    """Parse Excel file and yield rows as dictionaries.

    Args:
        file_content: Raw file bytes
        sheet_name: Sheet name or index to read
        skip_rows: Number of header rows to skip

    Yields:
        Dictionary for each row with column names as keys
    """
    df = pd.read_excel(
        io.BytesIO(file_content),
        sheet_name=sheet_name,
        skiprows=skip_rows,
    )

    # Replace NaN with None
    df = df.where(pd.notnull(df), None)

    for _, row in df.iterrows():
        row_dict = row.to_dict()
        # Clean up whitespace in string values
        cleaned_row = {
            k: v.strip() if isinstance(v, str) else v
            for k, v in row_dict.items()
        }
        yield cleaned_row


def parse_file(
    file_content: bytes,
    file_name: str,
    encoding: str = "utf-8",
    skip_rows: int = 0,
    sheet_name: str | int = 0,
) -> Iterator[dict[str, Any]]:
    """Parse file based on extension.

    Args:
        file_content: Raw file bytes
        file_name: Original file name (used to determine type)
        encoding: File encoding (for CSV)
        skip_rows: Number of header rows to skip
        sheet_name: Sheet name or index (for Excel)

    Yields:
        Dictionary for each row with column names as keys

    Raises:
        ValueError: If file type is not supported
    """
    ext = Path(file_name).suffix.lower()

    if ext == ".csv":
        yield from parse_csv(file_content, encoding=encoding, skip_rows=skip_rows)
    elif ext in (".xlsx", ".xls"):
        yield from parse_excel(file_content, sheet_name=sheet_name, skip_rows=skip_rows)
    else:
        raise ValueError(f"Unsupported file type: {ext}")


def get_column_names(
    file_content: bytes,
    file_name: str,
    encoding: str = "utf-8",
    sheet_name: str | int = 0,
) -> list[str]:
    """Extract column names from a file.

    Args:
        file_content: Raw file bytes
        file_name: Original file name
        encoding: File encoding (for CSV)
        sheet_name: Sheet name or index (for Excel)

    Returns:
        List of column names
    """
    ext = Path(file_name).suffix.lower()

    if ext == ".csv":
        text_content = file_content.decode(encoding)
        reader = csv.reader(io.StringIO(text_content))
        return next(reader, [])
    elif ext in (".xlsx", ".xls"):
        df = pd.read_excel(io.BytesIO(file_content), sheet_name=sheet_name, nrows=0)
        return list(df.columns)
    else:
        raise ValueError(f"Unsupported file type: {ext}")


def count_rows(
    file_content: bytes,
    file_name: str,
    encoding: str = "utf-8",
    sheet_name: str | int = 0,
    skip_rows: int = 0,
) -> int:
    """Count the number of data rows in a file.

    Args:
        file_content: Raw file bytes
        file_name: Original file name
        encoding: File encoding (for CSV)
        sheet_name: Sheet name or index (for Excel)
        skip_rows: Number of additional header rows to skip (after the column header)

    Returns:
        Number of data rows (excluding header and skipped rows)
    """
    ext = Path(file_name).suffix.lower()

    if ext == ".csv":
        text_content = file_content.decode(encoding)
        # Count lines minus header and skipped rows
        return max(0, sum(1 for _ in io.StringIO(text_content)) - 1 - skip_rows)
    elif ext in (".xlsx", ".xls"):
        df = pd.read_excel(io.BytesIO(file_content), sheet_name=sheet_name, skiprows=skip_rows)
        return len(df)
    else:
        raise ValueError(f"Unsupported file type: {ext}")
