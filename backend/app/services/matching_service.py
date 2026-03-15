"""Matching service for reconciliation."""

from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal
from enum import Enum
from typing import Any

from rapidfuzz import fuzz

from app.utils.dates import date_difference_days, is_within_tolerance as date_within_tolerance
from app.utils.money import (
    amount_difference,
    amount_difference_percent,
    is_within_tolerance as amount_within_tolerance,
)


class MatchType(str, Enum):
    """Type of match found."""

    EXACT = "exact"
    TOLERANCE = "tolerance"
    FUZZY = "fuzzy"
    SCORED = "scored"
    NONE = "none"


@dataclass
class MatchFeatures:
    """Features used to evaluate a match."""

    # Exact match indicators
    external_id_match: bool = False
    reference_match: bool = False

    # Date features
    date_exact_match: bool = False
    date_diff_days: int | None = None
    date_within_tolerance: bool = False

    # Amount features
    amount_exact_match: bool = False
    amount_diff: Decimal | None = None
    amount_diff_percent: float | None = None
    amount_within_tolerance: bool = False

    # Fuzzy features
    description_similarity: float = 0.0
    counterparty_similarity: float = 0.0
    reference_similarity: float = 0.0

    # Computed score
    total_score: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for storage."""
        return {
            "external_id_match": self.external_id_match,
            "reference_match": self.reference_match,
            "date_exact_match": self.date_exact_match,
            "date_diff_days": self.date_diff_days,
            "date_within_tolerance": self.date_within_tolerance,
            "amount_exact_match": self.amount_exact_match,
            "amount_diff": str(self.amount_diff) if self.amount_diff else None,
            "amount_diff_percent": self.amount_diff_percent,
            "amount_within_tolerance": self.amount_within_tolerance,
            "description_similarity": self.description_similarity,
            "counterparty_similarity": self.counterparty_similarity,
            "reference_similarity": self.reference_similarity,
            "total_score": self.total_score,
        }


@dataclass
class MatchResult:
    """Result of matching two records."""

    match_type: MatchType
    score: float
    features: MatchFeatures
    is_match: bool

    @property
    def confidence(self) -> str:
        """Return confidence level based on score."""
        if self.score >= 0.95:
            return "high"
        elif self.score >= 0.80:
            return "medium"
        elif self.score >= 0.60:
            return "low"
        else:
            return "none"


@dataclass
class MatchingConfig:
    """Configuration for matching thresholds."""

    # Date tolerance
    date_tolerance_days: int = 3

    # Amount tolerance (as decimal, e.g., 0.01 = 1%)
    amount_tolerance_percent: float = 0.01

    # Fuzzy matching thresholds
    fuzzy_threshold: float = 0.80
    description_weight: float = 0.3
    counterparty_weight: float = 0.3
    reference_weight: float = 0.4

    # Score weights for combined scoring
    exact_id_weight: float = 0.30
    date_weight: float = 0.25
    amount_weight: float = 0.25
    fuzzy_weight: float = 0.20

    # Minimum score to consider a match
    min_match_score: float = 0.70

    # High confidence threshold
    high_confidence_score: float = 0.95


class MatchingService:
    """Service for matching records during reconciliation."""

    def __init__(self, config: MatchingConfig | None = None):
        """Initialize with matching configuration."""
        self.config = config or MatchingConfig()

    def match_records(
        self,
        left_record: dict[str, Any],
        right_record: dict[str, Any],
    ) -> MatchResult:
        """Compare two records and return match result.

        Args:
            left_record: First record (normalized)
            right_record: Second record (normalized)

        Returns:
            MatchResult with match type, score, and features
        """
        features = self._extract_features(left_record, right_record)
        features.total_score = self._compute_score(features)

        # Determine match type
        match_type = self._determine_match_type(features)

        is_match = features.total_score >= self.config.min_match_score

        return MatchResult(
            match_type=match_type,
            score=features.total_score,
            features=features,
            is_match=is_match,
        )

    def exact_match(
        self,
        left_record: dict[str, Any],
        right_record: dict[str, Any],
    ) -> bool:
        """Check if two records are an exact match.

        Exact match requires:
        - Same external_record_id OR same reference_code
        - Same amount
        - Same date
        """
        # Check external ID
        left_id = left_record.get("external_record_id")
        right_id = right_record.get("external_record_id")
        id_match = left_id and right_id and left_id == right_id

        # Check reference
        left_ref = left_record.get("reference_code")
        right_ref = right_record.get("reference_code")
        ref_match = left_ref and right_ref and left_ref == right_ref

        if not (id_match or ref_match):
            return False

        # Check amount
        left_amount = left_record.get("amount")
        right_amount = right_record.get("amount")
        if left_amount != right_amount:
            return False

        # Check date
        left_date = left_record.get("record_date")
        right_date = right_record.get("record_date")
        if left_date != right_date:
            return False

        return True

    def tolerance_match(
        self,
        left_record: dict[str, Any],
        right_record: dict[str, Any],
    ) -> bool:
        """Check if records match within tolerance.

        Tolerance match requires:
        - Same external_record_id OR same reference_code
        - Amount within tolerance
        - Date within tolerance
        """
        # Check external ID or reference
        left_id = left_record.get("external_record_id")
        right_id = right_record.get("external_record_id")
        id_match = left_id and right_id and left_id == right_id

        left_ref = left_record.get("reference_code")
        right_ref = right_record.get("reference_code")
        ref_match = left_ref and right_ref and left_ref == right_ref

        if not (id_match or ref_match):
            return False

        # Check amount within tolerance
        left_amount = left_record.get("amount")
        right_amount = right_record.get("amount")
        if not amount_within_tolerance(
            left_amount, right_amount, self.config.amount_tolerance_percent
        ):
            return False

        # Check date within tolerance
        left_date = left_record.get("record_date")
        right_date = right_record.get("record_date")
        if not date_within_tolerance(
            left_date, right_date, self.config.date_tolerance_days
        ):
            return False

        return True

    def fuzzy_match(
        self,
        left_record: dict[str, Any],
        right_record: dict[str, Any],
    ) -> float:
        """Compute fuzzy match score based on text fields.

        Returns score between 0 and 1.
        """
        scores = []
        weights = []

        # Description similarity
        left_desc = left_record.get("description", "")
        right_desc = right_record.get("description", "")
        if left_desc and right_desc:
            desc_score = fuzz.ratio(str(left_desc), str(right_desc)) / 100.0
            scores.append(desc_score)
            weights.append(self.config.description_weight)

        # Counterparty similarity
        left_cp = left_record.get("counterparty", "")
        right_cp = right_record.get("counterparty", "")
        if left_cp and right_cp:
            cp_score = fuzz.ratio(str(left_cp), str(right_cp)) / 100.0
            scores.append(cp_score)
            weights.append(self.config.counterparty_weight)

        # Reference similarity
        left_ref = left_record.get("reference_code", "")
        right_ref = right_record.get("reference_code", "")
        if left_ref and right_ref:
            ref_score = fuzz.ratio(str(left_ref), str(right_ref)) / 100.0
            scores.append(ref_score)
            weights.append(self.config.reference_weight)

        if not scores:
            return 0.0

        # Weighted average
        total_weight = sum(weights)
        if total_weight == 0:
            return 0.0

        return sum(s * w for s, w in zip(scores, weights)) / total_weight

    def _extract_features(
        self,
        left_record: dict[str, Any],
        right_record: dict[str, Any],
    ) -> MatchFeatures:
        """Extract all matching features from two records."""
        features = MatchFeatures()

        # External ID match
        left_id = left_record.get("external_record_id")
        right_id = right_record.get("external_record_id")
        features.external_id_match = bool(left_id and right_id and left_id == right_id)

        # Reference match
        left_ref = left_record.get("reference_code")
        right_ref = right_record.get("reference_code")
        features.reference_match = bool(left_ref and right_ref and left_ref == right_ref)

        # Date features
        left_date = left_record.get("record_date")
        right_date = right_record.get("record_date")
        if isinstance(left_date, date) and isinstance(right_date, date):
            features.date_exact_match = left_date == right_date
            features.date_diff_days = date_difference_days(left_date, right_date)
            features.date_within_tolerance = date_within_tolerance(
                left_date, right_date, self.config.date_tolerance_days
            )

        # Amount features
        left_amount = left_record.get("amount")
        right_amount = right_record.get("amount")
        if isinstance(left_amount, Decimal) and isinstance(right_amount, Decimal):
            features.amount_exact_match = left_amount == right_amount
            features.amount_diff = amount_difference(left_amount, right_amount)
            features.amount_diff_percent = amount_difference_percent(left_amount, right_amount)
            features.amount_within_tolerance = amount_within_tolerance(
                left_amount, right_amount, self.config.amount_tolerance_percent
            )

        # Fuzzy features
        left_desc = left_record.get("description", "")
        right_desc = right_record.get("description", "")
        if left_desc and right_desc:
            features.description_similarity = fuzz.ratio(str(left_desc), str(right_desc)) / 100.0

        left_cp = left_record.get("counterparty", "")
        right_cp = right_record.get("counterparty", "")
        if left_cp and right_cp:
            features.counterparty_similarity = fuzz.ratio(str(left_cp), str(right_cp)) / 100.0

        if left_ref and right_ref:
            features.reference_similarity = fuzz.ratio(str(left_ref), str(right_ref)) / 100.0

        return features

    def _compute_score(self, features: MatchFeatures) -> float:
        """Compute overall match score from features."""
        score = 0.0

        # Exact ID/reference match contributes heavily
        if features.external_id_match or features.reference_match:
            score += self.config.exact_id_weight
        elif features.reference_similarity > 0:
            score += self.config.exact_id_weight * features.reference_similarity

        # Date contribution
        if features.date_exact_match:
            score += self.config.date_weight
        elif features.date_within_tolerance:
            # Partial credit based on how close
            if features.date_diff_days is not None:
                days_factor = 1.0 - (features.date_diff_days / (self.config.date_tolerance_days + 1))
                score += self.config.date_weight * max(0, days_factor)

        # Amount contribution
        if features.amount_exact_match:
            score += self.config.amount_weight
        elif features.amount_within_tolerance:
            # Partial credit based on how close
            if features.amount_diff_percent is not None:
                amount_factor = 1.0 - (features.amount_diff_percent / (self.config.amount_tolerance_percent + 0.001))
                score += self.config.amount_weight * max(0, min(1, amount_factor))

        # Fuzzy contribution
        fuzzy_score = (
            features.description_similarity * self.config.description_weight +
            features.counterparty_similarity * self.config.counterparty_weight +
            features.reference_similarity * self.config.reference_weight
        )
        total_fuzzy_weight = (
            self.config.description_weight +
            self.config.counterparty_weight +
            self.config.reference_weight
        )
        if total_fuzzy_weight > 0:
            normalized_fuzzy = fuzzy_score / total_fuzzy_weight
            score += self.config.fuzzy_weight * normalized_fuzzy

        return min(1.0, score)

    def _determine_match_type(self, features: MatchFeatures) -> MatchType:
        """Determine the type of match based on features."""
        # Check for exact match
        has_id_match = features.external_id_match or features.reference_match
        if has_id_match and features.amount_exact_match and features.date_exact_match:
            return MatchType.EXACT

        # Check for tolerance match
        if has_id_match and features.amount_within_tolerance and features.date_within_tolerance:
            return MatchType.TOLERANCE

        # Check for fuzzy match
        fuzzy_score = max(
            features.description_similarity,
            features.counterparty_similarity,
            features.reference_similarity,
        )
        if fuzzy_score >= self.config.fuzzy_threshold:
            return MatchType.FUZZY

        # Scored match if score is above threshold
        if features.total_score >= self.config.min_match_score:
            return MatchType.SCORED

        return MatchType.NONE
