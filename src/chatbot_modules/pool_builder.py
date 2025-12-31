"""
Pool builder for meal planning candidate generation.

Extracted from chatbot.py - builds per-day candidate pools based on parsed requirements.
"""

import time
import logging
from typing import Dict, List, Tuple, Set, Optional, Callable

from tag_canon import CANON_COURSE_EXCLUDE
from requirements_parser import DayRequirement

logger = logging.getLogger(__name__)

# Pool configuration
POOL_SIZE = 80  # Fetch 80 candidates per day


def build_per_day_pools(
    db,
    day_requirements: List[DayRequirement],
    recent_names: List[str],
    exclude_allergens: List[str],
    excluded_ids_by_date: Dict[str, Set[int]] = None,
    user_id: str = None,
    week_of: str = None,
    verbose: bool = False,
    verbose_callback: Optional[Callable[[str], None]] = None,
) -> Tuple[Dict[str, List], Dict[str, float]]:
    """
    Build per-day candidate pools based on parsed requirements.

    Uses seeded random sampling for reproducible results within a week
    while providing variety across weeks (Phase 1 latency fix).

    Args:
        db: DatabaseInterface instance for recipe queries
        day_requirements: List of DayRequirement objects
        recent_names: Recently used recipe names (for freshness penalty)
        exclude_allergens: Allergens to filter out
        excluded_ids_by_date: Optional dict of recipe IDs to exclude per date (for retry)
        user_id: User identifier for seed generation
        week_of: Week start date for seed generation
        verbose: Enable verbose output
        verbose_callback: Callback function for verbose output

    Returns:
        Tuple of (candidates_by_date dict, timing_by_date dict)
    """
    candidates_by_date: Dict[str, List] = {}
    timing_by_date: Dict[str, float] = {}
    excluded_ids_by_date = excluded_ids_by_date or {}

    # Generate stable seed for this user + week (Phase 1: seeded sampling)
    seed_base = hash(f"{user_id or 'default'}_{week_of or 'unknown'}") % (2**31)

    logger.info(f"[POOL-BUILD] Starting per-day pool construction (POOL_SIZE={POOL_SIZE}, seed_base={seed_base})")

    for day_idx, req in enumerate(day_requirements):
        pool_start = time.time()

        # Build tag requirements
        include_tags = ["main-dish"]  # Always require main dish for dinner
        exclude_tags = list(CANON_COURSE_EXCLUDE)  # Exclude desserts, beverages, etc.

        # Add cuisine requirement
        if req.cuisine:
            include_tags.append(req.cuisine)

        # Add hard dietary constraints to query
        for diet in req.dietary_hard:
            include_tags.append(diet)

        # Get excluded IDs for this date (from previous retry failures)
        exclude_ids = list(excluded_ids_by_date.get(req.date, set()))

        # Per-day seed variation (same week, different days get different samples)
        day_seed = seed_base + day_idx

        # Build search query from unhandled constraints (user-specified recipe keywords)
        search_query = None
        if req.unhandled:
            search_query = " ".join(req.unhandled)

        # Query database using seeded sampling (Phase 1 latency fix)
        pool = db.search_recipes_sampled(
            include_tags=include_tags,
            exclude_tags=exclude_tags,
            exclude_ids=[str(id) for id in exclude_ids] if exclude_ids else None,
            query=search_query,
            limit=POOL_SIZE,
            seed=day_seed,
        )

        # Apply allergen filtering using structured ingredients
        if exclude_allergens:
            pool = [
                r for r in pool
                if r.has_structured_ingredients()
                and not any(r.has_allergen(a) for a in exclude_allergens)
            ]

        # Apply freshness penalty: deprioritize recently used recipes
        freshness_applied = False
        if recent_names:
            recent_set = set(recent_names)
            fresh = [r for r in pool if r.name not in recent_set]
            stale = [r for r in pool if r.name in recent_set]
            if stale:
                freshness_applied = True
            pool = fresh + stale  # Fresh first, then stale as backup

        candidates_by_date[req.date] = pool
        pool_time = time.time() - pool_start
        timing_by_date[req.date] = pool_time

        # Post-processing logging (query logging handled by search_recipes_sampled)
        if freshness_applied:
            logger.info(f"[POOL-POST] {req.date}: freshness_penalty_applied=True")
        if exclude_ids:
            logger.info(f"[POOL-POST] {req.date}: excluded_ids={len(exclude_ids)}")

        if verbose and verbose_callback:
            tags_str = ", ".join(include_tags)
            verbose_callback(f"      → {req.date}: {len(pool)} candidates ({tags_str})")

    total_candidates = sum(len(p) for p in candidates_by_date.values())
    logger.info(f"[POOL-BUILD] Complete: {total_candidates} total candidates across {len(day_requirements)} days")

    return candidates_by_date, timing_by_date
