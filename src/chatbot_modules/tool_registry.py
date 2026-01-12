"""
Tool registry for the meal planning chatbot.

Maps tool names to their handler functions.
Centralizes dispatch logic for auditable tool execution.
"""

from chatbot_modules.tool_handlers import (
    handle_plan_meals,
    handle_plan_meals_smart,
    handle_create_shopping_list,
    handle_add_extra_items,
    handle_search_recipes,
    handle_get_cooking_guide,
    handle_get_meal_history,
    handle_show_current_plan,
    handle_show_shopping_list,
    handle_swap_meal,
    handle_swap_meal_fast,
    handle_confirm_swap,
    handle_check_allergens,
    handle_list_meals_by_allergen,
    handle_get_day_ingredients,
    handle_modify_recipe,
    handle_clear_recipe_modifications,
    # Favorites
    handle_show_favorites,
    handle_add_favorite,
    handle_remove_favorite,
)

# Central registry mapping tool names to handler functions
TOOL_HANDLERS = {
    "plan_meals": handle_plan_meals,
    "plan_meals_smart": handle_plan_meals_smart,
    "create_shopping_list": handle_create_shopping_list,
    "add_extra_items": handle_add_extra_items,
    "search_recipes": handle_search_recipes,
    "get_cooking_guide": handle_get_cooking_guide,
    "get_meal_history": handle_get_meal_history,
    "show_current_plan": handle_show_current_plan,
    "show_shopping_list": handle_show_shopping_list,
    "swap_meal": handle_swap_meal,
    "swap_meal_fast": handle_swap_meal_fast,
    "confirm_swap": handle_confirm_swap,
    "check_allergens": handle_check_allergens,
    "list_meals_by_allergen": handle_list_meals_by_allergen,
    "get_day_ingredients": handle_get_day_ingredients,
    "modify_recipe": handle_modify_recipe,
    "clear_recipe_modifications": handle_clear_recipe_modifications,
    # Favorites
    "show_favorites": handle_show_favorites,
    "add_favorite": handle_add_favorite,
    "remove_favorite": handle_remove_favorite,
}


def execute_tool(chatbot, tool_name: str, tool_input: dict) -> str:
    """
    Execute a tool by name.

    Args:
        chatbot: The MealPlanningChatbot instance
        tool_name: Name of the tool to execute
        tool_input: Dictionary of tool parameters

    Returns:
        String result from the tool execution
    """
    handler = TOOL_HANDLERS.get(tool_name)
    if handler:
        try:
            return handler(chatbot, tool_input)
        except Exception as e:
            return f"Error executing {tool_name}: {str(e)}"
    else:
        return f"Unknown tool: {tool_name}"
