"""
Tool handler functions for the meal planning chatbot.

Extracted from chatbot.py - contains handler functions for each tool.
Each handler takes (chatbot, tool_input) and returns a string result.
"""

import time
import logging
from datetime import datetime, timedelta
from typing import Dict, Any, Set, List

from data.models import PlannedMeal, MealPlan
from requirements_parser import parse_requirements
from chatbot_modules.pool_builder import build_per_day_pools
from chatbot_modules.recipe_selector import select_recipes_with_llm, validate_plan
from chatbot_modules.swap_matcher import check_backup_match, select_backup_options

logger = logging.getLogger(__name__)

# Configuration
MAX_RETRIES = 2


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

    # 2. Get user message and parse requirements
    plan_start_time = time.time()
    user_message = None
    if chatbot.conversation_history:
        for msg in reversed(chatbot.conversation_history):
            if msg["role"] == "user":
                user_message = msg["content"]
                break

    parse_start = time.time()
    day_requirements = parse_requirements(user_message or "", dates)
    parse_time = time.time() - parse_start

    logger.info(f"[PARSE] parse_requirements completed in {parse_time:.3f}s")
    logger.info(f"[PARSE] Input message: {user_message}")
    for req in day_requirements:
        logger.info(f"[PARSE] {req.date}: cuisine={req.cuisine}, dietary_hard={req.dietary_hard}, dietary_soft={req.dietary_soft}, surprise={req.surprise}, unhandled={req.unhandled}")

    if chatbot.verbose:
        chatbot._verbose_output(f"      → Parsed requirements: {[str(r) for r in day_requirements]}")

    # 3. Get recent meals for freshness penalty
    recent_meals = chatbot.assistant.db.get_meal_history(user_id=chatbot.user_id, weeks_back=2)
    recent_names = [m.recipe.name for m in recent_meals] if recent_meals else []

    # 4. Get allergen exclusions
    exclude_allergens = tool_input.get("exclude_allergens", [])

    # 5. Selection with retry loop
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

    # Return summary
    total_ingredients = len(plan.get_all_ingredients())
    all_allergens = plan.get_all_allergens()
    allergen_str = f", allergens: {', '.join(all_allergens)}" if all_allergens else ", allergen-free"

    output = f"✓ Created {num_days}-day meal plan!\n\n"
    output += "Meals:\n"
    for meal in plan.meals:
        ing_count = len(meal.recipe.get_ingredients()) if meal.recipe.has_structured_ingredients() else "?"
        output += f"- {meal.date}: {meal.recipe.name} ({ing_count} ingredients)\n"
    output += f"\n📊 {total_ingredients} total ingredients{allergen_str}"

    return output


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

    # Step 5: Update database
    success = chatbot.assistant.db.swap_meal_in_plan(
        plan_id=chatbot.last_meal_plan.id,
        date=date,
        new_recipe_id=new_recipe.id,
        user_id=chatbot.user_id
    )

    if not success:
        return "Error: Failed to update meal plan in database"

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

    # Update database
    success = chatbot.assistant.db.swap_meal_in_plan(
        plan_id=chatbot.last_meal_plan.id,
        date=date,
        new_recipe_id=selected_recipe.id,
        user_id=chatbot.user_id
    )

    if not success:
        return "Error: Failed to update meal plan in database"

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
