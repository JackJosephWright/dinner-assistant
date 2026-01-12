"""
Tool configuration and definitions for the meal planning chatbot.

Extracted from chatbot.py - contains tool schemas and system prompt generation.
"""

from typing import Dict, List, Any, Optional
from datetime import datetime


def build_system_prompt(
    current_meal_plan_id: Optional[str],
    current_shopping_list_id: Optional[str],
    last_meal_plan: Optional[Any],
    selected_dates: Optional[List[str]] = None,
) -> str:
    """
    Build the system prompt for the LLM.

    Args:
        current_meal_plan_id: Current meal plan ID if any
        current_shopping_list_id: Current shopping list ID if any
        last_meal_plan: The last meal plan object (with meals list)
        selected_dates: List of dates selected by user from UI (YYYY-MM-DD format)

    Returns:
        System prompt string for the LLM
    """
    context = []
    if current_meal_plan_id:
        context.append(f"Current meal plan ID: {current_meal_plan_id}")
    if current_shopping_list_id:
        context.append(f"Current shopping list ID: {current_shopping_list_id}")

    # Add selected dates context - this tells the LLM it can immediately call plan_meals_smart
    if selected_dates:
        dates_with_days = []
        for date_str in selected_dates:
            try:
                dt = datetime.fromisoformat(date_str)
                dates_with_days.append(f"{date_str} ({dt.strftime('%A')})")
            except ValueError:
                dates_with_days.append(date_str)
        context.append(f"User has selected these dates for planning: {', '.join(dates_with_days)}")
        context.append(f"Number of days to plan: {len(selected_dates)}")

    context_str = "\n".join(context) if context else "No active plans yet."

    # Add meal plan date mapping for interpreting day references
    meal_plan_dates_context = ""
    if last_meal_plan and last_meal_plan.meals:
        meal_plan_dates_context = "\n\nCurrent meal plan dates:\n"
        for i, meal in enumerate(last_meal_plan.meals, 1):
            # Handle both datetime objects and string dates
            if isinstance(meal.date, str):
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
- IMMEDIATELY call plan_meals_smart to create the plan - don't search first
- If "User has selected these dates for planning" appears in Current context, DO NOT ask how many days - just call plan_meals_smart immediately (it will use those dates)
- ALWAYS use plan_meals_smart (never use plan_meals or search_recipes for planning)
- For CUISINE-SPECIFIC requests (e.g., "French meals", "Italian week", "Asian dishes"):
  * Call plan_meals_smart DIRECTLY with the cuisine as search_query
  * Example: "week of French meals" → plan_meals_smart(num_days=7, search_query="French")
  * Example: "5 Italian dinners" → plan_meals_smart(num_days=5, search_query="Italian")
  * Example: "Asian recipes" → plan_meals_smart(num_days=7, search_query="Asian")
  * DO NOT use search_recipes first - go straight to plan_meals_smart
- For MULTI-REQUIREMENT requests (e.g., "5 meals where one is ramen and one is spaghetti"):
  * Use plan_meals_smart WITHOUT specifying search_query (defaults to "dinner" for broad coverage)
  * Or use BROAD search_query like "main course" if you want to be explicit
  * The LLM selector automatically prioritizes user's specific requirements
  * DO NOT create generic plan + multiple swaps (inefficient - wastes 5-10 LLM calls)
  * Example: User wants "5 meals, one ramen, one pasta" → call plan_meals_smart(num_days=5) [search_query defaults to "dinner"]

CRITICAL: After creating a plan, STOP and present it to the user. Do NOT automatically swap meals or "improve" the plan. Only swap when the user EXPLICITLY asks to change a meal.

IMPORTANT: When plan_meals_smart returns JSON with "status": "complete", the plan is SAVED and ready. Present the meals list to the user in a friendly format. Do NOT call plan_meals_smart again - the plan is already created and saved.

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

Working with favorites:
- Use show_favorites when user asks "what are my favorites?" or "show saved recipes"
- Use add_favorite when user wants to star a recipe (from current plan or search results)
- Use remove_favorite to unstar a recipe
- Favorites are automatically considered when generating meal plans - you don't need to explicitly ask
- The planning system may include 1-2 favorites naturally when they fit the request

IMPORTANT: Keep responses SHORT and to the point. Users want speed over lengthy explanations. Confirm actions with 1-2 sentences max. BUT ALWAYS answer the user's actual question based on tool results."""


# Tool definitions - static configuration
TOOL_DEFINITIONS: List[Dict[str, Any]] = [
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
    # Recipe Variants v0 tools
    {
        "name": "modify_recipe",
        "description": "Modify a recipe in the current meal plan (e.g., 'use halibut instead of cod', 'make it dairy-free', 'double the garlic'). Creates a variant that persists and updates shopping list. Use for ingredient swaps, additions, removals, or scaling.",
        "input_schema": {
            "type": "object",
            "properties": {
                "date": {
                    "type": "string",
                    "description": "Date of the meal to modify (YYYY-MM-DD)",
                },
                "modification": {
                    "type": "string",
                    "description": "What to change (e.g., 'replace cod with halibut', 'remove the dairy', 'add extra garlic')",
                },
            },
            "required": ["date", "modification"],
        },
    },
    {
        "name": "clear_recipe_modifications",
        "description": "Remove all modifications from a recipe, reverting it to the original version.",
        "input_schema": {
            "type": "object",
            "properties": {
                "date": {
                    "type": "string",
                    "description": "Date of the meal to revert (YYYY-MM-DD)",
                },
            },
            "required": ["date"],
        },
    },
    # Favorites tools
    {
        "name": "show_favorites",
        "description": "Show user's favorite recipes (starred and auto-learned from 5-star ratings). Use when user asks 'what are my favorites?', 'show my saved recipes', or 'list favorites'.",
        "input_schema": {
            "type": "object",
            "properties": {
                "limit": {
                    "type": "integer",
                    "description": "Maximum number of favorites to show (default: 10)",
                    "default": 10,
                },
            },
        },
    },
    {
        "name": "add_favorite",
        "description": "Star a recipe as a favorite. Use when user says 'save this recipe', 'add to favorites', 'star this', or 'favorite this'. Can add from current meal plan or search results.",
        "input_schema": {
            "type": "object",
            "properties": {
                "recipe_id": {
                    "type": "string",
                    "description": "Recipe ID to star (from current plan or search results)",
                },
                "recipe_name": {
                    "type": "string",
                    "description": "Recipe name (for display)",
                },
            },
            "required": ["recipe_id", "recipe_name"],
        },
    },
    {
        "name": "remove_favorite",
        "description": "Remove a recipe from favorites. Use when user says 'unstar', 'remove from favorites', or 'unfavorite'.",
        "input_schema": {
            "type": "object",
            "properties": {
                "recipe_id": {
                    "type": "string",
                    "description": "Recipe ID to unstar",
                },
            },
            "required": ["recipe_id"],
        },
    },
]


def get_tools() -> List[Dict[str, Any]]:
    """Get the tool definitions list."""
    return TOOL_DEFINITIONS
