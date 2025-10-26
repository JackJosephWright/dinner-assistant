"""
Shopping Agent for grocery list generation.

Takes a meal plan and generates an organized shopping list.
"""

import logging
from typing import Dict, Any, Optional

from data.database import DatabaseInterface
from mcp_server.tools.shopping_tools import ShoppingTools

logger = logging.getLogger(__name__)


class ShoppingAgent:
    """Agent for generating organized grocery lists from meal plans."""

    def __init__(self, db: DatabaseInterface):
        """
        Initialize Shopping Agent.

        Args:
            db: Database interface instance
        """
        self.db = db
        self.tools = ShoppingTools(db)
        logger.info("Shopping Agent initialized")

    def create_grocery_list(self, meal_plan_id: str, scaling_instructions: Optional[str] = None) -> Dict[str, Any]:
        """
        Create a grocery list from a meal plan.

        Args:
            meal_plan_id: ID of the meal plan
            scaling_instructions: Optional scaling instructions (ignored by algorithmic agent)

        Returns:
            Dictionary with grocery list results
        """
        try:
            # Get meal plan
            meal_plan = self.db.get_meal_plan(meal_plan_id)
            if not meal_plan:
                return {
                    "success": False,
                    "error": "Meal plan not found"
                }

            logger.info(f"Creating grocery list for meal plan {meal_plan_id}")

            # Consolidate ingredients
            result = self.tools.consolidate_ingredients(meal_plan_id)

            if not result.get("success"):
                return result

            logger.info(f"Created grocery list with {result['num_items']} items")

            return result

        except Exception as e:
            logger.error(f"Error creating grocery list: {e}", exc_info=True)
            return {
                "success": False,
                "error": str(e),
            }

    def format_shopping_list(self, grocery_list_id: str) -> str:
        """
        Format a grocery list for display.

        Args:
            grocery_list_id: ID of the grocery list

        Returns:
            Formatted shopping list string
        """
        grocery_list = self.db.get_grocery_list(grocery_list_id)

        if not grocery_list:
            return "Grocery list not found."

        lines = [
            f"Shopping List for Week of {grocery_list.week_of}",
            f"{'='*60}",
            f"\nTotal Items: {len(grocery_list.items)}",
            "",
        ]

        # Group by store section
        for section, items in sorted(grocery_list.store_sections.items()):
            lines.append(f"\n{section.upper()}")
            lines.append("-" * 30)

            for item in items:
                checkbox = "☐"
                recipes = ", ".join(item.recipe_sources[:2])
                if len(item.recipe_sources) > 2:
                    recipes += f", +{len(item.recipe_sources) - 2} more"

                lines.append(f"  {checkbox} {item.name} - {item.quantity}")
                lines.append(f"      For: {recipes}")

        return "\n".join(lines)
