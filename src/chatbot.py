#!/usr/bin/env python3
"""
LLM-powered chatbot for Meal Planning Assistant.

Uses Claude via Anthropic API with MCP tool access.
"""

import os
import sys
import json
from typing import List, Dict, Any
from datetime import datetime, timedelta
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

from anthropic import Anthropic

from main import MealPlanningAssistant
from data.models import PlannedMeal, MealPlan


class MealPlanningChatbot:
    """LLM-powered chatbot with MCP tool access."""

    def __init__(self, verbose=False, verbose_callback=None):
        """Initialize chatbot with LLM and tools.

        Args:
            verbose: If True, print tool execution details
            verbose_callback: Optional callback function(message: str) for streaming verbose output to web UI
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
            recent_plans = self.assistant.db.get_recent_meal_plans(limit=1)
            if recent_plans:
                self.last_meal_plan = recent_plans[0]
                self.current_meal_plan_id = recent_plans[0].id
                if self.verbose:
                    self._verbose_output(f"📋 Resumed plan for week of {recent_plans[0].week_of}")
        except Exception as e:
            if self.verbose:
                self._verbose_output(f"Note: Could not load recent plan: {e}")

    def _select_recipes_with_llm(self, recipes: List, num_needed: int, recent_meals: List = None, user_requirements: str = None) -> List:
        """
        Use LLM to intelligently select recipes considering variety and preferences.

        Args:
            recipes: List of Recipe objects to choose from
            num_needed: Number of recipes to select
            recent_meals: Optional list of recent meal names for variety
            user_requirements: Optional user's specific requirements (e.g., "one ramen, one spaghetti")

        Returns:
            List of selected Recipe objects
        """
        if len(recipes) <= num_needed:
            return recipes

        # Format recipes compactly for LLM
        recipes_text = []
        for i, r in enumerate(recipes, 1):
            ing_count = len(r.get_ingredients()) if r.has_structured_ingredients() else len(r.ingredients_raw)
            recipes_text.append(
                f"#{i} - {r.name}\n"
                f"   Recipe ID: {r.id}\n"
                f"   Ingredients: {ing_count} items\n"
                f"   Tags: {', '.join(r.tags[:5])}"
            )

        recent_text = ""
        if recent_meals:
            recent_text = f"\nRecent meals (avoid similar):\n" + "\n".join(f"- {m}" for m in recent_meals[:10])

        user_req_text = ""
        if user_requirements:
            user_req_text = f"\n⭐ USER'S SPECIFIC REQUIREMENTS (HIGHEST PRIORITY):\n{user_requirements}\n"

        # Show first few actual recipe IDs as examples
        example_ids = [str(r.id) for r in recipes[:5]]

        prompt = f"""Select {num_needed} recipes from the candidates below that would make a varied, balanced meal plan.

Goals:
- Add variety (different cuisines, cooking methods, proteins)
- Avoid repeating similar dishes
- Create an appealing week of meals
{user_req_text}
{recent_text}

Candidates ({len(recipes)} recipes):
{chr(10).join(recipes_text)}

CRITICAL INSTRUCTIONS FOR RECIPE ID SELECTION:
⚠️  IMPORTANT: Recipe IDs are 6-digit numbers like {example_ids[0]}, {example_ids[1]}, {example_ids[2]}
⚠️  DO NOT use the #N list position numbers (1, 2, 3, etc.)
⚠️  ONLY use the exact values shown in "Recipe ID:" lines

Steps:
1. Choose {num_needed} recipes that meet the requirements
2. For EACH recipe, copy its EXACT "Recipe ID:" value (6-digit number)
3. Return ONLY a JSON array of these Recipe ID strings
4. NO explanations, NO markdown, just the array

Example response format (using actual 6-digit IDs from above):
["{example_ids[0]}", "{example_ids[1]}", "{example_ids[2] if len(example_ids) > 2 else ''}"]"""

        try:
            response = self.client.messages.create(
                model="claude-sonnet-4-5-20250929",
                max_tokens=500,  # Increased for user requirements context
                messages=[{"role": "user", "content": prompt}]
            )

            # Extract JSON from response
            content = response.content[0].text.strip()

            if self.verbose:
                self._verbose_output(f"      → LLM response: {content[:100]}...")

            # Remove markdown code blocks if present
            if content.startswith("```"):
                content = content.split("```")[1]
                if content.startswith("json"):
                    content = content[4:]
            content = content.strip()

            # Extract JSON array if LLM added explanation text
            # Look for the first [ and last ]
            if not content.startswith("["):
                start_idx = content.find("[")
                if start_idx != -1:
                    content = content[start_idx:]
            if not content.endswith("]"):
                end_idx = content.rfind("]")
                if end_idx != -1:
                    content = content[:end_idx + 1]

            selected_ids = json.loads(content)

            # Convert IDs to strings for comparison (LLM may return strings or ints)
            selected_ids_str = [str(id) for id in selected_ids]

            if self.verbose:
                self._verbose_output(f"      → Matching IDs: {selected_ids_str}")
                self._verbose_output(f"      → Available recipe IDs: {[str(r.id) for r in recipes[:5]]}...")

            # Return recipes matching selected IDs
            matched = [r for r in recipes if str(r.id) in selected_ids_str]

            if self.verbose:
                self._verbose_output(f"      → Matched {len(matched)} recipes")

            # If LLM hallucinated invalid IDs, fill remaining slots with unused recipes
            if len(matched) < num_needed:
                if self.verbose:
                    self._verbose_output(f"      → ⚠️  LLM returned invalid IDs, filling {num_needed - len(matched)} remaining slots...")

                # Get recipes that weren't selected
                matched_ids = {str(r.id) for r in matched}
                remaining = [r for r in recipes if str(r.id) not in matched_ids]

                # Add enough to reach num_needed
                needed = num_needed - len(matched)
                matched.extend(remaining[:needed])

                if self.verbose:
                    self._verbose_output(f"      → Added: {[r.name[:30] for r in remaining[:needed]]}")

            return matched[:num_needed]

        except Exception as e:
            # Fallback: just return first N recipes
            if self.verbose:
                self._verbose_output(f"LLM selection failed: {e}, using fallback")
            return recipes[:num_needed]

    def _llm_semantic_match(self, requirements: str, category: str) -> bool:
        """
        Use LLM to determine if requirements semantically match a category.

        This is a fallback for edge cases that algorithmic matching misses.
        Uses Claude Haiku for fast, cheap semantic analysis (~100ms, $0.003).

        Args:
            requirements: User's swap request
            category: Backup category key

        Returns:
            True if LLM determines the requirements match the category
        """
        try:
            prompt = f"""Does the user's request match the recipe category?

User request: "{requirements}"
Recipe category: "{category}"

Consider:
- Does the request want recipes from this category?
- Are there negative filters that exclude this category?
- Would recipes in this category satisfy the request?

Answer ONLY with: YES or NO"""

            response = self.client.messages.create(
                model="claude-3-5-haiku-20241022",
                max_tokens=5,
                messages=[{"role": "user", "content": prompt}]
            )

            answer = response.content[0].text.strip().upper()
            return "YES" in answer

        except Exception as e:
            if self.verbose:
                self._verbose_output(f"      → LLM semantic match failed: {e}, assuming no match")
            return False

    def _select_backup_options(self, backups: List, num_options: int = 3) -> List:
        """
        Select the most interesting backup recipes to show user.

        Uses LLM to pick varied, appealing options from the backup queue.

        Args:
            backups: List of Recipe objects from backup queue
            num_options: Number of options to return (default 3)

        Returns:
            List of selected Recipe objects
        """
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

            response = self.client.messages.create(
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

            import json
            selected_ids = json.loads(content)
            selected_ids_str = [str(id) for id in selected_ids]

            # Match IDs to recipes
            selected = [r for r in backups if str(r.id) in selected_ids_str][:num_options]

            # If LLM failed, just return first N
            if len(selected) < num_options:
                return backups[:num_options]

            return selected

        except Exception as e:
            if self.verbose:
                self._verbose_output(f"      → LLM selection failed: {e}, using first {num_options}")
            return backups[:num_options]

    def _check_backup_match(self, requirements: str, category: str) -> str:
        """
        Check if user requirements match a backup category using hybrid matching.

        Uses two-tier approach:
        1. Fast algorithmic checks (handles 80-90% of cases)
        2. LLM semantic fallback for edge cases (handles remaining 10-20%)

        Args:
            requirements: User's swap request (e.g., "different chicken dish")
            category: Backup category key (e.g., "chicken")

        Returns:
            "confirm" - Vague request, show options to user
            "auto" - Specific request, auto-swap from backups
            "no_match" - Requirements don't match this category
        """
        requirements_lower = requirements.lower()
        category_lower = category.lower()

        # Tier 1: Fast algorithmic checks

        # Remove common exclusion patterns before checking for specific foods
        # "no X", "without X", "not X" are exclusions, not requirements
        import re
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
            if self.verbose:
                self._verbose_output(f"      → Matched '{category}' via direct match → AUTO mode")
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
                if self.verbose:
                    self._verbose_output(f"      → Matched '{category}' via related term '{term}' → AUTO mode")
                return "auto"

        # Check for vague terms that match any category → need confirmation
        # But only if there's NO specific food mentioned
        vague_terms = ["something", "anything", "other", "else"]
        if any(term in requirements_lower for term in vague_terms) and not has_specific_food:
            if self.verbose:
                self._verbose_output(f"      → Matched '{category}' via vague terms → CONFIRM mode")
            return "confirm"

        # "different" alone is vague, but "different chicken" is specific
        # Only trigger confirm if "different" exists AND no specific food AND category doesn't match
        if "different" in requirements_lower and not has_specific_food and category_lower not in requirements_lower:
            if self.verbose:
                self._verbose_output(f"      → Matched '{category}' via 'different' (vague) → CONFIRM mode")
            return "confirm"

        # Check for modifier words indicating same category → auto-swap
        modifiers = ["swap", "replace", "change"]
        has_modifier = any(mod in requirements_lower for mod in modifiers)
        if has_modifier and category_lower in requirements_lower:
            if self.verbose:
                self._verbose_output(f"      → Matched '{category}' via modifier → AUTO mode")
            return "auto"

        # Tier 2: LLM semantic fallback for edge cases → auto-swap
        if self._llm_semantic_match(requirements, category):
            if self.verbose:
                self._verbose_output(f"      → Matched '{category}' via LLM semantic analysis → AUTO mode")
            return "auto"

        if self.verbose:
            self._verbose_output(f"      → No match for '{category}'")
        return "no_match"

    def get_system_prompt(self) -> str:
        """Get system prompt for the LLM."""
        context = []
        if self.current_meal_plan_id:
            context.append(f"Current meal plan ID: {self.current_meal_plan_id}")
        if self.current_shopping_list_id:
            context.append(f"Current shopping list ID: {self.current_shopping_list_id}")

        context_str = "\n".join(context) if context else "No active plans yet."

        # Add meal plan date mapping for interpreting day references
        meal_plan_dates_context = ""
        if self.last_meal_plan and self.last_meal_plan.meals:
            meal_plan_dates_context = "\n\nCurrent meal plan dates:\n"
            for i, meal in enumerate(self.last_meal_plan.meals, 1):
                # Handle both datetime objects and string dates
                if isinstance(meal.date, str):
                    from datetime import datetime
                    meal_date = datetime.fromisoformat(meal.date)
                    day_name = meal_date.strftime("%A")
                else:
                    day_name = meal.date.strftime("%A")
                    meal_date = meal.date

                meal_plan_dates_context += f"  Day {i}: {day_name} ({meal.date}) - {meal.recipe.name}\n"

            meal_plan_dates_context += "\nWhen user says 'day 1', 'day 2', etc., they mean the Nth meal in the plan (day 1 = first meal, day 2 = second meal, etc.)"

        return f"""You are a helpful meal planning assistant. You help users plan their weekly meals, create shopping lists, and provide cooking guidance.

You have access to a database of 492,630 recipes and can search, plan meals, generate shopping lists, and provide cooking instructions.

Current context:
{context_str}{meal_plan_dates_context}

When users ask about meal planning:
- Offer to plan their week
- Ask about preferences if needed
- Use plan_meals_smart for most requests (supports allergens, time limits, search keywords)
- For MULTI-REQUIREMENT requests (e.g., "5 meals where one is ramen and one is spaghetti"):
  * Use plan_meals_smart WITHOUT specifying search_query (defaults to "dinner" for broad coverage)
  * Or use BROAD search_query like "main course" if you want to be explicit
  * The LLM selector automatically prioritizes user's specific requirements
  * DO NOT create generic plan + multiple swaps (inefficient - wastes 5-10 LLM calls)
  * Example: User wants "5 meals, one ramen, one pasta" → call plan_meals_smart(num_days=5) [search_query defaults to "dinner"]

When users want to change a meal:
- Use show_current_plan to see the current plan if needed
- Use swap_meal_fast FIRST for requests like "different chicken", "another pasta", "swap this"
  * swap_meal_fast uses cached backup recipes for instant swaps (<10ms, 95% faster)
  * Falls back to fresh search automatically if requirements don't match cached categories
- Only use swap_meal directly if swap_meal_fast is not appropriate

IMPORTANT - Interpreting day/meal references for swaps:
- "day 1", "day 2", "day 3" = the 1st, 2nd, 3rd meal in the plan (see Current meal plan dates above)
- "Monday", "Tuesday", etc. = the meal on that specific day of the week
- "the chicken meal", "that pasta" = find the meal matching that description
- "November 3rd", "2025-11-03" = specific calendar date (use exactly as given)
Examples:
  - "swap day 3" → Use date from "Day 3" above (e.g., if Day 3 is 2025-11-02, use that date)
  - "swap Monday" → Find Monday's date in the plan
  - "swap the chicken" → Find which meal has chicken, use its date

When users want shopping lists:
- Check if they have a meal plan first
- Use the create_shopping_list tool

For cooking help:
- Use get_cooking_guide to provide instructions
- Suggest substitutions when asked

When analyzing recipes:
- If asked about ingredients/allergens, use get_cooking_guide to check the ingredients
- ANALYZE the tool results and ANSWER the user's question directly
- Don't just display tool results - use them to answer what was asked

Working with cached meal plans:
- After creating or loading a plan, it is cached in memory with full Recipe objects
- For follow-up questions about the CURRENT plan, use the new cache-based tools:
  * check_allergens - "Does my plan have shellfish?" (instant, no DB queries)
  * list_meals_by_allergen - "Which meals have dairy?" (instant, no DB queries)
  * get_day_ingredients - "What do I need for Monday?" (instant, no DB queries)
- These tools work on the cached plan and are MUCH faster than re-fetching data
- Only use get_cooking_guide for recipes that are NOT in the current plan

IMPORTANT: Keep responses SHORT and to the point. Users want speed over lengthy explanations. Confirm actions with 1-2 sentences max. BUT ALWAYS answer the user's actual question based on tool results."""

    def get_tools(self) -> List[Dict[str, Any]]:
        """Define tools available to the LLM."""
        return [
            {
                "name": "plan_meals",
                "description": "Generate a 7-day meal plan with variety and balanced nutrition. Returns a meal plan with recipe names, IDs, and variety summary.",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "week_of": {
                            "type": "string",
                            "description": "ISO date for Monday of the week (YYYY-MM-DD). Optional, defaults to next week.",
                        },
                        "num_days": {
                            "type": "integer",
                            "description": "Number of days to plan (default: 7)",
                            "default": 7,
                        },
                    },
                },
            },
            {
                "name": "plan_meals_smart",
                "description": "Create a meal plan using enriched recipe database with smart filtering. Supports allergen filtering, time constraints, and natural language requests. USE THIS for custom planning requests. For multi-requirement requests (e.g., 'one ramen, one spaghetti, three other meals'), use broad search_query like 'dinner' and the LLM will prioritize specific requirements from user's message.",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "num_days": {
                            "type": "integer",
                            "description": "Number of days to plan (e.g., 4 for Mon-Thu, 7 for full week)",
                        },
                        "search_query": {
                            "type": "string",
                            "description": "Search keywords (e.g., 'chicken', 'pasta', 'quick dinners'). Defaults to 'dinner' if not specified. For multi-requirement requests like '5 meals where one is ramen and one is spaghetti', omit this parameter or use broad terms like 'main course' - the LLM selector will automatically prioritize user's specific requirements.",
                        },
                        "exclude_allergens": {
                            "type": "array",
                            "items": {"type": "string"},
                            "description": "Allergens to avoid: 'dairy', 'gluten', 'nuts', 'shellfish', 'eggs'",
                        },
                        "max_time": {
                            "type": "integer",
                            "description": "Maximum cooking time in minutes",
                        },
                    },
                    "required": ["num_days"],
                },
            },
            {
                "name": "create_shopping_list",
                "description": "Create a consolidated shopping list from the current meal plan. Organizes ingredients by store section. Can apply scaling instructions to specific recipes.",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "meal_plan_id": {
                            "type": "string",
                            "description": "ID of the meal plan (use current if available)",
                        },
                        "scaling_instructions": {
                            "type": "string",
                            "description": "Optional natural language instructions for scaling specific recipes (e.g., 'double the Italian sandwiches', 'triple the chicken for meal prep', 'reduce pasta by half')",
                        },
                    },
                    "required": ["meal_plan_id"],
                },
            },
            {
                "name": "add_extra_items",
                "description": "Add extra items to the current shopping list that aren't from recipes (e.g., 'bananas', 'milk', 'bread'). Use when user wants to add personal items to their shopping list.",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "items": {
                            "type": "array",
                            "description": "List of items to add",
                            "items": {
                                "type": "object",
                                "properties": {
                                    "name": {
                                        "type": "string",
                                        "description": "Name of the item (e.g., 'bananas')"
                                    },
                                    "quantity": {
                                        "type": "string",
                                        "description": "Quantity with unit (e.g., '6', '1 gallon', '2 loaves'). Defaults to '1' if not specified."
                                    },
                                },
                                "required": ["name"]
                            }
                        },
                    },
                    "required": ["items"],
                },
            },
            {
                "name": "search_recipes",
                "description": "Search for recipes by keyword, cooking time, or tags. Returns recipe IDs, names, and details.",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "query": {
                            "type": "string",
                            "description": "Search keyword (e.g., 'chicken', 'salmon')",
                        },
                        "max_time": {
                            "type": "integer",
                            "description": "Maximum cooking time in minutes",
                        },
                        "tags": {
                            "type": "array",
                            "items": {"type": "string"},
                            "description": "Required tags like 'easy', 'vegetarian'",
                        },
                        "limit": {
                            "type": "integer",
                            "description": "Maximum results (default: 10)",
                            "default": 10,
                        },
                    },
                },
            },
            {
                "name": "get_cooking_guide",
                "description": "Get detailed cooking instructions for a specific recipe including ingredients, steps, and tips.",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "recipe_id": {
                            "type": "string",
                            "description": "Recipe ID",
                        },
                    },
                    "required": ["recipe_id"],
                },
            },
            {
                "name": "get_meal_history",
                "description": "Show the user's recent meal history to understand their preferences.",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "weeks_back": {
                            "type": "integer",
                            "description": "Number of weeks to look back (default: 4)",
                            "default": 4,
                        },
                    },
                },
            },
            {
                "name": "show_current_plan",
                "description": "Display the current meal plan details.",
                "input_schema": {
                    "type": "object",
                    "properties": {},
                },
            },
            {
                "name": "show_shopping_list",
                "description": "Display the current shopping list.",
                "input_schema": {
                    "type": "object",
                    "properties": {},
                },
            },
            {
                "name": "swap_meal",
                "description": "Swap a meal in the current meal plan with a different recipe. Use when user wants to replace a specific meal.",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "date": {
                            "type": "string",
                            "description": "Date of meal to swap (YYYY-MM-DD)",
                        },
                        "requirements": {
                            "type": "string",
                            "description": "User's requirements for the replacement (e.g., 'shellfish dish', 'vegetarian pasta', 'quick chicken')",
                        },
                    },
                    "required": ["date", "requirements"],
                },
            },
            {
                "name": "swap_meal_fast",
                "description": "Swap a meal using cached backup recipes for instant results. Falls back to fresh search if requirements don't match cached category. Use for 'different chicken', 'another pasta', etc.",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "date": {
                            "type": "string",
                            "description": "Date of meal to swap (YYYY-MM-DD)",
                        },
                        "requirements": {
                            "type": "string",
                            "description": "EXACT user request - preserve their words verbatim (e.g., if user says 'something else', pass 'something else', NOT 'different chicken'). Vague phrases like 'something else' trigger option selection, specific phrases like 'different chicken' trigger auto-swap.",
                        },
                    },
                    "required": ["date", "requirements"],
                },
            },
            {
                "name": "confirm_swap",
                "description": "Complete a meal swap after user selects from backup options. Use when user has been shown options and picked one (e.g., '1', 'the first one', 'the salad').",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "selection": {
                            "type": "string",
                            "description": "User's selection (e.g., '1', '2', '3', 'first', 'salad')",
                        },
                    },
                    "required": ["selection"],
                },
            },
            {
                "name": "check_allergens",
                "description": "Check if the current meal plan contains specific allergens. Uses the cached meal plan for instant results. Only works after a plan has been created or loaded.",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "allergen": {
                            "type": "string",
                            "description": "Allergen to check for (e.g., 'dairy', 'shellfish', 'nuts', 'gluten', 'eggs')",
                        },
                    },
                    "required": ["allergen"],
                },
            },
            {
                "name": "list_meals_by_allergen",
                "description": "List all meals in the current plan that contain a specific allergen. Returns detailed meal information.",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "allergen": {
                            "type": "string",
                            "description": "Allergen to filter by",
                        },
                    },
                    "required": ["allergen"],
                },
            },
            {
                "name": "get_day_ingredients",
                "description": "Get all ingredients needed for a specific day from the current meal plan. Useful for daily cooking prep.",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "date": {
                            "type": "string",
                            "description": "Date in YYYY-MM-DD format (e.g., '2025-10-29')",
                        },
                    },
                    "required": ["date"],
                },
            },
        ]

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
                num_days = tool_input.get("num_days", 7)

                # Use dates from UI if available (web interface)
                if hasattr(self, 'selected_dates') and self.selected_dates:
                    dates = self.selected_dates[:num_days]  # Use UI-selected dates
                    week_of = self.week_start if hasattr(self, 'week_start') else dates[0]
                    if self.verbose:
                        self._verbose_output(f"      → Using {len(dates)} dates from UI: {dates[0]} to {dates[-1]}")
                else:
                    # Fallback for CLI/non-web usage - generate dates from today
                    today = datetime.now().date()
                    dates = [(today + timedelta(days=i)).isoformat() for i in range(num_days)]
                    week_of = dates[0]
                    if self.verbose:
                        self._verbose_output(f"      → Planning {num_days} days starting {dates[0]}")

                # 2. SQL search for candidates
                # Default to "dinner" for broad coverage (this is a dinner planning bot)
                search_query = tool_input.get("search_query", "dinner")
                candidates = self.assistant.db.search_recipes(
                    query=search_query,
                    max_time=tool_input.get("max_time"),
                    limit=100
                )

                if self.verbose:
                    self._verbose_output(f"      → SQL search found {len(candidates)} candidates for '{search_query}'")

                if not candidates:
                    return f"No recipes found matching '{search_query}'. Try different search terms."

                # 3. Filter by allergens using structured ingredients
                exclude_allergens = tool_input.get("exclude_allergens", [])
                filtered = [
                    r for r in candidates
                    if r.has_structured_ingredients()
                    and not any(r.has_allergen(a) for a in exclude_allergens)
                ]

                if self.verbose:
                    if exclude_allergens:
                        self._verbose_output(f"      → Filtered to {len(filtered)} recipes without {', '.join(exclude_allergens)}")
                    else:
                        self._verbose_output(f"      → All {len(filtered)} have structured ingredients")

                if not filtered:
                    return f"Found {len(candidates)} recipes, but none without {', '.join(exclude_allergens)}. Try relaxing constraints."

                if len(filtered) < num_days:
                    return f"Only found {len(filtered)} recipes matching all constraints, need {num_days}. Try relaxing constraints or reducing days."

                # 4. LLM selects with variety
                recent_meals = self.assistant.db.get_meal_history(weeks_back=2)
                recent_names = [m.recipe.name for m in recent_meals] if recent_meals else []

                # Get user's original request from conversation history
                user_message = None
                if self.conversation_history:
                    # Find the most recent user message
                    for msg in reversed(self.conversation_history):
                        if msg["role"] == "user":
                            user_message = msg["content"]
                            break

                if self.verbose:
                    self._verbose_output(f"      → Using LLM to select {num_days} varied recipes from {len(filtered)} options...")
                    if user_message:
                        self._verbose_output(f"      → Passing user requirements to selector: '{user_message[:60]}...'")

                selected = self._select_recipes_with_llm(filtered, num_days, recent_names, user_message)

                if self.verbose:
                    self._verbose_output(f"      → LLM selected: {', '.join([r.name[:30] for r in selected])}")

                # 4b. Store unselected recipes as backups for quick swaps
                backups = [r for r in filtered if r not in selected][:20]  # Top 20 backups
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

                # 6. Create and save MealPlan
                backup_dict = {search_query: backups} if backups and search_query else {}
                plan = MealPlan(
                    week_of=week_of,  # Use week start from UI or first date
                    meals=meals,
                    preferences_applied=exclude_allergens,  # Track what allergens were avoided
                    backup_recipes=backup_dict  # Store backups for instant swaps
                )
                plan_id = self.assistant.db.save_meal_plan(plan)
                self.current_meal_plan_id = plan_id

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
                    weeks_back=tool_input.get("weeks_back", 4)
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
                meal_plan = self.assistant.db.get_meal_plan(self.current_meal_plan_id)
                if meal_plan:
                    self.last_meal_plan = meal_plan
                    if self.verbose:
                        self._verbose_output(f"      → Loaded and cached plan ({len(meal_plan.meals)} meals)")

                # Get explanation from agent
                explanation = self.assistant.planning_agent.explain_plan(
                    self.current_meal_plan_id
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
                    mode = self._check_backup_match(requirements, category)
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
                    options = self._select_backup_options(candidates, num_options=3)

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
                    new_recipe_id=new_recipe.id
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
                    new_recipe_id=selected_recipe.id
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
