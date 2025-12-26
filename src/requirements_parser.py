"""
Parse multi-requirement meal planning requests into structured DayRequirement objects.

Python-first parser - no LLM required for typical cases.
Uses canonical vocabulary from src/tag_canon.py.

Examples:
    "monday italian, tuesday irish"
    "all vegetarian"
    "italian monday and tuesday, irish wednesday"
    "wednesday vegetarian for kids, thursday surprise me"
"""

import re
from dataclasses import dataclass, field
from typing import List, Optional, Tuple

from tag_canon import (
    CANON_CUISINES,
    CANON_DIETARY_HARD,
    CANON_DIETARY_SOFT,
    normalize_tag,
)


@dataclass
class DayRequirement:
    """Structured requirement for a specific day."""
    date: str  # "YYYY-MM-DD" format
    cuisine: Optional[str] = None  # Canonical cuisine tag
    dietary_hard: List[str] = field(default_factory=list)  # Validated + retry
    dietary_soft: List[str] = field(default_factory=list)  # Preference only
    surprise: bool = False  # True = dealer's choice
    raw_text: Optional[str] = None  # Original clause for debugging
    unhandled: List[str] = field(default_factory=list)  # Unrecognized constraints

    def __str__(self) -> str:
        parts = [f"date={self.date}"]
        if self.cuisine:
            parts.append(f"cuisine={self.cuisine}")
        if self.dietary_hard:
            parts.append(f"hard={self.dietary_hard}")
        if self.dietary_soft:
            parts.append(f"soft={self.dietary_soft}")
        if self.surprise:
            parts.append("surprise")
        if self.unhandled:
            parts.append(f"unhandled={self.unhandled}")
        return f"DayReq({', '.join(parts)})"


# Day name to index mapping (0 = first selected day)
DAY_NAMES = {
    "monday": 0, "mon": 0,
    "tuesday": 1, "tue": 1, "tues": 1,
    "wednesday": 2, "wed": 2,
    "thursday": 3, "thu": 3, "thur": 3, "thurs": 3,
    "friday": 4, "fri": 4,
    "saturday": 5, "sat": 5,
    "sunday": 6, "sun": 6,
}

# Patterns
SURPRISE_PATTERNS = ["surprise me", "surprise", "dealer's choice", "your choice", "anything"]


def parse_requirements(message: str, dates: List[str]) -> List[DayRequirement]:
    """
    Parse user message into per-day requirements.

    Args:
        message: User's natural language request
        dates: List of selected dates in YYYY-MM-DD format

    Returns:
        List of DayRequirement, one per date

    Examples:
        parse_requirements("monday italian, tuesday irish", ["2025-01-06", "2025-01-07"])
        -> [DayReq(date="2025-01-06", cuisine="italian"),
            DayReq(date="2025-01-07", cuisine="irish")]
    """
    if not dates:
        return []

    msg_lower = message.lower().strip()

    # Initialize with default requirements for all dates
    requirements = [DayRequirement(date=d) for d in dates]

    # Check for "all X" pattern first (applies to all days)
    all_match = re.search(r'\ball\s+(\w+)', msg_lower)
    if all_match:
        constraint = all_match.group(1)
        _apply_constraint_to_all(requirements, constraint)
        return requirements

    # Check for global cuisine without day specifiers
    # e.g., "italian food", "make me italian meals", "5 italian dinners"
    if not _has_day_specifiers(msg_lower):
        global_constraints = _extract_global_constraints(msg_lower)
        if global_constraints:
            for req in requirements:
                _apply_constraints(req, global_constraints)
            return requirements

    # Parse day-specific clauses
    clauses = _split_into_clauses(msg_lower)

    for clause in clauses:
        day_indices, remaining = _extract_days_from_clause(clause, len(dates))
        constraints = _extract_constraints(remaining)

        for idx in day_indices:
            if 0 <= idx < len(requirements):
                requirements[idx].raw_text = clause
                _apply_constraints(requirements[idx], constraints)

    return requirements


def _has_day_specifiers(message: str) -> bool:
    """Check if message contains day names or day references as whole words."""
    # Use word boundary regex to avoid matching "fri" in "friendly"
    for day in DAY_NAMES.keys():
        if re.search(rf'\b{day}\b', message):
            return True
    return False


def _split_into_clauses(message: str) -> List[str]:
    """Split message into day-specific clauses."""
    # Split on common delimiters
    # "monday italian, tuesday irish" -> ["monday italian", "tuesday irish"]
    # "monday italian. tuesday irish" -> ["monday italian", "tuesday irish"]

    # First split on commas and periods
    parts = re.split(r'[,.]', message)

    # Filter empty parts and strip whitespace
    clauses = [p.strip() for p in parts if p.strip()]

    return clauses


def _extract_days_from_clause(clause: str, num_dates: int) -> Tuple[List[int], str]:
    """
    Extract day indices from a clause.

    Returns:
        (list of day indices, remaining text without day names)
    """
    indices = []
    remaining = clause

    # Handle "X monday and tuesday" or "monday and tuesday X"
    # First, find all day references
    words = clause.split()

    for i, word in enumerate(words):
        word_clean = word.lower().strip(".,;:")

        if word_clean in DAY_NAMES:
            idx = DAY_NAMES[word_clean]
            if idx < num_dates and idx not in indices:
                indices.append(idx)
            remaining = remaining.replace(word, " ", 1)

    # Clean up remaining text
    remaining = " ".join(remaining.split())

    # If no days found, try to infer from position (e.g., first clause = first day)
    # But only if there's one clause per day
    # For now, return empty if no explicit days

    return indices, remaining


def _extract_constraints(text: str) -> dict:
    """
    Extract constraints from text.

    Returns:
        {
            "cuisine": Optional[str],
            "dietary_hard": List[str],
            "dietary_soft": List[str],
            "surprise": bool,
            "unhandled": List[str]
        }
    """
    result = {
        "cuisine": None,
        "dietary_hard": [],
        "dietary_soft": [],
        "surprise": False,
        "unhandled": [],
    }

    text_lower = text.lower()

    # Check for surprise
    for pattern in SURPRISE_PATTERNS:
        if pattern in text_lower:
            result["surprise"] = True
            return result  # Surprise overrides other constraints

    # First, check for known multi-word phrases in the full text
    # This catches "kid friendly", "gluten free", etc.
    multi_word_checks = [
        "kid friendly", "kid-friendly", "for kids",
        "gluten free", "gluten-free",
        "dairy free", "dairy-free",
        "low carb", "low-carb",
        "plant based", "plant-based",
    ]
    for phrase in multi_word_checks:
        if phrase in text_lower:
            normalized = normalize_tag(phrase)
            if normalized:
                _categorize_constraint(normalized, result)

    # Extract words and check against canonical tags
    words = text_lower.split()

    # Check for known single-word tags
    stop_words = {"for", "me", "and", "with", "a", "the", "make", "plan", "meals",
                  "food", "dinner", "dinners", "meal", "kid", "friendly", "free",
                  "low", "carb", "gluten", "dairy", "based", "plant"}

    for word in words:
        # Skip if word is part of a phrase we already matched
        if word in stop_words:
            continue

        normalized = normalize_tag(word)
        if normalized:
            # Don't add if already added via phrase matching
            if normalized not in result["dietary_hard"] and normalized not in result["dietary_soft"]:
                if result["cuisine"] != normalized:
                    _categorize_constraint(normalized, result)
        elif len(word) > 2 and word.isalpha():
            # Potential unhandled constraint
            result["unhandled"].append(word)

    return result


def _categorize_constraint(tag: str, result: dict):
    """Categorize a normalized tag into the appropriate constraint type."""
    if tag in CANON_CUISINES:
        result["cuisine"] = tag
    elif tag in CANON_DIETARY_HARD:
        if tag not in result["dietary_hard"]:
            result["dietary_hard"].append(tag)
    elif tag in CANON_DIETARY_SOFT:
        if tag not in result["dietary_soft"]:
            result["dietary_soft"].append(tag)


def _apply_constraints(req: DayRequirement, constraints: dict):
    """Apply extracted constraints to a DayRequirement."""
    if constraints.get("cuisine"):
        req.cuisine = constraints["cuisine"]
    if constraints.get("dietary_hard"):
        req.dietary_hard.extend(constraints["dietary_hard"])
    if constraints.get("dietary_soft"):
        req.dietary_soft.extend(constraints["dietary_soft"])
    if constraints.get("surprise"):
        req.surprise = True
    if constraints.get("unhandled"):
        req.unhandled.extend(constraints["unhandled"])


def _apply_constraint_to_all(requirements: List[DayRequirement], constraint: str):
    """Apply a single constraint to all requirements."""
    normalized = normalize_tag(constraint)
    if normalized:
        constraints = {"cuisine": None, "dietary_hard": [], "dietary_soft": [], "surprise": False, "unhandled": []}
        _categorize_constraint(normalized, constraints)
        for req in requirements:
            _apply_constraints(req, constraints)
    else:
        # Unhandled constraint
        for req in requirements:
            req.unhandled.append(constraint)


def _extract_global_constraints(message: str) -> dict:
    """Extract constraints that apply globally (no day specifiers)."""
    return _extract_constraints(message)
