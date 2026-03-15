"""Hashing utilities for records and files."""

import hashlib
import json
from typing import Any


def compute_sha256(data: bytes) -> str:
    """Compute SHA-256 hash of bytes."""
    return hashlib.sha256(data).hexdigest()


def compute_file_hash(file_path: str) -> str:
    """Compute SHA-256 hash of a file."""
    sha256_hash = hashlib.sha256()
    with open(file_path, "rb") as f:
        for byte_block in iter(lambda: f.read(4096), b""):
            sha256_hash.update(byte_block)
    return sha256_hash.hexdigest()


def compute_record_hash(data: dict[str, Any]) -> str:
    """Compute a stable hash for a record dictionary.

    Sorts keys for consistency and handles various data types.
    """
    # Serialize with sorted keys for consistency
    serialized = json.dumps(data, sort_keys=True, default=str)
    return compute_sha256(serialized.encode("utf-8"))


def compute_canonical_hash(
    source_system_id: str,
    record_date: str | None,
    amount: str | None,
    reference_code: str | None,
    external_record_id: str | None,
) -> str:
    """Compute hash for a canonical record based on key fields.

    This is used for deduplication and matching.
    """
    fields = [
        source_system_id,
        record_date or "",
        amount or "",
        reference_code or "",
        external_record_id or "",
    ]
    combined = "|".join(fields)
    return compute_sha256(combined.encode("utf-8"))
