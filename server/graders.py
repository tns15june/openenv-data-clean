"""Validation-based grading functions for data quality issues."""

import re
from datetime import datetime
from typing import Any, Dict, List, Set


def validate_email(value: Any) -> bool:
    """Value must be a valid email: user@domain.tld"""
    s = str(value).strip()
    return bool(re.match(r"^[\w.+\-]+@[\w\-]+\.\w{2,}$", s))


def validate_phone(value: Any) -> bool:
    """Value must contain only digits, dashes, spaces, parens, plus. At least 10 digits."""
    s = str(value).strip()
    if not re.match(r"^[\d\-\(\)\s\+\.]+$", s):
        return False
    digits = re.sub(r"\D", "", s)
    return len(digits) >= 10


def validate_date_format(value: Any) -> bool:
    """Value must be a valid YYYY-MM-DD date."""
    s = str(value).strip()
    try:
        datetime.strptime(s, "%Y-%m-%d")
        return True
    except ValueError:
        return False


def validate_non_empty(value: Any) -> bool:
    """Value must not be empty or whitespace-only."""
    if value is None:
        return False
    return str(value).strip() != ""


def validate_positive_number(value: Any) -> bool:
    """Value must be a positive number."""
    try:
        return float(value) > 0
    except (ValueError, TypeError):
        return False


def validate_in_range(value: Any, low: float, high: float) -> bool:
    """Value must be a number within [low, high]."""
    try:
        v = float(value)
        return low <= v <= high
    except (ValueError, TypeError):
        return False


def validate_canonical(value: Any, canonical_set: Set[str]) -> bool:
    """Value must exactly match one of the canonical values."""
    return str(value).strip() in canonical_set


def validate_no_excess_whitespace(value: Any) -> bool:
    """Value must be trimmed with no double spaces."""
    s = str(value)
    return s == s.strip() and "  " not in s


def validate_referential_integrity(
    value: Any, valid_ids: Set[str]
) -> bool:
    """Value must be an ID that exists in the given set."""
    return str(value).strip() in valid_ids


def validate_temporal_order(
    hire_date: str, termination_date: str
) -> bool:
    """Termination date must be after hire date. Empty termination is valid."""
    t = str(termination_date).strip()
    if not t or t.lower() in ("", "none", "null", "nat"):
        return True
    try:
        h = datetime.strptime(str(hire_date).strip(), "%Y-%m-%d")
        td = datetime.strptime(t, "%Y-%m-%d")
        return td > h
    except ValueError:
        return False


def validate_row_deleted(
    current_data: List[Dict[str, Any]], original_row: Dict[str, Any]
) -> bool:
    """Check that a specific original row no longer exists in the dataset."""
    for row in current_data:
        if all(
            str(row.get(k, "")) == str(v) for k, v in original_row.items()
        ):
            return False
    return True


# Issue type → validation function mapping
VALIDATORS = {
    "invalid_email": lambda val, **_: validate_email(val),
    "invalid_phone": lambda val, **_: validate_phone(val),
    "wrong_date_format": lambda val, **_: validate_date_format(val),
    "invalid_date": lambda val, **_: validate_date_format(val),
    "missing_value": lambda val, **_: validate_non_empty(val),
    "negative_number": lambda val, **_: validate_positive_number(val),
    "outlier": lambda val, low=0, high=0, **_: validate_in_range(val, low, high),
    "inconsistent_format": lambda val, canonical_set=frozenset(), **_: validate_canonical(
        val, canonical_set
    ),
    "excess_whitespace": lambda val, **_: validate_no_excess_whitespace(val),
    "referential_integrity": lambda val, valid_ids=frozenset(), **_: validate_referential_integrity(
        val, valid_ids
    ),
    "duplicate_row": None,  # Handled separately via validate_row_deleted
    "temporal_inconsistency": None,  # Handled separately with two columns
    "score_out_of_range": lambda val, low=0, high=10, **_: validate_in_range(
        val, low, high
    ),
    "cross_column_violation": None,  # Handled separately with multi-column logic
}
