"""
Protein cooking profiles for instruction modification.

This knowledge base provides safe cooking times, temperatures, and doneness cues
for common proteins. Used to guide LLM-generated step modifications when
ingredients are swapped.

v1 Scope: Only proteins with well-defined cooking profiles.
"""

from dataclasses import dataclass
from typing import Optional


@dataclass
class CookProfile:
    """Cooking profile for a protein."""
    min_time: int  # minutes
    max_time: int  # minutes
    method: str  # sauté, bake, sear, etc.
    cue: str  # doneness cue (visual/temp)
    safe_temp: Optional[int]  # minimum safe internal temp (°F), None for seafood w/o temp requirement


# v1 Knowledge Base: Common proteins only
PROTEIN_COOK_PROFILES: dict[str, CookProfile] = {
    # Poultry
    "chicken_breast": CookProfile(
        min_time=6, max_time=12, method="sauté",
        cue="no longer pink, 165°F internal", safe_temp=165
    ),
    "chicken_thigh": CookProfile(
        min_time=8, max_time=14, method="sauté",
        cue="no longer pink, 165°F internal", safe_temp=165
    ),
    "chicken": CookProfile(  # Generic fallback
        min_time=6, max_time=12, method="sauté",
        cue="no longer pink, 165°F internal", safe_temp=165
    ),
    "ground_chicken": CookProfile(
        min_time=6, max_time=10, method="sauté",
        cue="no longer pink, 165°F internal", safe_temp=165
    ),
    "turkey_breast": CookProfile(
        min_time=6, max_time=12, method="sauté",
        cue="no longer pink, 165°F internal", safe_temp=165
    ),
    "ground_turkey": CookProfile(
        min_time=8, max_time=12, method="sauté",
        cue="no longer pink, 165°F internal", safe_temp=165
    ),

    # Beef
    "ground_beef": CookProfile(
        min_time=8, max_time=12, method="sauté",
        cue="browned throughout, 160°F internal", safe_temp=160
    ),
    "beef": CookProfile(  # Generic fallback
        min_time=8, max_time=12, method="sauté",
        cue="browned throughout, 160°F internal", safe_temp=160
    ),
    "steak": CookProfile(
        min_time=4, max_time=8, method="sear",
        cue="to desired doneness, minimum 145°F", safe_temp=145
    ),
    "beef_steak": CookProfile(
        min_time=4, max_time=8, method="sear",
        cue="to desired doneness, minimum 145°F", safe_temp=145
    ),

    # Pork
    "ground_pork": CookProfile(
        min_time=8, max_time=12, method="sauté",
        cue="no longer pink, 160°F internal", safe_temp=160
    ),
    "pork": CookProfile(  # Generic fallback
        min_time=8, max_time=12, method="sauté",
        cue="no longer pink, 145°F internal", safe_temp=145
    ),
    "pork_chop": CookProfile(
        min_time=6, max_time=10, method="sear",
        cue="145°F internal", safe_temp=145
    ),
    "pork_tenderloin": CookProfile(
        min_time=15, max_time=25, method="roast",
        cue="145°F internal", safe_temp=145
    ),
    "bacon": CookProfile(
        min_time=4, max_time=8, method="sauté",
        cue="crispy", safe_temp=None
    ),
    "sausage": CookProfile(
        min_time=8, max_time=12, method="sauté",
        cue="browned and cooked through, 160°F internal", safe_temp=160
    ),

    # Seafood
    "shrimp": CookProfile(
        min_time=2, max_time=4, method="sauté",
        cue="pink and curled, opaque throughout", safe_temp=None
    ),
    "salmon": CookProfile(
        min_time=10, max_time=15, method="bake",
        cue="flakes easily with fork, 145°F internal", safe_temp=145
    ),
    "cod": CookProfile(
        min_time=8, max_time=12, method="bake",
        cue="flakes easily, opaque throughout", safe_temp=None
    ),
    "tilapia": CookProfile(
        min_time=6, max_time=10, method="bake",
        cue="flakes easily, opaque throughout", safe_temp=None
    ),
    "tuna": CookProfile(
        min_time=2, max_time=4, method="sear",
        cue="seared outside, pink inside (or to preference)", safe_temp=None
    ),
    "fish": CookProfile(  # Generic fallback
        min_time=8, max_time=12, method="bake",
        cue="flakes easily, opaque throughout", safe_temp=145
    ),
    "scallops": CookProfile(
        min_time=2, max_time=4, method="sear",
        cue="golden brown crust, opaque", safe_temp=None
    ),

    # Tofu/Plant-based
    "tofu": CookProfile(
        min_time=8, max_time=12, method="sauté",
        cue="golden brown on all sides", safe_temp=None
    ),
    "tempeh": CookProfile(
        min_time=8, max_time=12, method="sauté",
        cue="golden brown on all sides", safe_temp=None
    ),
}


def normalize_protein_name(ingredient: str) -> str:
    """
    Normalize an ingredient string to match a profile key.

    Examples:
        "chicken breast" -> "chicken_breast"
        "boneless chicken thighs" -> "chicken_thigh"
        "1 lb ground beef" -> "ground_beef"
        "large shrimp, peeled" -> "shrimp"
    """
    lower = ingredient.lower()

    # Remove common prefixes (quantities, adjectives)
    prefixes_to_remove = [
        "boneless", "skinless", "fresh", "frozen", "raw", "cooked",
        "lean", "extra lean", "organic", "free-range", "wild-caught",
        "farm-raised", "large", "medium", "small", "jumbo", "peeled",
        "deveined", "cubed", "diced", "sliced", "minced", "chopped",
    ]
    for prefix in prefixes_to_remove:
        lower = lower.replace(prefix, "")

    # Remove quantities (e.g., "1 lb", "2 cups")
    import re
    lower = re.sub(r'\d+\s*(lb|lbs|pound|pounds|oz|ounce|ounces|cup|cups|g|kg)?\s*', '', lower)

    # Remove trailing qualifiers
    lower = re.sub(r',.*$', '', lower)  # Everything after comma
    lower = lower.strip()

    # Map common variations to canonical names
    mappings = {
        "chicken breast": "chicken_breast",
        "chicken breasts": "chicken_breast",
        "chicken thigh": "chicken_thigh",
        "chicken thighs": "chicken_thigh",
        "ground chicken": "ground_chicken",
        "ground turkey": "ground_turkey",
        "turkey breast": "turkey_breast",
        "ground beef": "ground_beef",
        "ground pork": "ground_pork",
        "pork chop": "pork_chop",
        "pork chops": "pork_chop",
        "pork tenderloin": "pork_tenderloin",
        "beef steak": "beef_steak",
        "sirloin": "steak",
        "ribeye": "steak",
        "filet mignon": "steak",
        "ny strip": "steak",
        "salmon fillet": "salmon",
        "salmon fillets": "salmon",
        "cod fillet": "cod",
        "cod fillets": "cod",
        "tilapia fillet": "tilapia",
        "tilapia fillets": "tilapia",
        "tuna steak": "tuna",
    }

    # Check exact mappings first
    if lower in mappings:
        return mappings[lower]

    # Check if any mapping key is contained in the ingredient
    for key, value in mappings.items():
        if key in lower:
            return value

    # Check if any profile key is contained in the ingredient
    for profile_key in PROTEIN_COOK_PROFILES.keys():
        canonical = profile_key.replace("_", " ")
        if canonical in lower or profile_key in lower.replace(" ", "_"):
            return profile_key

    # Final fallback: try simple underscore conversion
    simple = lower.replace(" ", "_")
    if simple in PROTEIN_COOK_PROFILES:
        return simple

    return lower.replace(" ", "_")


def get_cook_profile(ingredient: str) -> Optional[CookProfile]:
    """
    Get the cooking profile for an ingredient.

    Returns None if ingredient is not a known protein.
    """
    normalized = normalize_protein_name(ingredient)
    return PROTEIN_COOK_PROFILES.get(normalized)


def has_cook_profile(ingredient: str) -> bool:
    """Check if we have a cooking profile for this ingredient."""
    return get_cook_profile(ingredient) is not None


# Keywords that indicate cooking method changes (should refuse instruction modification)
METHOD_CHANGE_KEYWORDS = frozenset({
    "air fry", "air fryer", "airfry",
    "slow cook", "slow cooker", "crockpot", "crock pot",
    "instant pot", "instantpot", "pressure cook", "pressure cooker",
    "sous vide",
    "microwave",
    "raw", "no cook", "uncooked",
    "grill", "grilled",  # Different equipment
    "smoke", "smoked", "smoker",  # Different equipment
    "deep fry", "deep fried",  # Safety concerns
})


def should_refuse_instruction_mod(user_request: str) -> bool:
    """
    Check if the user request involves cooking method changes
    that we should refuse to modify instructions for.
    """
    lower = user_request.lower()
    return any(kw in lower for kw in METHOD_CHANGE_KEYWORDS)
