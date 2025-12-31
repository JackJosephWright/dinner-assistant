"""
Swap matching logic for meal planning.

Extracted from chatbot.py - handles backup recipe matching and selection.
"""

import re
import json
import logging
from typing import List, Optional, Callable

logger = logging.getLogger(__name__)


def llm_semantic_match(
    client,
    requirements: str,
    category: str,
    verbose: bool = False,
    verbose_callback: Optional[Callable[[str], None]] = None,
) -> bool:
    """
    Use LLM to determine if requirements semantically match a category.

    This is a fallback for edge cases that algorithmic matching misses.
    Uses Claude Haiku for fast, cheap semantic analysis (~100ms, $0.003).

    Args:
        client: Anthropic client instance
        requirements: User's swap request
        category: Backup category key
        verbose: Enable verbose output
        verbose_callback: Callback function for verbose output

    Returns:
        True if LLM determines the requirements match the category
    """
    def _verbose_output(msg: str):
        if verbose and verbose_callback:
            verbose_callback(msg)

    try:
        prompt = f"""Does the user's request match the recipe category?

User request: "{requirements}"
Recipe category: "{category}"

Consider:
- Does the request want recipes from this category?
- Are there negative filters that exclude this category?
- Would recipes in this category satisfy the request?

Answer ONLY with: YES or NO"""

        response = client.messages.create(
            model="claude-3-5-haiku-20241022",
            max_tokens=5,
            messages=[{"role": "user", "content": prompt}]
        )

        answer = response.content[0].text.strip().upper()
        return "YES" in answer

    except Exception as e:
        _verbose_output(f"      → LLM semantic match failed: {e}, assuming no match")
        return False


def select_backup_options(
    client,
    backups: List,
    num_options: int = 3,
    verbose: bool = False,
    verbose_callback: Optional[Callable[[str], None]] = None,
) -> List:
    """
    Select the most interesting backup recipes to show user.

    Uses LLM to pick varied, appealing options from the backup queue.

    Args:
        client: Anthropic client instance
        backups: List of Recipe objects from backup queue
        num_options: Number of options to return (default 3)
        verbose: Enable verbose output
        verbose_callback: Callback function for verbose output

    Returns:
        List of selected Recipe objects
    """
    def _verbose_output(msg: str):
        if verbose and verbose_callback:
            verbose_callback(msg)

    if len(backups) <= num_options:
        return backups

    try:
        # Format backups for LLM
        backups_text = []
        for i, r in enumerate(backups, 1):
            ing_count = len(r.get_ingredients()) if r.has_structured_ingredients() else len(r.ingredients_raw)
            est_time = r.tags[0] if r.tags and 'min' in str(r.tags[0]) else 'unknown time'
            backups_text.append(
                f"{i}. {r.name}\n"
                f"   ID: {r.id}\n"
                f"   {ing_count} ingredients, {est_time}\n"
                f"   Tags: {', '.join(r.tags[:3])}"
            )

        prompt = f"""Select the {num_options} most interesting and varied recipes from this list to show the user.

Choose recipes that:
- Offer variety (different cuisines, cooking styles)
- Are appealing and practical for home cooking
- Represent the diversity of options available

Recipes ({len(backups)} total):
{chr(10).join(backups_text)}

Return ONLY a JSON array of {num_options} Recipe IDs (the ID numbers shown above).
Example: ["{backups[0].id}", "{backups[1].id}", "{backups[2].id}"]"""

        response = client.messages.create(
            model="claude-3-5-haiku-20241022",
            max_tokens=100,
            messages=[{"role": "user", "content": prompt}]
        )

        content = response.content[0].text.strip()

        # Extract JSON
        if not content.startswith("["):
            start_idx = content.find("[")
            if start_idx != -1:
                content = content[start_idx:]
        if not content.endswith("]"):
            end_idx = content.rfind("]")
            if end_idx != -1:
                content = content[:end_idx + 1]

        selected_ids = json.loads(content)
        selected_ids_str = [str(id) for id in selected_ids]

        # Match IDs to recipes
        selected = [r for r in backups if str(r.id) in selected_ids_str][:num_options]

        # If LLM failed, just return first N
        if len(selected) < num_options:
            return backups[:num_options]

        return selected

    except Exception as e:
        _verbose_output(f"      → LLM selection failed: {e}, using first {num_options}")
        return backups[:num_options]


def check_backup_match(
    client,
    requirements: str,
    category: str,
    verbose: bool = False,
    verbose_callback: Optional[Callable[[str], None]] = None,
) -> str:
    """
    Check if user requirements match a backup category using hybrid matching.

    Uses two-tier approach:
    1. Fast algorithmic checks (handles 80-90% of cases)
    2. LLM semantic fallback for edge cases (handles remaining 10-20%)

    Args:
        client: Anthropic client instance
        requirements: User's swap request (e.g., "different chicken dish")
        category: Backup category key (e.g., "chicken")
        verbose: Enable verbose output
        verbose_callback: Callback function for verbose output

    Returns:
        "confirm" - Vague request, show options to user
        "auto" - Specific request, auto-swap from backups
        "no_match" - Requirements don't match this category
    """
    def _verbose_output(msg: str):
        if verbose and verbose_callback:
            verbose_callback(msg)

    requirements_lower = requirements.lower()
    category_lower = category.lower()

    # Tier 1: Fast algorithmic checks

    # Remove common exclusion patterns before checking for specific foods
    # "no X", "without X", "not X" are exclusions, not requirements
    requirements_without_exclusions = requirements_lower
    # Match "no/without/not" followed by 1-3 words (handles "no beef", "no corned beef", etc.)
    exclusion_patterns = [
        r'\bno\s+(?:\w+\s+){0,2}\w+',  # "no X", "no X Y", "no X Y Z"
        r'\bwithout\s+(?:\w+\s+){0,2}\w+',
        r'\bnot\s+(?:\w+\s+){0,2}\w+'
    ]
    for pattern in exclusion_patterns:
        requirements_without_exclusions = re.sub(pattern, '', requirements_without_exclusions)

    # First, check for specific food terms (takes precedence over vague terms)
    # This ensures "different chicken" auto-swaps instead of asking for confirmation
    specific_food_terms = ["chicken", "beef", "pork", "fish", "pasta", "vegetarian", "vegan", "seafood"]
    has_specific_food = any(food in requirements_without_exclusions for food in specific_food_terms)

    # Direct category match → auto-swap
    if category_lower in requirements_lower:
        _verbose_output(f"      → Matched '{category}' via direct match → AUTO mode")
        return "auto"

    # Check for related terms → auto-swap
    related_terms = {
        "chicken": ["poultry", "bird"],
        "beef": ["steak", "meat", "burger"],
        "pasta": ["noodle", "spaghetti", "penne", "linguine"],
        "fish": ["seafood", "salmon", "tilapia", "tuna"],
        "vegetarian": ["veggie", "meatless", "plant-based"],
    }

    for term in related_terms.get(category_lower, []):
        if term in requirements_lower:
            _verbose_output(f"      → Matched '{category}' via related term '{term}' → AUTO mode")
            return "auto"

    # Check for vague terms that match any category → need confirmation
    # But only if there's NO specific food mentioned
    vague_terms = ["something", "anything", "other", "else"]
    if any(term in requirements_lower for term in vague_terms) and not has_specific_food:
        _verbose_output(f"      → Matched '{category}' via vague terms → CONFIRM mode")
        return "confirm"

    # "different" alone is vague, but "different chicken" is specific
    # Only trigger confirm if "different" exists AND no specific food AND category doesn't match
    if "different" in requirements_lower and not has_specific_food and category_lower not in requirements_lower:
        _verbose_output(f"      → Matched '{category}' via 'different' (vague) → CONFIRM mode")
        return "confirm"

    # Check for modifier words indicating same category → auto-swap
    modifiers = ["swap", "replace", "change"]
    has_modifier = any(mod in requirements_lower for mod in modifiers)
    if has_modifier and category_lower in requirements_lower:
        _verbose_output(f"      → Matched '{category}' via modifier → AUTO mode")
        return "auto"

    # Tier 2: LLM semantic fallback for edge cases → auto-swap
    if llm_semantic_match(client, requirements, category, verbose, verbose_callback):
        _verbose_output(f"      → Matched '{category}' via LLM semantic analysis → AUTO mode")
        return "auto"

    _verbose_output(f"      → No match for '{category}'")
    return "no_match"
