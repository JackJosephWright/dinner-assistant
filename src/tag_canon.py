"""
Canonical tag vocabulary for meal planning constraints.

Minimal runtime enforcement only. Analysis data in docs/tag_report.md.
"""

from typing import Optional, Set

# Cuisines (hard constraint - validated + retry)
CANON_CUISINES: Set[str] = {
    "italian", "mexican", "indian", "french", "chinese", "greek",
    "thai", "german", "cajun", "spanish", "japanese", "irish",
    "vietnamese", "korean", "american", "asian", "european",
}

# Hard dietary (validated + retry)
CANON_DIETARY_HARD: Set[str] = {"vegetarian", "vegan"}

# Soft dietary (preference only, no retry)
CANON_DIETARY_SOFT: Set[str] = {
    "kid-friendly", "healthy", "low-carb", "gluten-free",
    "dairy-free", "low-fat", "weeknight",
}

# Course tags for main dish validation
CANON_COURSE_MAIN: Set[str] = {"main-dish", "lunch"}

# Course tags that exclude from dinner selection
CANON_COURSE_EXCLUDE: Set[str] = {
    "desserts", "appetizers", "beverages", "condiments-etc",
    "sauces", "snacks", "salad-dressings",
}

# Minimal synonyms for user input normalization
TAG_SYNONYMS: dict[str, Set[str]] = {
    "vegetarian": {"vegetarian", "veggie", "meatless"},
    "vegan": {"vegan", "plant-based"},
    "kid-friendly": {"kid-friendly", "kid friendly", "for kids"},
    "low-carb": {"low-carb", "low carb", "keto"},
    "gluten-free": {"gluten-free", "gluten free"},
    "dairy-free": {"dairy-free", "dairy free"},
}


def normalize_tag(user_input: str) -> Optional[str]:
    """Normalize user input to canonical tag, or None if unrecognized."""
    lower = user_input.lower().strip()

    # Direct match
    all_canonical = CANON_CUISINES | CANON_DIETARY_HARD | CANON_DIETARY_SOFT
    if lower in all_canonical:
        return lower

    # Synonym lookup
    for canon, variants in TAG_SYNONYMS.items():
        if lower in variants:
            return canon

    return None
