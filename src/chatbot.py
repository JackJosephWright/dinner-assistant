#!/usr/bin/env python3
"""
LLM-powered chatbot for Meal Planning Assistant.

Uses Claude via Anthropic API with MCP tool access.
"""

import os
import sys
import json
import logging
import time
from dataclasses import dataclass
from typing import List, Dict, Any, Tuple, Optional, Set
from datetime import datetime, timedelta
from dotenv import load_dotenv

logger = logging.getLogger(__name__)

# Verification report config constants
POOL_SIZE = 80  # Fetch 80 candidates per day
LLM_CANDIDATES_SHOWN = 20  # Show top 20 to LLM
MAX_RETRIES = 2  # Maximum retry attempts
STAGE2_MODEL = "claude-sonnet-4-5-20250929"  # Model for recipe selection

# Load environment variables from .env file
load_dotenv()

from anthropic import Anthropic

from main import MealPlanningAssistant
from data.models import PlannedMeal, MealPlan
from tag_canon import (
    CANON_COURSE_MAIN,
    CANON_COURSE_EXCLUDE,
    TAG_SYNONYMS,
)
from requirements_parser import parse_requirements, DayRequirement
from chatbot_modules.pool_builder import build_per_day_pools
from chatbot_modules.recipe_selector import (
    select_recipes_with_llm,
    validate_plan,
    ValidationFailure,
)
from chatbot_modules.swap_matcher import (
    check_backup_match,
    select_backup_options,
    llm_semantic_match,
)
from chatbot_modules.tools_config import (
    build_system_prompt,
    get_tools as get_tool_definitions,
    TOOL_DEFINITIONS,
)


class MealPlanningChatbot:
    """LLM-powered chatbot with MCP tool access."""

    def __init__(self, verbose=False, verbose_callback=None, user_id: int = 1):
        """Initialize chatbot with LLM and tools.

        Args:
            verbose: If True, print tool execution details
            verbose_callback: Optional callback function(message: str) for streaming verbose output to web UI
            user_id: User ID for multi-user support (defaults to 1)
        """
        # Check for API key
        api_key = os.environ.get("ANTHROPIC_API_KEY")
        if not api_key:
            print("❌ Error: ANTHROPIC_API_KEY environment variable not set")
            print("\nTo use the chatbot, set your API key:")
            print("  export ANTHROPIC_API_KEY='your-key-here'")
            print("\nOr use command mode instead:")
            print("  ./run.sh workflow")
            sys.exit(1)

        self.client = Anthropic(api_key=api_key)
        # Use agentic agents (API key is available)
        self.assistant = MealPlanningAssistant(db_dir="data", use_agentic=True)
        self.conversation_history = []

        # User ID for multi-user support
        self.user_id = user_id

        # Current context
        self.current_meal_plan_id = None
        self.current_shopping_list_id = None

        # In-memory object store (for follow-up questions)
        self.last_search_results = []  # List[Recipe]
        self.last_meal_plan = None  # MealPlan object
        self.pending_swap_options = None  # Pending swap confirmation

        # Verbose mode for debugging
        self.verbose = verbose
        self._verbose_callback = verbose_callback
        # Wire verbose callback to planning agent
        self._sync_verbose_callback()

        # Auto-load most recent plan
        self._load_most_recent_plan()

    @property
    def verbose_callback(self):
        """Get the verbose callback."""
        return self._verbose_callback

    @verbose_callback.setter
    def verbose_callback(self, callback):
        """Set verbose callback and sync to planning agent."""
        self._verbose_callback = callback
        self._sync_verbose_callback()

    def _sync_verbose_callback(self):
        """Sync verbose callback to the assistant's planning agent."""
        if hasattr(self.assistant, 'planning_agent'):
            self.assistant.planning_agent.verbose_callback = self._verbose_callback

    def _verbose_output(self, message: str, end: str = "\n", flush: bool = False):
        """
        Output verbose message to both console and callback if available.

        Args:
            message: Verbose message to output
            end: String appended after the message (default: newline)
            flush: Whether to forcibly flush the stream (default: False)
        """
        print(message, end=end, flush=flush)
        if self.verbose_callback:
            try:
                self.verbose_callback(message)
            except Exception as e:
                # Don't let callback errors break the chatbot
                print(f"Warning: verbose_callback failed: {e}")

    def _load_most_recent_plan(self):
        """Load the most recent meal plan automatically on startup."""
        try:
            recent_plans = self.assistant.db.get_recent_meal_plans(user_id=self.user_id, limit=1)
            if recent_plans:
                self.last_meal_plan = recent_plans[0]
                self.current_meal_plan_id = recent_plans[0].id
                # Note: snapshot_id == meal_plan_id in this codebase
                self.current_snapshot_id = recent_plans[0].id
                if self.verbose:
                    self._verbose_output(f"📋 Resumed plan for week of {recent_plans[0].week_of}")
        except Exception as e:
            if self.verbose:
                self._verbose_output(f"Note: Could not load recent plan: {e}")

    # Wrapper methods for backwards compatibility with tests
    def validate_plan(self, selected_recipes: List, day_requirements: List) -> Tuple[List, List]:
        """Wrapper for standalone validate_plan function."""
        return validate_plan(selected_recipes, day_requirements)

    def _check_backup_match(self, requirements: str, category: str) -> str:
        """Wrapper for standalone check_backup_match function."""
        return check_backup_match(
            client=self.client,
            requirements=requirements,
            category=category,
            verbose=self.verbose,
            verbose_callback=self._verbose_output,
        )

    def get_system_prompt(self) -> str:
        """Get system prompt for the LLM."""
        return build_system_prompt(
            current_meal_plan_id=self.current_meal_plan_id,
            current_shopping_list_id=self.current_shopping_list_id,
            last_meal_plan=self.last_meal_plan,
        )

    def get_tools(self) -> List[Dict[str, Any]]:
        """Define tools available to the LLM."""
        return get_tool_definitions()

    def execute_tool(self, tool_name: str, tool_input: Dict[str, Any]) -> str:
        """Execute a tool and return results."""
        try:
            if tool_name == "plan_meals":
                result = self.assistant.plan_week(
                    week_of=tool_input.get("week_of"),
                    num_days=tool_input.get("num_days", 7),
                )
                if result["success"]:
                    self.current_meal_plan_id = result["meal_plan_id"]
                    # Note: snapshot_id == meal_plan_id in this codebase
                    self.current_snapshot_id = result["meal_plan_id"]
                    # Format nicely
                    output = f"Created meal plan: {result['meal_plan_id']}\n\n"
                    output += "Meals:\n"
                    for meal in result["meals"]:
                        output += f"- {meal['date']}: {meal['recipe_name']}\n"
                    return output
                else:
                    return f"Error: {result.get('error')}"

            elif tool_name == "plan_meals_smart":
                # 1. Extract/generate dates
                # Use dates from UI if available (web interface)
                if hasattr(self, 'selected_dates') and self.selected_dates:
                    # Use UI-selected dates - this overrides num_days from LLM
                    dates = self.selected_dates
                    num_days = len(dates)  # Use actual count of selected dates
                    week_of = self.week_start if hasattr(self, 'week_start') else dates[0]
                    if self.verbose:
                        self._verbose_output(f"      → Using {num_days} dates from UI: {dates[0]} to {dates[-1]}")
                else:
                    # Fallback for CLI/non-web usage - generate dates from today
                    num_days = tool_input.get("num_days", 7)
                    today = datetime.now().date()
                    dates = [(today + timedelta(days=i)).isoformat() for i in range(num_days)]
                    week_of = dates[0]
                    if self.verbose:
                        self._verbose_output(f"      → Planning {num_days} days starting {dates[0]}")

                # 2. Get user message and parse requirements
                plan_start_time = time.time()
                user_message = None
                if self.conversation_history:
                    for msg in reversed(self.conversation_history):
                        if msg["role"] == "user":
                            user_message = msg["content"]
                            break

                parse_start = time.time()
                day_requirements = parse_requirements(user_message or "", dates)
                parse_time = time.time() - parse_start

                # Log parsed requirements for verification report
                logger.info(f"[PARSE] parse_requirements completed in {parse_time:.3f}s")
                logger.info(f"[PARSE] Input message: {user_message}")
                for req in day_requirements:
                    logger.info(f"[PARSE] {req.date}: cuisine={req.cuisine}, dietary_hard={req.dietary_hard}, dietary_soft={req.dietary_soft}, surprise={req.surprise}, unhandled={req.unhandled}")

                if self.verbose:
                    self._verbose_output(f"      → Parsed requirements: {[str(r) for r in day_requirements]}")

                # 3. Get recent meals for freshness penalty
                recent_meals = self.assistant.db.get_meal_history(user_id=self.user_id, weeks_back=2)
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

                    # Build per-day candidate pools (filtering out excluded IDs from previous attempts)
                    self._verbose_output(f"Building candidate pools{' (retry ' + str(attempt) + ')' if attempt > 0 else ''}...")

                    candidates_by_date, pool_timing = build_per_day_pools(
                        db=self.assistant.db,
                        day_requirements=day_requirements,
                        recent_names=recent_names,
                        exclude_allergens=exclude_allergens,
                        excluded_ids_by_date=excluded_ids_by_date if attempt > 0 else None,
                        user_id=self.user_id,
                        week_of=week_of,
                        verbose=self.verbose,
                        verbose_callback=self._verbose_output,
                    )

                    # Check if we have enough candidates
                    empty_pools = [req.date for req in day_requirements if not candidates_by_date.get(req.date)]
                    if empty_pools:
                        logger.info(f"[RETRY-LOOP] Empty pools detected: {empty_pools}")
                        if attempt == 0:
                            return f"No recipes found for dates: {', '.join(empty_pools)}. Try relaxing cuisine/dietary constraints."
                        else:
                            # On retry, use fallback for empty pools
                            logger.warning(f"Empty pools on retry for: {empty_pools}")

                    total_candidates = sum(len(pool) for pool in candidates_by_date.values())
                    self._verbose_output(f"Selecting {num_days} recipes from {total_candidates} candidates...")

                    # LLM selection with per-day pools
                    selected = select_recipes_with_llm(
                        client=self.client,
                        candidates_by_date=candidates_by_date,
                        day_requirements=day_requirements,
                        recent_meals=recent_names,
                        validation_feedback=validation_feedback,
                        verbose=self.verbose,
                        verbose_callback=self._verbose_output,
                    )

                    if not selected:
                        return "Could not select any recipes. Try different constraints."

                    # Always emit completion progress
                    self._verbose_output(f"Selected: {', '.join([r.name[:25] for r in selected[:3]])}...")

                    if self.verbose:
                        self._verbose_output(f"      → Full selection: {', '.join([r.name[:30] for r in selected])}")

                    # Validate selection
                    validate_start = time.time()
                    hard_failures, soft_warnings = validate_plan(selected, day_requirements)
                    validate_time = time.time() - validate_start
                    logger.info(f"[VALIDATE] validate_plan completed in {validate_time:.3f}s")
                    logger.info(f"[VALIDATE] hard_failures={len(hard_failures)}, soft_warnings={len(soft_warnings)}")

                    # Log soft warnings (but don't retry for them)
                    if soft_warnings and self.verbose:
                        for w in soft_warnings:
                            self._verbose_output(f"      ℹ️  {w}")

                    attempt_time = time.time() - attempt_start
                    logger.info(f"[RETRY-LOOP] Attempt {attempt} completed in {attempt_time:.3f}s")

                    # Check for hard failures
                    if not hard_failures:
                        if attempt > 0:
                            self._verbose_output(f"      ✓ Validation passed after {attempt} retry(s)")
                            logger.info(f"[RETRY-LOOP] Success after {attempt} retry(s)")
                        else:
                            logger.info(f"[RETRY-LOOP] Success on first attempt")
                        break  # Success!

                    # Hard failures - prepare for retry or give up
                    if attempt < MAX_RETRIES:
                        total_retry_time += attempt_time

                        # Build feedback for retry
                        validation_feedback = ""
                        for f in hard_failures:
                            validation_feedback += f"- {f.date}: {f.recipe_name} - {f.reason}\n"
                            # Add failed recipe ID to exclusion list for that date
                            excluded_ids_by_date[f.date].add(f.recipe_id)

                        logger.info(f"[RETRY-LOOP] Retry {attempt + 1}/{MAX_RETRIES} after {len(hard_failures)} hard failures")
                        logger.info(f"[RETRY-LOOP] Excluded IDs by date: {dict((k, list(v)) for k, v in excluded_ids_by_date.items() if v)}")
                        logger.info(f"[RETRY-LOOP] Validation feedback:\n{validation_feedback}")
                        self._verbose_output(f"      ⚠️  {len(hard_failures)} validation failures, retrying...")
                        for f in hard_failures:
                            self._verbose_output(f"         - {f}")
                    else:
                        # Max retries reached - log failures but continue with best effort
                        total_retry_time += attempt_time
                        logger.warning(f"[RETRY-LOOP] Max retries reached with {len(hard_failures)} hard failures, using deterministic fallback")
                        self._verbose_output(f"      ⚠️  Max retries reached, {len(hard_failures)} failures remain:")
                        for f in hard_failures:
                            self._verbose_output(f"         - {f}")

                        # Use deterministic fallback for failed dates
                        failed_dates = {f.date for f in hard_failures}
                        for i, req in enumerate(day_requirements):
                            if req.date in failed_dates and i < len(selected):
                                pool = candidates_by_date.get(req.date, [])
                                # Filter out already-excluded IDs
                                valid_pool = [r for r in pool if r.id not in excluded_ids_by_date[req.date]]
                                if valid_pool:
                                    selected[i] = valid_pool[0]
                                    logger.info(f"Deterministic fallback for {req.date}: {valid_pool[0].name}")

                # Log final selected plan summary
                logger.info(f"[FINAL-PLAN] === Final Selected Plan Summary ===")
                for date, recipe in zip(dates, selected):
                    logger.info(f"[FINAL-PLAN] {date}: id={recipe.id}, name={recipe.name}")
                    logger.info(f"[FINAL-PLAN] {date}: tags={recipe.tags[:10]}")

                # Log timing summary
                total_plan_time = time.time() - plan_start_time
                pool_total_time = sum(pool_timing.values())

                # Compact single-line summary for prod monitoring (Phase 1 instrumentation)
                logger.info(f"[PLAN-TIMING] days={num_days} pool_ms={pool_total_time*1000:.1f} "
                           f"stage2_ms={(total_plan_time - pool_total_time - parse_time)*1000:.1f} "
                           f"total_ms={total_plan_time*1000:.1f} retries={attempt}")

                # Detailed timing breakdown
                logger.info(f"[TIMING] === Timing Summary ===")
                logger.info(f"[TIMING] parse_requirements: {parse_time:.3f}s")
                logger.info(f"[TIMING] build_per_day_pools total: {pool_total_time:.3f}s")
                for date, t in pool_timing.items():
                    logger.info(f"[TIMING] build_per_day_pools[{date}]: {t:.3f}s")
                logger.info(f"[TIMING] total_retry_time: {total_retry_time:.3f}s")
                logger.info(f"[TIMING] plan_meals_smart total: {total_plan_time:.3f}s (so far)")

                # 6. Store backup recipes from pools for quick swaps
                all_candidates = []
                for pool in candidates_by_date.values():
                    all_candidates.extend(pool)
                selected_ids = {r.id for r in selected}
                backups = [r for r in all_candidates if r.id not in selected_ids][:20]
                if self.verbose and backups:
                    self._verbose_output(f"      → Stored {len(backups)} backup recipes for quick swaps")

                # 5. Create PlannedMeal objects with embedded recipes
                meals = [
                    PlannedMeal(
                        date=date,
                        meal_type="dinner",
                        recipe=recipe,
                        servings=4
                    )
                    for date, recipe in zip(dates, selected)
                ]

                # 7. Create and save MealPlan
                self._verbose_output("Saving your meal plan...")
                backup_dict = {"mixed": backups} if backups else {}
                plan = MealPlan(
                    week_of=week_of,  # Use week start from UI or first date
                    meals=meals,
                    preferences_applied=exclude_allergens,  # Track what allergens were avoided
                    backup_recipes=backup_dict  # Store backups for instant swaps
                )
                persist_start = time.time()
                plan_id = self.assistant.db.save_meal_plan(plan, user_id=self.user_id)
                persist_time = time.time() - persist_start
                logger.info(f"[PERSIST] Saved meal plan {plan_id} in {persist_time:.3f}s")
                self.current_meal_plan_id = plan_id
                # Note: snapshot_id == meal_plan_id in this codebase
                self.current_snapshot_id = plan_id

                # Cache the plan in memory for follow-up questions
                self.last_meal_plan = plan

                if self.verbose:
                    self._verbose_output(f"      → Cached plan in memory ({len(plan.meals)} meals with embedded recipes)")

                # 7. Return summary
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

            elif tool_name == "create_shopping_list":
                meal_plan_id = tool_input.get("meal_plan_id") or self.current_meal_plan_id
                if not meal_plan_id:
                    return "Error: No meal plan available. Please plan meals first."

                scaling_instructions = tool_input.get("scaling_instructions")
                result = self.assistant.create_shopping_list(
                    meal_plan_id,
                    scaling_instructions=scaling_instructions
                )
                if result["success"]:
                    self.current_shopping_list_id = result["grocery_list_id"]
                    scaling_note = f" (with scaling: {scaling_instructions})" if scaling_instructions else ""
                    return f"Created shopping list with {result['num_items']} items, organized by store section{scaling_note}."
                else:
                    return f"Error: {result.get('error')}"

            elif tool_name == "add_extra_items":
                if not self.current_shopping_list_id:
                    return "Error: No shopping list available. Please create a shopping list first."

                items = tool_input.get("items", [])
                if not items:
                    return "Error: No items provided to add."

                # Call the shopping tools to add extra items
                from mcp_server.tools.shopping_tools import ShoppingTools
                shopping_tools = ShoppingTools(self.assistant.db)
                result = shopping_tools.add_extra_items(
                    grocery_list_id=self.current_shopping_list_id,
                    items=items
                )

                if result["success"]:
                    item_names = ", ".join([item["name"] for item in result["added_items"]])
                    return f"✓ Added {len(result['added_items'])} item(s) to your shopping list: {item_names}"
                else:
                    return f"Error: {result.get('error')}"

            elif tool_name == "search_recipes":
                recipes = self.assistant.db.search_recipes(
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

                    # Include allergen info if recipe is enriched
                    if recipe.has_structured_ingredients():
                        allergens = recipe.get_all_allergens()
                        if allergens:
                            output += f"  Allergens: {', '.join(allergens)}\n"
                        else:
                            output += f"  Allergens: none detected\n"

                return output

            elif tool_name == "get_cooking_guide":
                result = self.assistant.get_cooking_guide(tool_input["recipe_id"])
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

            elif tool_name == "get_meal_history":
                history = self.assistant.db.get_meal_history(
                    user_id=self.user_id, weeks_back=tool_input.get("weeks_back", 4)
                )
                if not history:
                    return "No meal history available."

                output = f"Recent meals (last {tool_input.get('weeks_back', 4)} weeks):\n"
                for meal in history[:20]:
                    output += f"- {meal.recipe_name}\n"
                return output

            elif tool_name == "show_current_plan":
                if not self.current_meal_plan_id:
                    return "No active meal plan. Would you like me to create one?"

                # Load plan from DB and cache it
                meal_plan = self.assistant.db.get_meal_plan(self.current_meal_plan_id, user_id=self.user_id)
                if meal_plan:
                    self.last_meal_plan = meal_plan
                    if self.verbose:
                        self._verbose_output(f"      → Loaded and cached plan ({len(meal_plan.meals)} meals)")

                # Get explanation from agent
                explanation = self.assistant.planning_agent.explain_plan(
                    self.current_meal_plan_id, user_id=self.user_id
                )
                return explanation

            elif tool_name == "show_shopping_list":
                if not self.current_shopping_list_id:
                    return "No shopping list created yet. Would you like me to create one?"

                formatted = self.assistant.shopping_agent.format_shopping_list(
                    self.current_shopping_list_id
                )
                return formatted

            elif tool_name == "swap_meal":
                if not self.current_meal_plan_id:
                    return "No active meal plan. Please create a meal plan first."

                result = self.assistant.planning_agent.swap_meal(
                    meal_plan_id=self.current_meal_plan_id,
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

            elif tool_name == "swap_meal_fast":
                if not self.last_meal_plan:
                    return "No meal plan loaded. Please create or load a plan first."

                date = tool_input["date"]
                requirements = tool_input["requirements"]

                # Step 1: Try to find matching backups
                candidates = []
                used_category = None
                match_mode = None

                for category, backups in self.last_meal_plan.backup_recipes.items():
                    mode = check_backup_match(
                        client=self.client,
                        requirements=requirements,
                        category=category,
                        verbose=self.verbose,
                        verbose_callback=self._verbose_output,
                    )
                    if mode != "no_match":
                        candidates = backups
                        used_category = category
                        match_mode = mode
                        if self.verbose:
                            self._verbose_output(f"      → Found {len(candidates)} backup recipes for '{category}' (0 DB queries)")
                        break

                # Step 2: Fall back to fresh search if no match
                if not candidates:
                    if self.verbose:
                        self._verbose_output(f"      → No matching backups, falling back to fresh search...")
                    # Use existing swap_meal tool
                    return self.execute_tool("swap_meal", tool_input)

                # Step 3: Handle based on match mode
                if match_mode == "confirm":
                    # Show options to user for vague requests
                    options = select_backup_options(
                        client=self.client,
                        backups=candidates,
                        num_options=3,
                        verbose=self.verbose,
                        verbose_callback=self._verbose_output,
                    )

                    if self.verbose:
                        self._verbose_output(f"      → Vague request detected, showing {len(options)} options to user")

                    # Return formatted options for LLM to present
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

                    # Store options for confirm_swap tool
                    self.pending_swap_options = {
                        "date": date,
                        "options": options,
                        "category": used_category
                    }

                    return output

                # Step 3b: Auto-swap for specific requests
                # Select best match from backups (just use first for now)
                new_recipe = candidates[0]

                # Step 4: Find the meal to swap
                target_meal = None
                for meal in self.last_meal_plan.meals:
                    if meal.date == date:
                        target_meal = meal
                        break

                if not target_meal:
                    return f"No meal found on {date}"

                old_recipe_name = target_meal.recipe.name

                # Step 5: Update database
                success = self.assistant.db.swap_meal_in_plan(
                    plan_id=self.last_meal_plan.id,
                    date=date,
                    new_recipe_id=new_recipe.id,
                    user_id=self.user_id
                )

                if not success:
                    return "Error: Failed to update meal plan in database"

                # Step 6: Update cached plan
                target_meal.recipe = new_recipe
                if self.verbose:
                    self._verbose_output(f"      → Updated cached plan (instant swap, total <10ms)")

                # Step 7: Return success message
                output = f"✓ Swapped meal on {date} (using cached backups)\n"
                output += f"  Old: {old_recipe_name}\n"
                output += f"  New: {new_recipe.name}\n"
                output += f"  Category: {used_category}\n"
                output += f"  Performance: <10ms (95% faster than fresh search)"
                return output

            elif tool_name == "confirm_swap":
                if not self.pending_swap_options:
                    return "No pending swap to confirm. Please request a meal swap first."

                selection = tool_input["selection"].lower()

                # Parse selection (could be "1", "2", "3", "first", "second", "third", or recipe name)
                selected_recipe = None
                options = self.pending_swap_options["options"]

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

                # If still no match, use first option as fallback
                if not selected_recipe:
                    selected_recipe = options[0]
                    if self.verbose:
                        self._verbose_output(f"      → Could not parse selection '{selection}', using first option")

                # Perform the swap
                date = self.pending_swap_options["date"]
                category = self.pending_swap_options["category"]

                # Find the meal to swap
                target_meal = None
                for meal in self.last_meal_plan.meals:
                    if meal.date == date:
                        target_meal = meal
                        break

                if not target_meal:
                    return f"Error: No meal found on {date}"

                old_recipe_name = target_meal.recipe.name

                # Update database
                success = self.assistant.db.swap_meal_in_plan(
                    plan_id=self.last_meal_plan.id,
                    date=date,
                    new_recipe_id=selected_recipe.id,
                    user_id=self.user_id
                )

                if not success:
                    return "Error: Failed to update meal plan in database"

                # Update cached plan
                target_meal.recipe = selected_recipe
                if self.verbose:
                    self._verbose_output(f"      → Swapped to user's selected option (instant, <10ms)")

                # Clear pending options
                self.pending_swap_options = None

                # Return success message
                output = f"✓ Swapped meal on {date}\n"
                output += f"  Old: {old_recipe_name}\n"
                output += f"  New: {selected_recipe.name}\n"
                output += f"  Category: {category}\n"
                output += f"  Performance: <10ms (from backup queue)"
                return output

            elif tool_name == "check_allergens":
                if not self.last_meal_plan:
                    return "No meal plan loaded. Please create or load a plan first."

                allergen = tool_input["allergen"].lower()
                all_allergens = self.last_meal_plan.get_all_allergens()

                if self.verbose:
                    self._verbose_output(f"      → Checking cached plan for '{allergen}' (0 DB queries)")

                if allergen in all_allergens:
                    meals = self.last_meal_plan.get_meals_with_allergen(allergen)
                    meal_names = [meal.recipe.name for meal in meals]
                    return f"⚠️  Found {allergen} in {len(meals)} meal(s): {', '.join(meal_names)}"
                else:
                    return f"✓ No {allergen} detected in your meal plan!"

            elif tool_name == "list_meals_by_allergen":
                if not self.last_meal_plan:
                    return "No meal plan loaded. Please create or load a plan first."

                allergen = tool_input["allergen"].lower()
                meals = self.last_meal_plan.get_meals_with_allergen(allergen)

                if self.verbose:
                    self._verbose_output(f"      → Filtering cached plan for '{allergen}' (0 DB queries)")

                if not meals:
                    return f"No meals contain {allergen}."

                output = f"Meals with {allergen}:\n\n"
                for meal in meals:
                    output += f"- {meal.date}: {meal.recipe.name}\n"
                    # Show which ingredients contain the allergen
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

            elif tool_name == "get_day_ingredients":
                if not self.last_meal_plan:
                    return "No meal plan loaded. Please create or load a plan first."

                date = tool_input["date"]
                meals = self.last_meal_plan.get_meals_for_day(date)

                if self.verbose:
                    self._verbose_output(f"      → Getting ingredients for {date} from cached plan (0 DB queries)")

                if not meals:
                    return f"No meals found for {date}. Check your plan dates."

                # Get ingredients from all meals on this day
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

            # Recipe Variants v0 tools
            elif tool_name == "modify_recipe":
                if not self.last_meal_plan:
                    return "No meal plan loaded. Please create or load a plan first."

                date = tool_input["date"]
                modification = tool_input["modification"]

                # Find the meal for this date
                meals = self.last_meal_plan.get_meals_for_day(date)
                if not meals:
                    return f"No meal found for {date}. Check your plan dates."

                meal = meals[0]  # Get the first meal (dinner)
                recipe = meal.recipe

                if self.verbose:
                    self._verbose_output(f"      → Modifying recipe '{recipe.name}' for {date}")

                try:
                    from patch_engine import create_variant

                    # Get snapshot ID from session/context
                    snapshot_id = getattr(self, 'current_snapshot_id', None)
                    if not snapshot_id:
                        # Try to get from last_meal_plan
                        snapshot_id = getattr(self.last_meal_plan, 'snapshot_id', None)
                    if not snapshot_id:
                        snapshot_id = f"snap_{date.replace('-', '')}"  # Fallback

                    # Create the variant
                    variant, warnings = create_variant(
                        user_request=modification,
                        recipe=recipe.to_dict(),
                        snapshot_id=snapshot_id,
                        date=date,
                        meal_type="dinner",
                        client=self.client,
                    )

                    # Store the variant in the meal
                    meal.variant = variant

                    # Update the snapshot in DB if possible
                    if hasattr(self.assistant, 'db') and snapshot_id:
                        try:
                            snapshot = self.assistant.db.get_snapshot(snapshot_id)
                            if snapshot:
                                for pm in snapshot.get('planned_meals', []):
                                    if pm.get('date') == date and pm.get('meal_type') == 'dinner':
                                        pm['variant'] = variant
                                        break
                                self.assistant.db.save_snapshot(snapshot)
                                logger.info(f"[VARIANT_CREATE] Saved variant to snapshot {snapshot_id}")
                        except Exception as e:
                            logger.warning(f"[VARIANT_CREATE] Could not save to snapshot: {e}")

                    # Build response
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

            elif tool_name == "clear_recipe_modifications":
                if not self.last_meal_plan:
                    return "No meal plan loaded. Please create or load a plan first."

                date = tool_input["date"]

                # Find the meal for this date
                meals = self.last_meal_plan.get_meals_for_day(date)
                if not meals:
                    return f"No meal found for {date}. Check your plan dates."

                meal = meals[0]

                if not meal.has_variant():
                    return f"The meal on {date} hasn't been modified."

                # Get snapshot and clear variant
                snapshot_id = getattr(self, 'current_snapshot_id', None) or getattr(self.last_meal_plan, 'snapshot_id', None)

                if snapshot_id and hasattr(self.assistant, 'db'):
                    try:
                        from patch_engine import clear_variant
                        snapshot = self.assistant.db.get_snapshot(snapshot_id)
                        if snapshot:
                            clear_variant(snapshot, date, "dinner")
                            self.assistant.db.save_snapshot(snapshot)
                    except Exception as e:
                        logger.warning(f"[VARIANT_CLEAR] Could not update snapshot: {e}")

                # Clear from in-memory meal
                original_name = meal.recipe.name
                meal.variant = None

                return f"✓ Reverted to original recipe: {original_name}"

            else:
                return f"Unknown tool: {tool_name}"

        except Exception as e:
            return f"Error executing {tool_name}: {str(e)}"

    def chat(self, user_message: str) -> str:
        """Send a message and get response."""
        # Add user message to history
        self.conversation_history.append({
            "role": "user",
            "content": user_message,
        })

        # Call Claude with tools
        response = self.client.messages.create(
            model="claude-sonnet-4-5-20250929",
            max_tokens=512,  # Reduced from 4096 for faster, more concise responses
            system=self.get_system_prompt(),
            tools=self.get_tools(),
            messages=self.conversation_history,
        )

        # Process response
        assistant_content = []

        while response.stop_reason == "tool_use":
            # Add assistant's response with tool_use blocks to history
            self.conversation_history.append({
                "role": "assistant",
                "content": response.content,
            })

            # Execute all tools and collect results
            tool_results = []
            for content_block in response.content:
                if content_block.type == "tool_use":
                    # Always emit user-friendly progress for tools (keeps UI responsive)
                    tool_friendly_names = {
                        "plan_meals": "Creating your meal plan...",
                        "plan_meals_smart": "Finding recipes for your meal plan...",
                        "create_shopping_list": "Building your shopping list...",
                        "search_recipes": "Searching recipes...",
                        "swap_meal": "Finding a replacement meal...",
                        "swap_meal_fast": "Swapping meal...",
                        "get_cooking_guide": "Loading recipe details...",
                        "check_allergens": "Checking allergens...",
                        "show_current_plan": "Loading your meal plan...",
                        "modify_recipe": "Modifying recipe...",
                        "clear_recipe_modifications": "Reverting to original recipe...",
                    }
                    friendly_msg = tool_friendly_names.get(content_block.name, f"Running {content_block.name}...")
                    self._verbose_output(friendly_msg)

                    if self.verbose:
                        self._verbose_output(f"\n🔧 [TOOL] {content_block.name}")
                        self._verbose_output(f"   Input: {json.dumps(content_block.input, indent=2)}")

                    tool_result = self.execute_tool(
                        content_block.name,
                        content_block.input,
                    )

                    if self.verbose:
                        # Truncate long results for readability
                        result_preview = tool_result if len(tool_result) < 200 else tool_result[:200] + "..."
                        self._verbose_output(f"   Result: {result_preview}\n")

                    tool_results.append({
                        "type": "tool_result",
                        "tool_use_id": content_block.id,
                        "content": tool_result,
                    })

            # Add all tool results in a single user message
            self.conversation_history.append({
                "role": "user",
                "content": tool_results,
            })

            # Emit progress before next LLM call
            self._verbose_output("Preparing your response...")

            # Get next response
            response = self.client.messages.create(
                model="claude-sonnet-4-5-20250929",
                max_tokens=512,  # Reduced from 4096 for faster, more concise responses
                system=self.get_system_prompt(),
                tools=self.get_tools(),
                messages=self.conversation_history,
            )

        # Extract final text response
        final_response = ""
        for content_block in response.content:
            if hasattr(content_block, "text"):
                final_response += content_block.text

        # Add to history
        self.conversation_history.append({
            "role": "assistant",
            "content": final_response,
        })

        return final_response

    def _display_current_plan_verbose(self):
        """Display current meal plan state in verbose mode."""
        if not self.verbose:
            return

        self._verbose_output("\n" + "="*70)
        self._verbose_output("📋 CURRENT MEAL PLAN STATE")
        self._verbose_output("="*70)

        if self.last_meal_plan is None or not self.last_meal_plan.meals:
            self._verbose_output("No active meal plan")
        else:
            self._verbose_output(f"Week of: {self.last_meal_plan.week_of}")
            self._verbose_output(f"Number of meals: {len(self.last_meal_plan.meals)}")
            self._verbose_output(f"\nMeals:")
            for meal in self.last_meal_plan.meals:
                day_name = meal.date.strftime("%a %m/%d") if isinstance(meal.date, datetime) else meal.date
                self._verbose_output(f"  • {day_name}: {meal.recipe.name}")
                self._verbose_output(f"    ({len(meal.recipe.ingredients)} ingredients)")

            # Show backup recipes available
            if self.last_meal_plan.backup_recipes:
                total_backups = sum(len(recipes) for recipes in self.last_meal_plan.backup_recipes.values())
                self._verbose_output(f"\n🔄 Backup recipes: {total_backups} cached")
                for category, recipes in self.last_meal_plan.backup_recipes.items():
                    self._verbose_output(f"   • {category}: {len(recipes)} recipes")

        self._verbose_output("="*70 + "\n")

    def run(self):
        """Run interactive chat loop."""
        self._verbose_output("\n" + "="*70)
        self._verbose_output("🍽️  MEAL PLANNING ASSISTANT - AI Chatbot")
        self._verbose_output("="*70)
        self._verbose_output("\nPowered by Claude Sonnet 4.5 with intelligent tools")
        self._verbose_output("Database: 5,000 enriched recipes (100% structured ingredients)")

        if self.verbose:
            self._verbose_output("Mode: VERBOSE (showing tool execution details)")

        self._verbose_output("\n✨ What I can do:")
        self._verbose_output("  • Plan meals with smart recipe selection")
        self._verbose_output("  • Filter by allergens (dairy, gluten, nuts, etc.)")
        self._verbose_output("  • Find recipes by keywords or cooking time")
        self._verbose_output("  • Create shopping lists organized by category")
        self._verbose_output("  • Swap meals in your plan")

        self._verbose_output("\n💡 Try asking:")
        self._verbose_output('  "Plan 4 days of chicken meals"')
        self._verbose_output('  "Plan a week, no dairy or gluten"')
        self._verbose_output('  "Show me quick pasta recipes under 30 minutes"')

        self._verbose_output("\nType 'quit' to exit.\n")

        while True:
            try:
                user_input = input("You: ").strip()

                if not user_input:
                    continue

                if user_input.lower() in ["quit", "exit", "bye"]:
                    self._verbose_output("\n🍽️  Assistant: Goodbye! Happy cooking!")
                    break

                # Get response
                self._verbose_output("\n🍽️  Assistant: ", end="", flush=True)
                response = self.chat(user_input)
                self._verbose_output(response + "\n")

                # Display current meal plan state in verbose mode
                self._display_current_plan_verbose()

            except KeyboardInterrupt:
                self._verbose_output("\n\n🍽️  Assistant: Goodbye!")
                break
            except Exception as e:
                self._verbose_output(f"\n❌ Error: {e}\n")


def main():
    """Entry point."""
    import argparse

    parser = argparse.ArgumentParser(
        description="Meal Planning Assistant - AI-powered chat interface"
    )
    parser.add_argument(
        "-v", "--verbose",
        action="store_true",
        help="Show tool execution details for debugging"
    )

    args = parser.parse_args()

    chatbot = MealPlanningChatbot(verbose=args.verbose)
    chatbot.run()


if __name__ == "__main__":
    main()
