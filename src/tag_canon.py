"""
Canonical tag mapping for meal planning constraints.

Derived from docs/tag_report.json analysis of 492,630 recipes.
This file provides the authoritative vocabulary for:
- Cuisine constraints (hard: validated + retry)
- Dietary constraints (hard vs soft)
- Course/meal-type constraints (for validation)

All tag sets are based on actual database coverage.
"""

from typing import Optional, Set

# =============================================================================
# CUISINE TAGS (Hard constraints - validated + retry on mismatch)
# =============================================================================
# Top cuisines by recipe count in database
CANON_CUISINES: Set[str] = {
    "italian",      # 15,375 recipes
    "mexican",      # 14,536 recipes
    "indian",       # 6,207 recipes
    "french",       # 4,823 recipes
    "chinese",      # 4,239 recipes
    "greek",        # 4,145 recipes
    "thai",         # 2,561 recipes
    "german",       # 2,508 recipes
    "cajun",        # 2,442 recipes
    "spanish",      # 2,089 recipes
    "japanese",     # 1,903 recipes
    "irish",        # 1,197 recipes
    "vietnamese",   # 691 recipes
    "korean",       # 547 recipes
    "american",     # 60,518 recipes
    "asian",        # 26,728 recipes (broader category)
    "european",     # 49,542 recipes (broader category)
}

# =============================================================================
# DIETARY TAGS
# =============================================================================
# Hard dietary constraints (validated + retry on failure)
# These are reliably tagged and users expect strict enforcement
CANON_DIETARY_HARD: Set[str] = {
    "vegetarian",   # 67,841 recipes - strong signal
    "vegan",        # 19,640 recipes - strong signal
}

# Soft dietary constraints (preference only, no retry on failure)
# These are less reliably tagged or represent preferences not hard requirements
CANON_DIETARY_SOFT: Set[str] = {
    "kid-friendly",   # 50,542 recipes
    "healthy",        # 83,187 recipes
    "low-carb",       # 87,825 recipes
    "gluten-free",    # 11,353 recipes
    "dairy-free",     # 343 recipes (sparse coverage)
    "low-fat",        # 45,024 recipes
    "weeknight",      # 43,762 recipes
}

# =============================================================================
# COURSE/MEAL-TYPE TAGS
# =============================================================================
# Tags that indicate a recipe is suitable as a dinner main dish
CANON_COURSE_MAIN: Set[str] = {
    "main-dish",    # 150,134 recipes
    "lunch",        # 44,158 recipes (acceptable for dinner)
}

# Tags that should EXCLUDE a recipe from dinner main selection
# If a recipe has ONLY these tags and not main-dish, reject it
CANON_COURSE_EXCLUDE: Set[str] = {
    "desserts",         # 103,995 recipes
    "appetizers",       # 45,146 recipes
    "beverages",        # 16,206 recipes
    "condiments-etc",   # 21,575 recipes
    "sauces",           # 10,688 recipes
    "snacks",           # 16,516 recipes
    "salad-dressings",  # 4,095 recipes
    "sweet-sauces",     # 1,716 recipes
    "savory-sauces",    # 3,573 recipes
}

# =============================================================================
# TIME-RELATED TAGS (for future use)
# =============================================================================
CANON_TIME_TAGS: Set[str] = {
    "15-minutes-or-less",   # 82,974 recipes
    "30-minutes-or-less",   # 115,905 recipes
    "60-minutes-or-less",   # 153,554 recipes
}

# =============================================================================
# SYNONYM MAPPINGS
# =============================================================================
# Maps canonical tag -> set of user input variants that should normalize to it
TAG_SYNONYMS: dict[str, Set[str]] = {
    # Cuisine synonyms
    "american": {"american", "usa", "us"},
    "italian": {"italian", "italy"},
    "mexican": {"mexican", "mexico"},
    "chinese": {"chinese", "china"},
    "japanese": {"japanese", "japan"},
    "thai": {"thai", "thailand"},
    "indian": {"indian", "india"},
    "french": {"french", "france"},
    "greek": {"greek", "greece"},
    "german": {"german", "germany"},
    "spanish": {"spanish", "spain"},
    "korean": {"korean", "korea"},
    "vietnamese": {"vietnamese", "vietnam"},
    "irish": {"irish", "ireland"},
    "cajun": {"cajun", "creole", "louisiana"},

    # Dietary synonyms
    "vegetarian": {"vegetarian", "veggie", "meatless", "no meat"},
    "vegan": {"vegan", "plant-based", "plant based"},
    "kid-friendly": {"kid-friendly", "kid friendly", "kids", "family-friendly", "family friendly", "for kids"},
    "healthy": {"healthy", "nutritious"},
    "low-carb": {"low-carb", "low carb", "keto", "low carbs"},
    "gluten-free": {"gluten-free", "gluten free", "no gluten"},
    "dairy-free": {"dairy-free", "dairy free", "no dairy"},

    # Course synonyms
    "main-dish": {"main-dish", "main dish", "main course", "entree", "dinner", "mains"},
    "desserts": {"desserts", "dessert", "sweet", "sweets"},
    "appetizers": {"appetizers", "appetizer", "starter", "starters"},
    "beverages": {"beverages", "beverage", "drink", "drinks"},

    # Time synonyms (map to actual DB tags)
    "quick": {"quick", "fast", "speedy"},
    "weeknight": {"weeknight", "weeknights", "weekday"},
}


def normalize_tag(user_input: str) -> Optional[str]:
    """
    Normalize user input to canonical tag.

    Args:
        user_input: Raw user text (e.g., "italian", "kid friendly", "veggie")

    Returns:
        Canonical tag string if recognized, None otherwise

    Examples:
        normalize_tag("italian") -> "italian"
        normalize_tag("kid friendly") -> "kid-friendly"
        normalize_tag("veggie") -> "vegetarian"
        normalize_tag("something weird") -> None
    """
    lower = user_input.lower().strip()

    # Direct match against all canonical sets
    all_canonical = (
        CANON_CUISINES |
        CANON_DIETARY_HARD |
        CANON_DIETARY_SOFT |
        CANON_COURSE_MAIN |
        {"quick", "weeknight"}  # Common aliases
    )

    if lower in all_canonical:
        return lower

    # Check synonyms
    for canon, variants in TAG_SYNONYMS.items():
        if lower in variants:
            return canon
        # Partial match for multi-word inputs
        for variant in variants:
            if variant in lower:
                return canon

    return None


def get_tag_type(tag: str) -> str:
    """
    Determine the type/category of a canonical tag.

    Args:
        tag: Canonical tag string

    Returns:
        One of: "cuisine", "dietary_hard", "dietary_soft", "course_main",
                "course_exclude", "time", "unknown"
    """
    if tag in CANON_CUISINES:
        return "cuisine"
    elif tag in CANON_DIETARY_HARD:
        return "dietary_hard"
    elif tag in CANON_DIETARY_SOFT:
        return "dietary_soft"
    elif tag in CANON_COURSE_MAIN:
        return "course_main"
    elif tag in CANON_COURSE_EXCLUDE:
        return "course_exclude"
    elif tag in CANON_TIME_TAGS or tag in {"quick", "weeknight"}:
        return "time"
    else:
        return "unknown"


def get_db_tags_for_constraint(canonical: str) -> Set[str]:
    """
    Get all DB tag variants that satisfy a canonical constraint.

    Args:
        canonical: Canonical tag (e.g., "italian", "vegetarian")

    Returns:
        Set of DB tags that match (usually just {canonical} but can include synonyms)
    """
    # For now, DB tags match canonical tags directly
    # If we discover DB uses different tags, add mappings here
    result = {canonical}

    # Add any known DB variants
    if canonical in TAG_SYNONYMS:
        # Only add variants that are actually DB tags (not user input variants)
        # For now, assume DB uses hyphenated forms
        pass

    return result
