"""
Recipe selection logic for meal planning.

Extracted from chatbot.py - handles LLM-based recipe selection and plan validation.
"""

import json
import time
import logging
from dataclasses import dataclass
from typing import Dict, List, Tuple, Optional, Callable, Set

from tag_canon import TAG_SYNONYMS, CANON_COURSE_MAIN, CANON_COURSE_EXCLUDE
from requirements_parser import DayRequirement

logger = logging.getLogger(__name__)

# Selection configuration
LLM_CANDIDATES_SHOWN = 20  # Show top 20 to LLM
STAGE2_MODEL = "claude-sonnet-4-5-20250929"  # Model for recipe selection


@dataclass
class ValidationFailure:
    """Records a validation failure for debugging and retry logic."""
    date: str
    recipe_id: int
    recipe_name: str
    requirement: str
    reason: str

    def __str__(self) -> str:
        return f"{self.date}: {self.recipe_name} - {self.reason}"


def select_recipes_with_llm(
    client,
    candidates_by_date: Dict[str, List],
    day_requirements: List[DayRequirement],
    recent_meals: List = None,
    validation_feedback: str = None,
    verbose: bool = False,
    verbose_callback: Optional[Callable[[str], None]] = None,
) -> List:
    """
    Use LLM to select ONE recipe per day from per-day candidate pools.

    Args:
        client: Anthropic client instance
        candidates_by_date: Dict mapping date -> list of candidate Recipe objects
        day_requirements: List of DayRequirement objects (in date order)
        recent_meals: Optional list of recent meal names for variety
        validation_feedback: Optional feedback from previous validation failure (for retry)
        verbose: Enable verbose output
        verbose_callback: Callback function for verbose output

    Returns:
        List of selected Recipe objects (in date order)
    """
    def _verbose_output(msg: str):
        if verbose and verbose_callback:
            verbose_callback(msg)

    # Build per-day sections for the prompt
    sections = []
    all_pools_empty = True
    dates = [req.date for req in day_requirements]

    for req in day_requirements:
        pool = candidates_by_date.get(req.date, [])
        if pool:
            all_pools_empty = False

        # Show top 20 candidates per day (from pool of 80)
        pool_text = "\n".join([
            f"  #{i+1} [ID:{r.id}] {r.name} [{', '.join(r.tags[:5])}]"
            for i, r in enumerate(pool[:20])
        ])

        # Format requirements for this day
        req_parts = []
        if req.cuisine:
            req_parts.append(f"Cuisine: {req.cuisine}")
        if req.dietary_hard:
            req_parts.append(f"Dietary (MUST have): {', '.join(req.dietary_hard)}")
        if req.dietary_soft:
            req_parts.append(f"Preferences: {', '.join(req.dietary_soft)}")
        if req.surprise:
            req_parts.append("Surprise me (any cuisine)")
        if not req_parts:
            req_parts.append("No specific requirements")

        sections.append(f"""
### {req.date}
Requirements: {' | '.join(req_parts)}
Candidates ({len(pool)} available, showing top 20):
{pool_text if pool_text else "  (no candidates available)"}
""")

    if all_pools_empty:
        # Fallback: return empty list if no candidates
        _verbose_output("      → ⚠️  All candidate pools empty, cannot select")
        return []

    recent_text = ""
    if recent_meals:
        recent_text = f"\nRecent meals (avoid if possible):\n" + "\n".join(f"- {m}" for m in recent_meals[:10])

    feedback_text = ""
    if validation_feedback:
        feedback_text = f"\n⚠️ PREVIOUS ATTEMPT FAILED - FIX THESE ISSUES:\n{validation_feedback}\n"

    # Build example date keys
    example_dates = dates[:3] if len(dates) >= 3 else dates

    prompt = f"""Select ONE recipe for EACH day below from that day's candidate pool.

CRITICAL: Return a JSON object with DATE KEYS, not an array.
{feedback_text}
{recent_text}

{chr(10).join(sections)}

RESPONSE FORMAT (exact structure required):
{{
  "{example_dates[0]}": <recipe_id>,
  "{example_dates[1] if len(example_dates) > 1 else 'YYYY-MM-DD'}": <recipe_id>,
  ...
}}

RULES:
1. Each day MUST get exactly ONE recipe from its own candidate pool
2. Recipe ID must be a valid ID from that day's candidates (shown in [ID:XXXXXX])
3. Cuisine/dietary requirements MUST be matched (they're already filtered in candidates)
4. Return ONLY the JSON object, no explanation
5. Use the exact date strings as keys"""

    # Log Stage 2 prompt summary
    logger.info(f"[STAGE2] Model: {STAGE2_MODEL}")
    logger.info(f"[STAGE2] Prompt summary: {len(dates)} days, date-keyed JSON required")
    for req in day_requirements:
        pool = candidates_by_date.get(req.date, [])
        logger.info(f"[STAGE2] {req.date}: showing {min(len(pool), LLM_CANDIDATES_SHOWN)}/{len(pool)} candidates to LLM")
    if validation_feedback:
        logger.info(f"[STAGE2] Retry feedback included: {len(validation_feedback)} chars")

    try:
        llm_start = time.time()
        response = client.messages.create(
            model=STAGE2_MODEL,
            max_tokens=500,
            messages=[{"role": "user", "content": prompt}]
        )
        llm_time = time.time() - llm_start
        logger.info(f"[STAGE2] LLM call completed in {llm_time:.3f}s")

        # Extract JSON from response
        content = response.content[0].text.strip()

        _verbose_output(f"      → LLM response: {content[:150]}...")

        # Remove markdown code blocks if present
        if content.startswith("```"):
            content = content.split("```")[1]
            if content.startswith("json"):
                content = content[4:]
        content = content.strip()

        # Extract JSON object if LLM added explanation text
        if not content.startswith("{"):
            start_idx = content.find("{")
            if start_idx != -1:
                content = content[start_idx:]
        if not content.endswith("}"):
            end_idx = content.rfind("}")
            if end_idx != -1:
                content = content[:end_idx + 1]

        selection_map = json.loads(content)  # {"2025-12-29": 489123, ...}
        logger.info(f"[LLM] Selection map: {selection_map}")

        _verbose_output(f"      → Parsed selection: {selection_map}")

        # Build result list in date order
        selected = []
        for req in day_requirements:
            recipe_id = str(selection_map.get(req.date, ""))
            pool = candidates_by_date.get(req.date, [])

            # Find recipe in this day's pool
            match = next((r for r in pool if str(r.id) == recipe_id), None)

            if match:
                selected.append(match)
                _verbose_output(f"      → {req.date}: Selected {match.name}")
            else:
                # Fallback: first valid recipe from pool
                if pool:
                    selected.append(pool[0])
                    logger.warning(f"Invalid ID {recipe_id} for {req.date}, using fallback: {pool[0].name}")
                    _verbose_output(f"      → {req.date}: ⚠️  Invalid ID {recipe_id}, fallback to {pool[0].name}")
                else:
                    logger.warning(f"No candidates for {req.date}, skipping")
                    _verbose_output(f"      → {req.date}: ⚠️  No candidates available")

        return selected

    except Exception as e:
        # Fallback: first recipe from each pool
        _verbose_output(f"LLM selection failed: {e}, using deterministic fallback")
        logger.warning(f"LLM selection failed: {e}")

        selected = []
        for req in day_requirements:
            pool = candidates_by_date.get(req.date, [])
            if pool:
                selected.append(pool[0])
        return selected


def validate_plan(
    selected_recipes: List,
    day_requirements: List[DayRequirement]
) -> Tuple[List[ValidationFailure], List[str]]:
    """
    Validate that selected recipes match day requirements.

    Args:
        selected_recipes: List of Recipe objects (in date order)
        day_requirements: List of DayRequirement objects (in date order)

    Returns:
        Tuple of (hard_failures, soft_warnings)
        - hard_failures: List of ValidationFailure that trigger retry
        - soft_warnings: List of warning strings for logging only
    """
    hard_failures = []
    soft_warnings = []

    for recipe, req in zip(selected_recipes, day_requirements):
        recipe_tags_set = set(recipe.tags) if recipe.tags else set()

        # Skip validation for surprise days
        if req.surprise:
            continue

        # HARD: Check cuisine requirement
        if req.cuisine:
            # Check direct match and synonyms
            cuisine_variants = TAG_SYNONYMS.get(req.cuisine, {req.cuisine})
            if not (recipe_tags_set & cuisine_variants) and req.cuisine not in recipe_tags_set:
                hard_failures.append(ValidationFailure(
                    date=req.date,
                    recipe_id=recipe.id,
                    recipe_name=recipe.name,
                    requirement=f"cuisine={req.cuisine}",
                    reason=f"Tags {list(recipe_tags_set)[:5]} missing '{req.cuisine}'"
                ))

        # HARD: Check hard dietary requirements (vegetarian, vegan)
        for diet in req.dietary_hard:
            diet_variants = TAG_SYNONYMS.get(diet, {diet})
            if not (recipe_tags_set & diet_variants) and diet not in recipe_tags_set:
                hard_failures.append(ValidationFailure(
                    date=req.date,
                    recipe_id=recipe.id,
                    recipe_name=recipe.name,
                    requirement=f"dietary_hard={diet}",
                    reason=f"Missing hard constraint '{diet}'"
                ))

        # SOFT: Check soft dietary requirements (kid-friendly, healthy, etc.)
        for diet in req.dietary_soft:
            diet_variants = TAG_SYNONYMS.get(diet, {diet})
            if not (recipe_tags_set & diet_variants) and diet not in recipe_tags_set:
                soft_warnings.append(
                    f"[SOFT] {req.date}: {recipe.name} missing preference '{diet}'"
                )

        # HARD: Dinner must be main-dish (reject desserts/drinks)
        has_main_dish = bool(recipe_tags_set & CANON_COURSE_MAIN)
        has_excluded = bool(recipe_tags_set & CANON_COURSE_EXCLUDE)

        if not has_main_dish and has_excluded:
            hard_failures.append(ValidationFailure(
                date=req.date,
                recipe_id=recipe.id,
                recipe_name=recipe.name,
                requirement="main-dish",
                reason=f"Recipe has {recipe_tags_set & CANON_COURSE_EXCLUDE}, not suitable for dinner"
            ))
        elif not has_main_dish:
            soft_warnings.append(
                f"[SOFT] {req.date}: {recipe.name} missing 'main-dish' tag (may still be OK)"
            )

        # LOG: Unhandled constraints
        if req.unhandled:
            soft_warnings.append(
                f"[UNHANDLED] {req.date}: Ignored constraints: {req.unhandled}"
            )

    # Log all issues
    if hard_failures:
        logger.warning(f"Plan validation: {len(hard_failures)} HARD failures")
        for f in hard_failures:
            logger.warning(f"  {f}")

    if soft_warnings:
        logger.info(f"Plan validation: {len(soft_warnings)} soft warnings")
        for w in soft_warnings:
            logger.info(f"  {w}")

    return hard_failures, soft_warnings
