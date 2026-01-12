"""
Tool handler functions for the meal planning chatbot.

Extracted from chatbot.py - contains handler functions for each tool.
Each handler takes (chatbot, tool_input) and returns a string result.
"""

import time
import json
import logging
from datetime import datetime, timedelta
from typing import Dict, Any, Set, List, Tuple
from concurrent.futures import ThreadPoolExecutor, as_completed

from data.models import PlannedMeal, MealPlan, Recipe
from requirements_parser import parse_requirements
from chatbot_modules.pool_builder import build_per_day_pools, build_per_day_pools_v2
from chatbot_modules.recipe_selector import select_recipes_with_llm, validate_plan
from chatbot_modules.swap_matcher import check_backup_match, select_backup_options

logger = logging.getLogger(__name__)

# Configuration
MAX_RETRIES = 2
USE_LLM_QUERY_BUILDER = True  # Feature flag for new approach
USE_GENERATE_FUZZY_MATCH = True  # Option F: ChatGPT-like speed with real recipes


def llm_build_query_params(
    client,
    user_message: str,
    dates: List[str],
) -> Dict[str, Dict]:
    """
    Use LLM to convert user request directly into DB query parameters.

    Replaces the algorithmic parse_requirements() approach with a single
    Haiku call that understands natural language and maps to available tags.

    Returns: {
        "2026-01-14": {"include_tags": ["main-dish", "30-minutes-or-less"], "query": null},
        "2026-01-12": {"include_tags": ["main-dish"], "query": "peruvian chicken"},
    }
    """
    import json

    # Format dates with day names for context - create explicit mapping
    from datetime import datetime as dt
    date_mapping = []
    for d in dates:
        day_name = dt.fromisoformat(d).strftime("%A")
        date_mapping.append(f"{day_name} = {d}")
    date_mapping_str = "\n".join(date_mapping)

    # Build default entries for ALL dates to ensure Haiku returns all of them
    default_entries = ",\n  ".join([f'"{d}": {{"include_tags": ["main-dish"], "query": null}}' for d in dates])

    prompt = f'''Parse this meal planning request and return database query parameters.

User request: "{user_message}"

CRITICAL - Day-to-Date Mapping (READ CAREFULLY):
{date_mapping_str}

When user mentions "Sunday" → use date {dates[0] if dates else ""}
When user mentions "Tuesday" → find Tuesday in the mapping above

Tags to use:
- "quick"/"fast"/"sports night" → include_tags: ["main-dish", "30-minutes-or-less"]
- "peruvian chicken" → include_tags: ["main-dish", "peruvian", "chicken"], query: "peruvian chicken"
- No constraints mentioned → include_tags: ["main-dish"], query: null

Return JSON with EXACTLY these {len(dates)} dates: {", ".join(dates)}

Example output format:
{{
  "{dates[0]}": {{"include_tags": ["main-dish"], "query": null}},
  ...one entry for each date...
}}'''

    logger.info(f"[LLM-QUERY] Calling Haiku to build query params for {len(dates)} days")
    logger.info(f"[LLM-QUERY] User message: {user_message}")
    logger.info(f"[LLM-QUERY] Date mapping: {date_mapping_str}")
    start_time = time.time()

    response = client.messages.create(
        model="claude-3-5-haiku-20241022",
        max_tokens=500,
        messages=[{"role": "user", "content": prompt}]
    )

    elapsed = time.time() - start_time
    logger.info(f"[LLM-QUERY] Haiku response in {elapsed:.3f}s")

    # Parse JSON response
    content = response.content[0].text.strip()
    # Handle potential markdown code blocks
    if content.startswith("```"):
        content = content.split("```")[1]
        if content.startswith("json"):
            content = content[4:]
        content = content.strip()

    result = json.loads(content)

    # Ensure ALL dates have entries - fill in missing ones with defaults
    default_params = {"include_tags": ["main-dish"], "query": None}
    for d in dates:
        if d not in result:
            logger.warning(f"[LLM-QUERY] Missing date {d} in Haiku response - adding default")
            result[d] = default_params.copy()

    # Log the parsed params
    for date, params in result.items():
        logger.info(f"[LLM-QUERY] {date}: include_tags={params.get('include_tags')}, query={params.get('query')}")

    return result


def generate_meal_names(
    client,
    user_message: str,
    dates: List[str],
    recent_meals: List[str] = None,
    user_profile: Any = None,
    favorites: List[Dict] = None,
) -> Dict[str, str]:
    """
    Use Haiku to generate creative meal names (like ChatGPT).

    This is fast (~600ms) because it just generates text without DB lookup.
    Returns: {"2026-01-12": "Peruvian Roasted Chicken", ...}
    """
    # Format dates with day names
    date_mapping = "\n".join([
        f"{datetime.fromisoformat(d).strftime('%A')} = {d}"
        for d in dates
    ])

    # Add recent meals context to avoid repetition
    recent_meals_context = ""
    if recent_meals:
        recent_list = ", ".join(recent_meals[:10])  # Limit to 10 most recent
        recent_meals_context = f"""
IMPORTANT - Avoid these recently eaten meals:
{recent_list}

Suggest DIFFERENT dishes to provide variety."""

    # Add user preferences context
    preferences_context = ""
    if user_profile:
        prefs = []
        if user_profile.favorite_cuisines:
            prefs.append(f"- Favorite cuisines: {', '.join(user_profile.favorite_cuisines)}")
        if user_profile.dietary_restrictions:
            prefs.append(f"- Dietary restrictions: {', '.join(user_profile.dietary_restrictions)}")
        if user_profile.allergens:
            prefs.append(f"- MUST AVOID (allergens): {', '.join(user_profile.allergens)}")
        if user_profile.disliked_ingredients:
            prefs.append(f"- Avoid if possible: {', '.join(user_profile.disliked_ingredients)}")
        if user_profile.preferred_proteins:
            prefs.append(f"- Preferred proteins: {', '.join(user_profile.preferred_proteins)}")
        if user_profile.spice_tolerance and user_profile.spice_tolerance != "medium":
            prefs.append(f"- Spice preference: {user_profile.spice_tolerance}")
        if user_profile.health_focus:
            prefs.append(f"- Health focus: {user_profile.health_focus}")

        if prefs:
            preferences_context = "\n\nUser preferences:\n" + "\n".join(prefs)

    # Add favorites context
    favorites_context = ""
    if favorites:
        fav_names = [f["recipe_name"] for f in favorites[:10]]
        favorites_context = f"""

User's favorite recipes (starred or highly rated):
{', '.join(fav_names)}

You MAY include 1-2 favorites in the plan if they fit the request naturally.
Do NOT force favorites if the user has specific requirements (e.g., "all Thai food")."""

    prompt = f'''Generate a thoughtful meal plan for this request:

User request: "{user_message}"

Dates to plan:
{date_mapping}
{recent_meals_context}{preferences_context}{favorites_context}

Create an elegant, varied meal plan. Consider:
- Cuisine authenticity (if Italian requested, suggest real Italian dishes)
- Variety across the week (different proteins, cooking styles, cuisines)
- User's specific requirements (quick = under 30 min, specific dishes mentioned)
- Balance of complexity (mix easy weeknight meals with more involved weekend dishes)

Return ONLY a JSON object mapping each date to a descriptive meal name.
Example: {{"2026-01-12": "Honey Garlic Chicken", "2026-01-13": "Creamy Tuscan Pasta"}}

Return exactly {len(dates)} entries, one per date.'''

    logger.info(f"[GENERATE] Calling Haiku to generate {len(dates)} meal names")
    start_time = time.time()

    response = client.messages.create(
        model="claude-3-5-haiku-20241022",
        max_tokens=500,
        messages=[{"role": "user", "content": prompt}]
    )

    elapsed = time.time() - start_time
    logger.info(f"[GENERATE] Haiku response in {elapsed*1000:.0f}ms")

    # Parse JSON response
    content = response.content[0].text.strip()
    # Handle potential markdown code blocks
    if content.startswith("```"):
        content = content.split("```")[1]
        if content.startswith("json"):
            content = content[4:]
        content = content.strip()

    result = json.loads(content)

    # Ensure all dates have entries
    for d in dates:
        if d not in result:
            logger.warning(f"[GENERATE] Missing date {d}, adding default")
            result[d] = "Dinner"

    for date, name in result.items():
        logger.info(f"[GENERATE] {date}: {name}")

    return result


def parallel_fuzzy_match(
    db,
    meal_names: Dict[str, str],
) -> Dict[str, Recipe]:
    """
    Fuzzy match meal names to real recipes in parallel.

    Uses ThreadPoolExecutor to run all searches simultaneously (~500ms total).
    Returns: {"2026-01-12": Recipe(...), ...}
    """
    # Common modifiers/adjectives that don't help find recipes
    SKIP_WORDS = {
        # Quality adjectives
        "classic", "traditional", "authentic", "homemade", "easy", "quick",
        "simple", "delicious", "amazing", "best", "ultimate", "perfect",
        "fresh", "creamy", "crispy", "tender", "juicy", "flavorful",
        "hearty", "light", "healthy", "gourmet", "rustic", "elegant",
        # Cooking methods (usually not in recipe names)
        "slow", "simmered", "braised", "roasted", "grilled", "baked",
        "fried", "seared", "steamed", "poached", "sauteed", "pan",
        # Time/style words
        "minute", "minutes", "hour", "hours", "day", "style", "inspired",
        # Connectors
        "with", "and", "the", "for", "from", "over", "topped",
    }

    def extract_food_keywords(name: str) -> List[str]:
        """Extract food-related keywords from a meal name."""
        words = name.lower().replace("-", " ").split()
        # Filter out short words, numbers, and common modifiers
        keywords = [
            w for w in words
            if len(w) > 2 and not w.isdigit() and w not in SKIP_WORDS
        ]
        # Take up to 4 most likely food words (increased from 3)
        return keywords[:4] if keywords else ["dinner"]

    def score_match(recipe_name: str, keywords: List[str]) -> int:
        """Score how well a recipe matches the keywords (higher = better)."""
        name_lower = recipe_name.lower()
        score = 0
        for kw in keywords:
            if kw in name_lower:
                score += 10  # Exact word match
            elif any(kw in word for word in name_lower.split()):
                score += 5   # Partial match
        return score

    def best_match(results: List[Recipe], keywords: List[str]) -> Recipe:
        """Pick the best matching recipe from results based on keyword overlap."""
        if not results:
            return None
        if len(results) == 1:
            return results[0]
        # Score each result and pick the best
        scored = [(score_match(r.name, keywords), r) for r in results]
        scored.sort(key=lambda x: x[0], reverse=True)
        return scored[0][1]

    def match_one(date: str, name: str) -> Tuple[str, Recipe, str]:
        """Match a single meal name to a recipe. Returns (date, recipe, matched_name)."""
        match_start = time.time()

        # Extract food keywords for searching
        keywords = extract_food_keywords(name)
        query = " ".join(keywords)

        # Search with keywords, get more results to pick the best
        results = db.search_recipes(query=query, limit=15)
        if results:
            best = best_match(results, keywords)
            elapsed = (time.time() - match_start) * 1000
            logger.info(f"[MATCH] {date}: '{name}' → '{best.name}' ({elapsed:.0f}ms, keywords='{query}')")
            return (date, best, best.name)

        # Try with fewer keywords if no match - try multiple reduction strategies
        # Only accept matches with at least 2 words to avoid weak single-word matches
        if len(keywords) > 1:
            # Strategy 1: Try dropping from the end (keep beginning), min 2 words
            for i in range(len(keywords) - 1, 1, -1):  # Stop at 2, not 1
                query = " ".join(keywords[:i])
                results = db.search_recipes(query=query, limit=15)
                if results:
                    best = best_match(results, keywords)
                    elapsed = (time.time() - match_start) * 1000
                    logger.info(f"[MATCH] {date}: '{name}' → '{best.name}' ({elapsed:.0f}ms, reduced='{query}')")
                    return (date, best, best.name)

            # Strategy 2: Try dropping from the beginning (keep end - often more specific)
            for i in range(1, len(keywords) - 1):  # Keep at least 2 words
                query = " ".join(keywords[i:])
                results = db.search_recipes(query=query, limit=15)
                if results:
                    best = best_match(results, keywords)
                    elapsed = (time.time() - match_start) * 1000
                    logger.info(f"[MATCH] {date}: '{name}' → '{best.name}' ({elapsed:.0f}ms, tail='{query}')")
                    return (date, best, best.name)

            # Strategy 3: Try pairs of consecutive keywords
            for i in range(len(keywords) - 1):
                query = " ".join(keywords[i:i+2])
                results = db.search_recipes(query=query, limit=15)
                if results:
                    best = best_match(results, keywords)
                    elapsed = (time.time() - match_start) * 1000
                    logger.info(f"[MATCH] {date}: '{name}' → '{best.name}' ({elapsed:.0f}ms, pair='{query}')")
                    return (date, best, best.name)

            # Strategy 4: Try each keyword individually as last resort (but not first keyword which is often noise)
            for i in range(1, len(keywords)):
                query = keywords[i]
                results = db.search_recipes(query=query, limit=15)
                if results:
                    best = best_match(results, keywords)
                    elapsed = (time.time() - match_start) * 1000
                    logger.info(f"[MATCH] {date}: '{name}' → '{best.name}' ({elapsed:.0f}ms, single='{query}')")
                    return (date, best, best.name)

        # Fallback to generic dinner
        results = db.search_recipes(query="dinner main dish", limit=1)
        if results:
            elapsed = (time.time() - match_start) * 1000
            logger.info(f"[MATCH] {date}: '{name}' → '{results[0].name}' ({elapsed:.0f}ms, fallback)")
            return (date, results[0], results[0].name)

        # This shouldn't happen with 492K recipes
        raise ValueError(f"No recipes found for '{name}'")

    logger.info(f"[MATCH] Starting parallel fuzzy match for {len(meal_names)} meals")
    match_start = time.time()

    recipes = {}
    with ThreadPoolExecutor(max_workers=min(7, len(meal_names))) as executor:
        futures = {
            executor.submit(match_one, date, name): date
            for date, name in meal_names.items()
        }
        for future in as_completed(futures):
            try:
                date, recipe, matched_name = future.result()
                recipes[date] = recipe
            except Exception as e:
                date = futures[future]
                logger.error(f"[MATCH] Failed to match {date}: {e}")
                # Don't fail the whole plan, we'll handle missing recipes later

    elapsed = (time.time() - match_start) * 1000
    logger.info(f"[MATCH] Parallel fuzzy match completed in {elapsed:.0f}ms ({len(recipes)}/{len(meal_names)} matched)")

    return recipes


def handle_plan_meals(chatbot, tool_input: Dict[str, Any]) -> str:
    """Handle the plan_meals tool (deprecated)."""
    result = chatbot.assistant.plan_week(
        week_of=tool_input.get("week_of"),
        num_days=tool_input.get("num_days", 7),
    )
    if result["success"]:
        chatbot.current_meal_plan_id = result["meal_plan_id"]
        chatbot.current_snapshot_id = result["meal_plan_id"]
        output = f"Created meal plan: {result['meal_plan_id']}\n\n"
        output += "Meals:\n"
        for meal in result["meals"]:
            output += f"- {meal['date']}: {meal['recipe_name']}\n"
        return output
    else:
        return f"Error: {result.get('error')}"


def handle_plan_meals_smart(chatbot, tool_input: Dict[str, Any]) -> str:
    """Handle the plan_meals_smart tool - main meal planning logic."""
    # 1. Extract/generate dates
    if hasattr(chatbot, 'selected_dates') and chatbot.selected_dates:
        dates = chatbot.selected_dates
        num_days = len(dates)
        week_of = chatbot.week_start if hasattr(chatbot, 'week_start') else dates[0]
        if chatbot.verbose:
            chatbot._verbose_output(f"      → Using {num_days} dates from UI: {dates[0]} to {dates[-1]}")
    else:
        num_days = tool_input.get("num_days", 7)
        today = datetime.now().date()
        dates = [(today + timedelta(days=i)).isoformat() for i in range(num_days)]
        week_of = dates[0]
        if chatbot.verbose:
            chatbot._verbose_output(f"      → Planning {num_days} days starting {dates[0]}")

    # 2. Get user message (skip tool_result entries - they're lists, not strings)
    plan_start_time = time.time()
    user_message = None
    if chatbot.conversation_history:
        for msg in reversed(chatbot.conversation_history):
            if msg["role"] == "user" and isinstance(msg["content"], str):
                user_message = msg["content"]
                break

    # =====================================================================
    # OPTION F: Generate + Fuzzy Match (ChatGPT-like speed)
    # =====================================================================
    if USE_GENERATE_FUZZY_MATCH:
        logger.info(f"[PLAN] Using Generate + Fuzzy Match approach (USE_GENERATE_FUZZY_MATCH=True)")
        chatbot._verbose_output("Generating meal ideas...")

        # Fetch recent meals to avoid repetition (~50ms)
        recent_meals = chatbot.assistant.db.get_meal_history(user_id=chatbot.user_id, weeks_back=2)
        recent_names = [m.recipe.name for m in recent_meals] if recent_meals else []
        if recent_names:
            logger.info(f"[PLAN] Found {len(recent_names)} recent meals to avoid")

        # Fetch user profile for preferences (~10ms)
        user_profile = chatbot.assistant.db.get_user_profile(user_id=chatbot.user_id)
        if user_profile:
            logger.info(f"[PLAN] Using user profile: cuisines={user_profile.favorite_cuisines}, allergens={user_profile.allergens}")

        # Fetch favorites (starred + auto-learned from ratings) (~10ms)
        favorites = chatbot.assistant.db.get_combined_favorites(user_id=chatbot.user_id, limit=10)
        if favorites:
            logger.info(f"[PLAN] Found {len(favorites)} favorites for context")

        # Step 1: Generate meal names with Haiku (~600ms)
        try:
            meal_names = generate_meal_names(
                client=chatbot.client,
                user_message=user_message or "plan varied dinners",
                dates=dates,
                recent_meals=recent_names,
                user_profile=user_profile,
                favorites=favorites,
            )
        except Exception as e:
            logger.error(f"[GENERATE] Failed: {e}")
            return f"Error generating meal plan: {str(e)}"

        chatbot._verbose_output("Finding matching recipes...")

        # Step 2: Parallel fuzzy match to real recipes (~500ms)
        try:
            recipes_by_date = parallel_fuzzy_match(
                db=chatbot.assistant.db,
                meal_names=meal_names,
            )
        except Exception as e:
            logger.error(f"[MATCH] Failed: {e}")
            return f"Error matching recipes: {str(e)}"

        # Check if we got all meals
        if len(recipes_by_date) < len(dates):
            missing = set(dates) - set(recipes_by_date.keys())
            logger.warning(f"[PLAN] Missing recipes for: {missing}")

        # Step 3: Build PlannedMeal objects
        meals = []
        for date in sorted(dates):
            if date in recipes_by_date:
                meals.append(PlannedMeal(
                    date=date,
                    meal_type="dinner",
                    recipe=recipes_by_date[date],
                    servings=4
                ))

        if not meals:
            return "Could not find matching recipes. Try different constraints."

        # Step 4: Create and save MealPlan
        chatbot._verbose_output("Saving your meal plan...")
        plan = MealPlan(
            week_of=week_of,
            meals=meals,
            preferences_applied=[],
            backup_recipes={}  # No backups in v1 of this approach
        )

        persist_start = time.time()
        plan_id = chatbot.assistant.db.save_meal_plan(plan, user_id=chatbot.user_id)
        persist_time = time.time() - persist_start
        logger.info(f"[PERSIST] Saved meal plan {plan_id} in {persist_time*1000:.0f}ms")

        chatbot.current_meal_plan_id = plan_id
        chatbot.current_snapshot_id = plan_id
        chatbot.last_meal_plan = plan

        # Log total timing
        total_time = time.time() - plan_start_time
        logger.info(f"[PLAN-TIMING] Generate+FuzzyMatch total={total_time*1000:.0f}ms for {num_days} days")

        # Return success JSON (ensure sorted by date for consistent display)
        sorted_plan_meals = sorted(plan.meals, key=lambda m: m.date)
        meals_summary = [
            {"date": m.date, "name": m.recipe.name, "generated": meal_names.get(m.date, "")}
            for m in sorted_plan_meals
        ]

        return json.dumps({
            "status": "complete",
            "plan_id": plan_id,
            "num_meals": len(plan.meals),
            "meals": meals_summary,
            "total_ingredients": len(plan.get_all_ingredients()),
            "timing_ms": int(total_time * 1000),
            "message": f"Created {num_days}-day meal plan in {total_time:.1f}s"
        })

    # =====================================================================
    # Legacy approaches (when USE_GENERATE_FUZZY_MATCH=False)
    # =====================================================================

    # 3. Get recent meals for freshness penalty
    recent_meals = chatbot.assistant.db.get_meal_history(user_id=chatbot.user_id, weeks_back=2)
    recent_names = [m.recipe.name for m in recent_meals] if recent_meals else []

    # 4. Get allergen exclusions
    exclude_allergens = tool_input.get("exclude_allergens", [])

    # 5. Build candidate pools - NEW or OLD approach
    if USE_LLM_QUERY_BUILDER:
        # NEW APPROACH: LLM builds query params directly
        logger.info(f"[PLAN] Using LLM query builder (USE_LLM_QUERY_BUILDER=True)")
        chatbot._verbose_output("Analyzing request with LLM...")

        try:
            query_params = llm_build_query_params(
                client=chatbot.client,
                user_message=user_message or "plan meals",
                dates=dates,
            )
        except Exception as e:
            logger.error(f"[LLM-QUERY] Failed to parse: {e}, falling back to algorithmic")
            query_params = {d: {"include_tags": ["main-dish"], "query": None} for d in dates}

        chatbot._verbose_output("Building candidate pools...")

        candidates_by_date, pool_timing = build_per_day_pools_v2(
            db=chatbot.assistant.db,
            query_params_by_date=query_params,
            recent_names=recent_names,
            exclude_allergens=exclude_allergens,
            user_id=chatbot.user_id,
            week_of=week_of,
            verbose=chatbot.verbose,
            verbose_callback=chatbot._verbose_output,
        )

        # Create minimal day_requirements for validation (still needed for select_recipes_with_llm)
        day_requirements = [
            type('DayReq', (), {
                'date': d,
                'cuisine': None,
                'dietary_hard': [],
                'dietary_soft': [],
                'surprise': False,
                'unhandled': [],
            })()
            for d in dates
        ]

        # Check for empty pools
        empty_pools = [d for d, pool in candidates_by_date.items() if not pool]
        if empty_pools:
            logger.warning(f"[PLAN] Empty pools after LLM query: {empty_pools}")
            # Don't immediately fail - let the selection try anyway

        # Single attempt with LLM approach (no retry loop needed - we trust the LLM)
        total_candidates = sum(len(pool) for pool in candidates_by_date.values())
        chatbot._verbose_output(f"Selecting {num_days} recipes from {total_candidates} candidates...")

        selected = select_recipes_with_llm(
            client=chatbot.client,
            candidates_by_date=candidates_by_date,
            day_requirements=day_requirements,
            recent_meals=recent_names,
            validation_feedback=None,
            verbose=chatbot.verbose,
            verbose_callback=chatbot._verbose_output,
        )

        if not selected:
            return "Could not select any recipes. Try different constraints."

        # Skip validation and retry loop for new approach
        pool_timing_total = sum(pool_timing.values())
        logger.info(f"[PLAN] LLM approach complete: {len(selected)} recipes selected, pool_time={pool_timing_total:.3f}s")

        # Set defaults for common logging code below
        parse_time = 0.0
        attempt = 0
        total_retry_time = 0.0

    else:
        # OLD APPROACH: Algorithmic parsing with retry loop
        logger.info(f"[PLAN] Using algorithmic parser (USE_LLM_QUERY_BUILDER=False)")

        parse_start = time.time()
        day_requirements = parse_requirements(user_message or "", dates)
        parse_time = time.time() - parse_start

        logger.info(f"[PARSE] parse_requirements completed in {parse_time:.3f}s")
        logger.info(f"[PARSE] Input message: {user_message}")
        for req in day_requirements:
            logger.info(f"[PARSE] {req.date}: cuisine={req.cuisine}, dietary_hard={req.dietary_hard}, dietary_soft={req.dietary_soft}, surprise={req.surprise}, unhandled={req.unhandled}")

        if chatbot.verbose:
            chatbot._verbose_output(f"      → Parsed requirements: {[str(r) for r in day_requirements]}")

        # Selection with retry loop
        logger.info(f"[RETRY-LOOP] Starting selection with MAX_RETRIES={MAX_RETRIES}")
        excluded_ids_by_date: Dict[str, Set[int]] = {d: set() for d in dates}
        validation_feedback = None
        selected = []
        candidates_by_date = {}
        pool_timing = {}
        total_retry_time = 0.0

        for attempt in range(MAX_RETRIES + 1):
            attempt_start = time.time()
            logger.info(f"[RETRY-LOOP] === Attempt {attempt} ===")

            chatbot._verbose_output(f"Building candidate pools{' (retry ' + str(attempt) + ')' if attempt > 0 else ''}...")

            candidates_by_date, pool_timing = build_per_day_pools(
                db=chatbot.assistant.db,
                day_requirements=day_requirements,
                recent_names=recent_names,
                exclude_allergens=exclude_allergens,
                excluded_ids_by_date=excluded_ids_by_date if attempt > 0 else None,
                user_id=chatbot.user_id,
                week_of=week_of,
                verbose=chatbot.verbose,
                verbose_callback=chatbot._verbose_output,
            )

            empty_pools = [req.date for req in day_requirements if not candidates_by_date.get(req.date)]
            if empty_pools:
                logger.info(f"[RETRY-LOOP] Empty pools detected: {empty_pools}")
                if attempt == 0:
                    return f"No recipes found for dates: {', '.join(empty_pools)}. Try relaxing cuisine/dietary constraints."
                else:
                    logger.warning(f"Empty pools on retry for: {empty_pools}")

            total_candidates = sum(len(pool) for pool in candidates_by_date.values())
            chatbot._verbose_output(f"Selecting {num_days} recipes from {total_candidates} candidates...")

            selected = select_recipes_with_llm(
                client=chatbot.client,
                candidates_by_date=candidates_by_date,
                day_requirements=day_requirements,
                recent_meals=recent_names,
                validation_feedback=validation_feedback,
                verbose=chatbot.verbose,
                verbose_callback=chatbot._verbose_output,
            )

            if not selected:
                return "Could not select any recipes. Try different constraints."

            chatbot._verbose_output(f"Selected: {', '.join([r.name[:25] for r in selected[:3]])}...")

            if chatbot.verbose:
                chatbot._verbose_output(f"      → Full selection: {', '.join([r.name[:30] for r in selected])}")

            validate_start = time.time()
            hard_failures, soft_warnings = validate_plan(selected, day_requirements)
            validate_time = time.time() - validate_start
            logger.info(f"[VALIDATE] validate_plan completed in {validate_time:.3f}s")
            logger.info(f"[VALIDATE] hard_failures={len(hard_failures)}, soft_warnings={len(soft_warnings)}")

            if soft_warnings and chatbot.verbose:
                for w in soft_warnings:
                    chatbot._verbose_output(f"      ℹ️  {w}")

            attempt_time = time.time() - attempt_start
            logger.info(f"[RETRY-LOOP] Attempt {attempt} completed in {attempt_time:.3f}s")

            if not hard_failures:
                if attempt > 0:
                    chatbot._verbose_output(f"      ✓ Validation passed after {attempt} retry(s)")
                    logger.info(f"[RETRY-LOOP] Success after {attempt} retry(s)")
                else:
                    logger.info(f"[RETRY-LOOP] Success on first attempt")
                break

            if attempt < MAX_RETRIES:
                total_retry_time += attempt_time
                validation_feedback = ""
                for f in hard_failures:
                    validation_feedback += f"- {f.date}: {f.recipe_name} - {f.reason}\n"
                    excluded_ids_by_date[f.date].add(f.recipe_id)

                logger.info(f"[RETRY-LOOP] Retry {attempt + 1}/{MAX_RETRIES} after {len(hard_failures)} hard failures")
                logger.info(f"[RETRY-LOOP] Excluded IDs by date: {dict((k, list(v)) for k, v in excluded_ids_by_date.items() if v)}")
                logger.info(f"[RETRY-LOOP] Validation feedback:\n{validation_feedback}")
                chatbot._verbose_output(f"      ⚠️  {len(hard_failures)} validation failures, retrying...")
                for f in hard_failures:
                    chatbot._verbose_output(f"         - {f}")
            else:
                total_retry_time += attempt_time
                logger.warning(f"[RETRY-LOOP] Max retries reached with {len(hard_failures)} hard failures, using deterministic fallback")
                chatbot._verbose_output(f"      ⚠️  Max retries reached, {len(hard_failures)} failures remain:")
                for f in hard_failures:
                    chatbot._verbose_output(f"         - {f}")

                failed_dates = {f.date for f in hard_failures}
                for i, req in enumerate(day_requirements):
                    if req.date in failed_dates and i < len(selected):
                        pool = candidates_by_date.get(req.date, [])
                        valid_pool = [r for r in pool if r.id not in excluded_ids_by_date[req.date]]
                        if valid_pool:
                            selected[i] = valid_pool[0]
                            logger.info(f"Deterministic fallback for {req.date}: {valid_pool[0].name}")

    # Log final plan summary
    logger.info(f"[FINAL-PLAN] === Final Selected Plan Summary ===")
    for date, recipe in zip(dates, selected):
        logger.info(f"[FINAL-PLAN] {date}: id={recipe.id}, name={recipe.name}")
        logger.info(f"[FINAL-PLAN] {date}: tags={recipe.tags[:10]}")

    # Log timing
    total_plan_time = time.time() - plan_start_time
    pool_total_time = sum(pool_timing.values())

    logger.info(f"[PLAN-TIMING] days={num_days} pool_ms={pool_total_time*1000:.1f} "
               f"stage2_ms={(total_plan_time - pool_total_time - parse_time)*1000:.1f} "
               f"total_ms={total_plan_time*1000:.1f} retries={attempt}")

    logger.info(f"[TIMING] === Timing Summary ===")
    logger.info(f"[TIMING] parse_requirements: {parse_time:.3f}s")
    logger.info(f"[TIMING] build_per_day_pools total: {pool_total_time:.3f}s")
    for date, t in pool_timing.items():
        logger.info(f"[TIMING] build_per_day_pools[{date}]: {t:.3f}s")
    logger.info(f"[TIMING] total_retry_time: {total_retry_time:.3f}s")
    logger.info(f"[TIMING] plan_meals_smart total: {total_plan_time:.3f}s (so far)")

    # 6. Store backup recipes
    all_candidates = []
    for pool in candidates_by_date.values():
        all_candidates.extend(pool)
    selected_ids = {r.id for r in selected}
    backups = [r for r in all_candidates if r.id not in selected_ids][:20]
    if chatbot.verbose and backups:
        chatbot._verbose_output(f"      → Stored {len(backups)} backup recipes for quick swaps")

    # Create PlannedMeal objects
    meals = [
        PlannedMeal(
            date=date,
            meal_type="dinner",
            recipe=recipe,
            servings=4
        )
        for date, recipe in zip(dates, selected)
    ]

    # Create and save MealPlan
    chatbot._verbose_output("Saving your meal plan...")
    backup_dict = {"mixed": backups} if backups else {}
    plan = MealPlan(
        week_of=week_of,
        meals=meals,
        preferences_applied=exclude_allergens,
        backup_recipes=backup_dict
    )
    persist_start = time.time()
    plan_id = chatbot.assistant.db.save_meal_plan(plan, user_id=chatbot.user_id)
    persist_time = time.time() - persist_start
    logger.info(f"[PERSIST] Saved meal plan {plan_id} in {persist_time:.3f}s")
    chatbot.current_meal_plan_id = plan_id
    chatbot.current_snapshot_id = plan_id

    chatbot.last_meal_plan = plan

    if chatbot.verbose:
        chatbot._verbose_output(f"      → Cached plan in memory ({len(plan.meals)} meals with embedded recipes)")

    # Return concise JSON to signal completion (prevents duplicate tool calls)
    total_ingredients = len(plan.get_all_ingredients())
    all_allergens = plan.get_all_allergens()

    meals_summary = [
        {"date": m.date, "name": m.recipe.name}
        for m in plan.meals
    ]

    return json.dumps({
        "status": "complete",
        "plan_id": plan_id,
        "num_meals": len(plan.meals),
        "meals": meals_summary,
        "total_ingredients": total_ingredients,
        "allergens": list(all_allergens) if all_allergens else [],
        "message": f"Created {num_days}-day meal plan with {total_ingredients} ingredients"
    })


def handle_create_shopping_list(chatbot, tool_input: Dict[str, Any]) -> str:
    """Handle the create_shopping_list tool."""
    meal_plan_id = tool_input.get("meal_plan_id") or chatbot.current_meal_plan_id
    if not meal_plan_id:
        return "Error: No meal plan available. Please plan meals first."

    scaling_instructions = tool_input.get("scaling_instructions")
    result = chatbot.assistant.create_shopping_list(
        meal_plan_id,
        scaling_instructions=scaling_instructions
    )
    if result["success"]:
        chatbot.current_shopping_list_id = result["grocery_list_id"]
        scaling_note = f" (with scaling: {scaling_instructions})" if scaling_instructions else ""
        return f"Created shopping list with {result['num_items']} items, organized by store section{scaling_note}."
    else:
        return f"Error: {result.get('error')}"


def handle_add_extra_items(chatbot, tool_input: Dict[str, Any]) -> str:
    """Handle the add_extra_items tool."""
    if not chatbot.current_shopping_list_id:
        return "Error: No shopping list available. Please create a shopping list first."

    items = tool_input.get("items", [])
    if not items:
        return "Error: No items provided to add."

    from mcp_server.tools.shopping_tools import ShoppingTools
    shopping_tools = ShoppingTools(chatbot.assistant.db)
    result = shopping_tools.add_extra_items(
        grocery_list_id=chatbot.current_shopping_list_id,
        items=items
    )

    if result["success"]:
        item_names = ", ".join([item["name"] for item in result["added_items"]])
        return f"✓ Added {len(result['added_items'])} item(s) to your shopping list: {item_names}"
    else:
        return f"Error: {result.get('error')}"


def handle_search_recipes(chatbot, tool_input: Dict[str, Any]) -> str:
    """Handle the search_recipes tool."""
    recipes = chatbot.assistant.db.search_recipes(
        query=tool_input.get("query"),
        max_time=tool_input.get("max_time"),
        tags=tool_input.get("tags"),
        limit=tool_input.get("limit", 10),
    )
    if not recipes:
        return "No recipes found matching your criteria."

    output = f"Found {len(recipes)} recipes:\n\n"
    for recipe in recipes[:10]:
        time_str = f"{recipe.estimated_time} min" if recipe.estimated_time else "?"
        output += f"- {recipe.name} (ID: {recipe.id})\n"
        output += f"  Time: {time_str}, Difficulty: {recipe.difficulty}\n"

        if recipe.has_structured_ingredients():
            allergens = recipe.get_all_allergens()
            if allergens:
                output += f"  Allergens: {', '.join(allergens)}\n"
            else:
                output += f"  Allergens: none detected\n"

    return output


def handle_get_cooking_guide(chatbot, tool_input: Dict[str, Any]) -> str:
    """Handle the get_cooking_guide tool."""
    result = chatbot.assistant.get_cooking_guide(tool_input["recipe_id"])
    if result["success"]:
        output = f"Recipe: {result['recipe_name']}\n"
        output += f"Time: {result['estimated_time']} min, Servings: {result['servings']}\n\n"
        output += "Ingredients:\n"
        for ing in result["ingredients"][:10]:
            output += f"- {ing}\n"
        if len(result["ingredients"]) > 10:
            output += f"... and {len(result['ingredients']) - 10} more\n"
        output += f"\nSteps: {len(result['steps'])} steps total"
        return output
    else:
        return f"Error: {result.get('error')}"


def handle_get_meal_history(chatbot, tool_input: Dict[str, Any]) -> str:
    """Handle the get_meal_history tool."""
    history = chatbot.assistant.db.get_meal_history(
        user_id=chatbot.user_id, weeks_back=tool_input.get("weeks_back", 4)
    )
    if not history:
        return "No meal history available."

    output = f"Recent meals (last {tool_input.get('weeks_back', 4)} weeks):\n"
    for meal in history[:20]:
        output += f"- {meal.recipe_name}\n"
    return output


def handle_show_current_plan(chatbot, tool_input: Dict[str, Any]) -> str:
    """Handle the show_current_plan tool."""
    if not chatbot.current_meal_plan_id:
        return "No active meal plan. Would you like me to create one?"

    meal_plan = chatbot.assistant.db.get_meal_plan(chatbot.current_meal_plan_id, user_id=chatbot.user_id)
    if meal_plan:
        chatbot.last_meal_plan = meal_plan
        if chatbot.verbose:
            chatbot._verbose_output(f"      → Loaded and cached plan ({len(meal_plan.meals)} meals)")

    explanation = chatbot.assistant.planning_agent.explain_plan(
        chatbot.current_meal_plan_id, user_id=chatbot.user_id
    )
    return explanation


def handle_show_shopping_list(chatbot, tool_input: Dict[str, Any]) -> str:
    """Handle the show_shopping_list tool."""
    if not chatbot.current_shopping_list_id:
        return "No shopping list created yet. Would you like me to create one?"

    formatted = chatbot.assistant.shopping_agent.format_shopping_list(
        chatbot.current_shopping_list_id
    )
    return formatted


def handle_swap_meal(chatbot, tool_input: Dict[str, Any]) -> str:
    """Handle the swap_meal tool."""
    if not chatbot.current_meal_plan_id:
        return "No active meal plan. Please create a meal plan first."

    result = chatbot.assistant.planning_agent.swap_meal(
        meal_plan_id=chatbot.current_meal_plan_id,
        date=tool_input["date"],
        requirements=tool_input["requirements"],
    )

    if result["success"]:
        # Also update the snapshot (source of truth for web UI)
        snapshot_id = getattr(chatbot, 'current_snapshot_id', None) or chatbot.current_meal_plan_id
        if snapshot_id and result.get("new_recipe_id"):
            chatbot.assistant.db.swap_meal_in_snapshot(
                snapshot_id=snapshot_id,
                date=result['date'],
                new_recipe_id=result['new_recipe_id'],
                user_id=chatbot.user_id
            )

        output = f"✓ Swapped meal on {result['date']}\n"
        output += f"  Old: {result['old_recipe']}\n"
        output += f"  New: {result['new_recipe']}\n"
        output += f"  Why: {result['reason']}"
        return output
    else:
        return f"Error: {result.get('error')}"


def handle_swap_meal_fast(chatbot, tool_input: Dict[str, Any]) -> str:
    """Handle the swap_meal_fast tool - uses cached backups for instant swaps."""
    if not chatbot.last_meal_plan:
        return "No meal plan loaded. Please create or load a plan first."

    date = tool_input["date"]
    requirements = tool_input["requirements"]

    # Step 1: Try to find matching backups
    candidates = []
    used_category = None
    match_mode = None

    for category, backups in chatbot.last_meal_plan.backup_recipes.items():
        mode = check_backup_match(
            client=chatbot.client,
            requirements=requirements,
            category=category,
            verbose=chatbot.verbose,
            verbose_callback=chatbot._verbose_output,
        )
        if mode != "no_match":
            candidates = backups
            used_category = category
            match_mode = mode
            if chatbot.verbose:
                chatbot._verbose_output(f"      → Found {len(candidates)} backup recipes for '{category}' (0 DB queries)")
            break

    # Step 2: Fall back to fresh search if no match
    if not candidates:
        if chatbot.verbose:
            chatbot._verbose_output(f"      → No matching backups, falling back to fresh search...")
        return handle_swap_meal(chatbot, tool_input)

    # Step 3: Handle based on match mode
    if match_mode == "confirm":
        options = select_backup_options(
            client=chatbot.client,
            backups=candidates,
            num_options=3,
            verbose=chatbot.verbose,
            verbose_callback=chatbot._verbose_output,
        )

        if chatbot.verbose:
            chatbot._verbose_output(f"      → Vague request detected, showing {len(options)} options to user")

        output = "I have these options from your original search:\n\n"
        for i, recipe in enumerate(options, 1):
            ing_count = len(recipe.get_ingredients()) if recipe.has_structured_ingredients() else len(recipe.ingredients_raw)
            est_time = "unknown"
            for tag in recipe.tags:
                if 'min' in str(tag).lower():
                    est_time = tag
                    break

            output += f"{i}. **{recipe.name}**\n"
            output += f"   {ing_count} ingredients, {est_time}\n\n"

        output += "Would any of these work? (Or say 'no' if you'd like something different)"

        chatbot.pending_swap_options = {
            "date": date,
            "options": options,
            "category": used_category
        }

        return output

    # Step 3b: Auto-swap for specific requests
    new_recipe = candidates[0]

    # Step 4: Find the meal to swap
    target_meal = None
    for meal in chatbot.last_meal_plan.meals:
        if meal.date == date:
            target_meal = meal
            break

    if not target_meal:
        return f"No meal found on {date}"

    old_recipe_name = target_meal.recipe.name

    # Step 5: Update database (legacy table)
    success = chatbot.assistant.db.swap_meal_in_plan(
        plan_id=chatbot.last_meal_plan.id,
        date=date,
        new_recipe_id=new_recipe.id,
        user_id=chatbot.user_id
    )

    if not success:
        return "Error: Failed to update meal plan in database"

    # Also update the snapshot (source of truth for web UI)
    snapshot_id = getattr(chatbot, 'current_snapshot_id', None) or chatbot.current_meal_plan_id
    if snapshot_id:
        chatbot.assistant.db.swap_meal_in_snapshot(
            snapshot_id=snapshot_id,
            date=date,
            new_recipe_id=new_recipe.id,
            user_id=chatbot.user_id
        )

    # Step 6: Update cached plan
    target_meal.recipe = new_recipe
    if chatbot.verbose:
        chatbot._verbose_output(f"      → Updated cached plan (instant swap, total <10ms)")

    # Step 7: Return success message
    output = f"✓ Swapped meal on {date} (using cached backups)\n"
    output += f"  Old: {old_recipe_name}\n"
    output += f"  New: {new_recipe.name}\n"
    output += f"  Category: {used_category}\n"
    output += f"  Performance: <10ms (95% faster than fresh search)"
    return output


def handle_confirm_swap(chatbot, tool_input: Dict[str, Any]) -> str:
    """Handle the confirm_swap tool - completes a swap after user selects option."""
    if not chatbot.pending_swap_options:
        return "No pending swap to confirm. Please request a meal swap first."

    selection = tool_input["selection"].lower()

    selected_recipe = None
    options = chatbot.pending_swap_options["options"]

    # Try numeric selection
    for num_word, index in [("1", 0), ("2", 1), ("3", 2),
                            ("first", 0), ("second", 1), ("third", 2),
                            ("one", 0), ("two", 1), ("three", 2)]:
        if num_word in selection:
            if index < len(options):
                selected_recipe = options[index]
                break

    # Try matching recipe name
    if not selected_recipe:
        for recipe in options:
            if recipe.name.lower() in selection or selection in recipe.name.lower():
                selected_recipe = recipe
                break

    # Fallback to first option
    if not selected_recipe:
        selected_recipe = options[0]
        if chatbot.verbose:
            chatbot._verbose_output(f"      → Could not parse selection '{selection}', using first option")

    date = chatbot.pending_swap_options["date"]
    category = chatbot.pending_swap_options["category"]

    # Find the meal to swap
    target_meal = None
    for meal in chatbot.last_meal_plan.meals:
        if meal.date == date:
            target_meal = meal
            break

    if not target_meal:
        return f"Error: No meal found on {date}"

    old_recipe_name = target_meal.recipe.name

    # Update database (legacy table)
    success = chatbot.assistant.db.swap_meal_in_plan(
        plan_id=chatbot.last_meal_plan.id,
        date=date,
        new_recipe_id=selected_recipe.id,
        user_id=chatbot.user_id
    )

    if not success:
        return "Error: Failed to update meal plan in database"

    # Also update the snapshot (source of truth for web UI)
    snapshot_id = getattr(chatbot, 'current_snapshot_id', None) or chatbot.current_meal_plan_id
    if snapshot_id:
        chatbot.assistant.db.swap_meal_in_snapshot(
            snapshot_id=snapshot_id,
            date=date,
            new_recipe_id=selected_recipe.id,
            user_id=chatbot.user_id
        )

    # Update cached plan
    target_meal.recipe = selected_recipe
    if chatbot.verbose:
        chatbot._verbose_output(f"      → Swapped to user's selected option (instant, <10ms)")

    # Clear pending options
    chatbot.pending_swap_options = None

    output = f"✓ Swapped meal on {date}\n"
    output += f"  Old: {old_recipe_name}\n"
    output += f"  New: {selected_recipe.name}\n"
    output += f"  Category: {category}\n"
    output += f"  Performance: <10ms (from backup queue)"
    return output


def handle_check_allergens(chatbot, tool_input: Dict[str, Any]) -> str:
    """Handle the check_allergens tool."""
    if not chatbot.last_meal_plan:
        return "No meal plan loaded. Please create or load a plan first."

    allergen = tool_input["allergen"].lower()
    all_allergens = chatbot.last_meal_plan.get_all_allergens()

    if chatbot.verbose:
        chatbot._verbose_output(f"      → Checking cached plan for '{allergen}' (0 DB queries)")

    if allergen in all_allergens:
        meals = chatbot.last_meal_plan.get_meals_with_allergen(allergen)
        meal_names = [meal.recipe.name for meal in meals]
        return f"⚠️  Found {allergen} in {len(meals)} meal(s): {', '.join(meal_names)}"
    else:
        return f"✓ No {allergen} detected in your meal plan!"


def handle_list_meals_by_allergen(chatbot, tool_input: Dict[str, Any]) -> str:
    """Handle the list_meals_by_allergen tool."""
    if not chatbot.last_meal_plan:
        return "No meal plan loaded. Please create or load a plan first."

    allergen = tool_input["allergen"].lower()
    meals = chatbot.last_meal_plan.get_meals_with_allergen(allergen)

    if chatbot.verbose:
        chatbot._verbose_output(f"      → Filtering cached plan for '{allergen}' (0 DB queries)")

    if not meals:
        return f"No meals contain {allergen}."

    output = f"Meals with {allergen}:\n\n"
    for meal in meals:
        output += f"- {meal.date}: {meal.recipe.name}\n"
        allergen_ings = [
            ing.name for ing in meal.recipe.get_ingredients()
            if allergen in ing.allergens
        ]
        if allergen_ings:
            output += f"  Contains in: {', '.join(allergen_ings[:3])}"
            if len(allergen_ings) > 3:
                output += f" (+{len(allergen_ings) - 3} more)"
            output += "\n"
    return output


def handle_get_day_ingredients(chatbot, tool_input: Dict[str, Any]) -> str:
    """Handle the get_day_ingredients tool."""
    if not chatbot.last_meal_plan:
        return "No meal plan loaded. Please create or load a plan first."

    date = tool_input["date"]
    meals = chatbot.last_meal_plan.get_meals_for_day(date)

    if chatbot.verbose:
        chatbot._verbose_output(f"      → Getting ingredients for {date} from cached plan (0 DB queries)")

    if not meals:
        return f"No meals found for {date}. Check your plan dates."

    all_ingredients = []
    meal_names = []
    for meal in meals:
        meal_names.append(meal.recipe.name)
        ingredients = meal.recipe.get_ingredients()
        if ingredients:
            all_ingredients.extend(ingredients)

    if not all_ingredients:
        return f"No structured ingredients available for {', '.join(meal_names)}"

    output = f"Ingredients for {', '.join(meal_names)} ({date}):\n\n"
    for ing in all_ingredients:
        output += f"- {ing.quantity} {ing.unit} {ing.name}"
        if ing.preparation:
            output += f", {ing.preparation}"
        output += "\n"

    output += f"\nTotal: {len(all_ingredients)} ingredients"
    return output


def handle_modify_recipe(chatbot, tool_input: Dict[str, Any]) -> str:
    """Handle the modify_recipe tool - creates recipe variants."""
    if not chatbot.last_meal_plan:
        return "No meal plan loaded. Please create or load a plan first."

    date = tool_input["date"]
    modification = tool_input["modification"]

    meals = chatbot.last_meal_plan.get_meals_for_day(date)
    if not meals:
        return f"No meal found for {date}. Check your plan dates."

    meal = meals[0]
    recipe = meal.recipe

    if chatbot.verbose:
        chatbot._verbose_output(f"      → Modifying recipe '{recipe.name}' for {date}")

    try:
        from patch_engine import create_variant

        snapshot_id = getattr(chatbot, 'current_snapshot_id', None)
        if not snapshot_id:
            snapshot_id = getattr(chatbot.last_meal_plan, 'snapshot_id', None)
        if not snapshot_id:
            snapshot_id = f"snap_{date.replace('-', '')}"

        variant, warnings = create_variant(
            user_request=modification,
            recipe=recipe.to_dict(),
            snapshot_id=snapshot_id,
            date=date,
            meal_type="dinner",
            client=chatbot.client,
        )

        meal.variant = variant

        if hasattr(chatbot.assistant, 'db') and snapshot_id:
            try:
                snapshot = chatbot.assistant.db.get_snapshot(snapshot_id)
                if snapshot:
                    for pm in snapshot.get('planned_meals', []):
                        if pm.get('date') == date and pm.get('meal_type') == 'dinner':
                            pm['variant'] = variant
                            break
                    chatbot.assistant.db.save_snapshot(snapshot)
                    logger.info(f"[VARIANT_CREATE] Saved variant to snapshot {snapshot_id}")
            except Exception as e:
                logger.warning(f"[VARIANT_CREATE] Could not save to snapshot: {e}")

        compiled = variant['compiled_recipe']
        output = f"✓ Modified '{recipe.name}' for {date}!\n\n"
        output += f"**{compiled['name']}**\n\n"

        if warnings:
            output += "**Cooking notes:**\n"
            for w in warnings:
                output += f"- {w}\n"
            output += "\n"

        output += "The shopping list will be updated with the new ingredients."
        return output

    except ValueError as e:
        return f"Couldn't modify the recipe: {str(e)}"
    except Exception as e:
        logger.error(f"[VARIANT_CREATE] Error: {e}", exc_info=True)
        return f"Error modifying recipe: {str(e)}"


def handle_clear_recipe_modifications(chatbot, tool_input: Dict[str, Any]) -> str:
    """Handle the clear_recipe_modifications tool."""
    if not chatbot.last_meal_plan:
        return "No meal plan loaded. Please create or load a plan first."

    date = tool_input["date"]

    meals = chatbot.last_meal_plan.get_meals_for_day(date)
    if not meals:
        return f"No meal found for {date}. Check your plan dates."

    meal = meals[0]

    if not meal.has_variant():
        return f"The meal on {date} hasn't been modified."

    snapshot_id = getattr(chatbot, 'current_snapshot_id', None) or getattr(chatbot.last_meal_plan, 'snapshot_id', None)

    if snapshot_id and hasattr(chatbot.assistant, 'db'):
        try:
            from patch_engine import clear_variant
            snapshot = chatbot.assistant.db.get_snapshot(snapshot_id)
            if snapshot:
                clear_variant(snapshot, date, "dinner")
                chatbot.assistant.db.save_snapshot(snapshot)
        except Exception as e:
            logger.warning(f"[VARIANT_CLEAR] Could not update snapshot: {e}")

    original_name = meal.recipe.name
    meal.variant = None

    return f"✓ Reverted to original recipe: {original_name}"


# =============================================================================
# Favorites Handlers
# =============================================================================

def handle_show_favorites(chatbot, tool_input: Dict[str, Any]) -> str:
    """Handle the show_favorites tool."""
    limit = tool_input.get("limit", 10)

    favorites = chatbot.assistant.db.get_combined_favorites(
        user_id=chatbot.user_id,
        limit=limit
    )

    if not favorites:
        return "You don't have any favorites yet. Star recipes you love to see them here!"

    # Format the favorites list
    lines = ["Your favorite recipes:\n"]
    starred = [f for f in favorites if f["source"] == "starred"]
    learned = [f for f in favorites if f["source"] == "learned"]

    if starred:
        lines.append("⭐ Starred:")
        for f in starred:
            lines.append(f"  • {f['recipe_name']}")

    if learned:
        if starred:
            lines.append("\n🎯 From your 5-star ratings:")
        else:
            lines.append("🎯 Based on your ratings:")
        for f in learned:
            times = f["times_cooked"]
            suffix = f" (made {times}x)" if times > 1 else ""
            lines.append(f"  • {f['recipe_name']}{suffix}")

    return "\n".join(lines)


def handle_add_favorite(chatbot, tool_input: Dict[str, Any]) -> str:
    """Handle the add_favorite tool."""
    recipe_id = tool_input["recipe_id"]
    recipe_name = tool_input["recipe_name"]

    success = chatbot.assistant.db.add_favorite(
        user_id=chatbot.user_id,
        recipe_id=recipe_id,
        recipe_name=recipe_name
    )

    if success:
        return f"⭐ Added '{recipe_name}' to your favorites!"
    else:
        return f"'{recipe_name}' is already in your favorites."


def handle_remove_favorite(chatbot, tool_input: Dict[str, Any]) -> str:
    """Handle the remove_favorite tool."""
    recipe_id = tool_input["recipe_id"]

    success = chatbot.assistant.db.remove_favorite(
        user_id=chatbot.user_id,
        recipe_id=recipe_id
    )

    if success:
        return "Removed from favorites."
    else:
        return "That recipe wasn't in your favorites."
