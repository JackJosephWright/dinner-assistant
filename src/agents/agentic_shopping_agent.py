"""
LLM-Powered Shopping Agent using LangGraph.

This agent uses Claude to reason about ingredient consolidation,
replacing the regex-based parsing with true agentic reasoning.
"""

import logging
import os
from typing import Dict, List, Any, Optional, TypedDict
from collections import defaultdict

from langgraph.graph import StateGraph, END
from anthropic import Anthropic

import sys
from pathlib import Path

# Add src to path if needed
if __name__ == "__main__":
    sys.path.insert(0, str(Path(__file__).parent.parent))

from data.database import DatabaseInterface
from data.models import GroceryList, GroceryItem

logger = logging.getLogger(__name__)


class ShoppingState(TypedDict):
    """State for the shopping agent."""
    meal_plan_id: str
    week_of: str

    # Collected ingredients
    raw_ingredients: List[Dict[str, Any]]  # List of {ingredient: str, recipe: str}

    # LLM consolidation results
    consolidated_items: List[Dict[str, Any]]  # List of consolidated grocery items

    # Final grocery list
    grocery_list_id: Optional[str]

    # Optional scaling/modification instructions (natural language)
    scaling_instructions: Optional[str]

    # Error handling
    error: Optional[str]


class AgenticShoppingAgent:
    """LLM-powered agent for generating organized grocery lists."""

    def __init__(self, db: DatabaseInterface, api_key: Optional[str] = None):
        """
        Initialize Shopping Agent with LLM.

        Args:
            db: Database interface instance
            api_key: Anthropic API key (or from env)
        """
        self.db = db

        # Initialize Anthropic client
        api_key = api_key or os.environ.get("ANTHROPIC_API_KEY")
        if not api_key:
            raise ValueError(
                "ANTHROPIC_API_KEY required for agentic shopping. "
                "Set environment variable or pass api_key parameter."
            )

        self.client = Anthropic(api_key=api_key)
        # Use Haiku for consolidation (simple structured task, 3-5x faster)
        self.model = "claude-3-5-haiku-20241022"

        # Build the LangGraph workflow
        self.graph = self._build_graph()

        logger.info("Agentic Shopping Agent initialized with LLM")

    def _build_graph(self) -> StateGraph:
        """Build the LangGraph state graph for shopping workflow."""

        workflow = StateGraph(ShoppingState)

        # Add nodes
        workflow.add_node("collect_ingredients", self._collect_ingredients_node)
        workflow.add_node("consolidate_with_llm", self._consolidate_with_llm_node)
        workflow.add_node("save_list", self._save_list_node)

        # Define edges
        workflow.set_entry_point("collect_ingredients")
        workflow.add_edge("collect_ingredients", "consolidate_with_llm")
        workflow.add_edge("consolidate_with_llm", "save_list")
        workflow.add_edge("save_list", END)

        return workflow.compile()

    def create_grocery_list(
        self,
        meal_plan_id: str,
        scaling_instructions: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Create a grocery list from a meal plan using LLM reasoning.

        Args:
            meal_plan_id: ID of the meal plan
            scaling_instructions: Optional natural language instructions for scaling
                                 specific recipes (e.g., "double the Italian sandwiches")

        Returns:
            Dictionary with grocery list results
        """
        try:
            # Get meal plan to get week_of
            meal_plan = self.db.get_meal_plan(meal_plan_id)
            if not meal_plan:
                return {
                    "success": False,
                    "error": "Meal plan not found"
                }

            # Initialize state
            initial_state = ShoppingState(
                meal_plan_id=meal_plan_id,
                week_of=meal_plan.week_of,
                raw_ingredients=[],
                consolidated_items=[],
                grocery_list_id=None,
                scaling_instructions=scaling_instructions,
                error=None,
            )

            # Run the graph
            final_state = self.graph.invoke(initial_state)

            # Check for errors
            if final_state.get("error"):
                return {
                    "success": False,
                    "error": final_state["error"],
                }

            # Get the saved grocery list for full details
            grocery_list = self.db.get_grocery_list(final_state["grocery_list_id"])

            logger.info(f"Created grocery list {final_state['grocery_list_id']} with {len(final_state['consolidated_items'])} items using LLM")

            return {
                "success": True,
                "grocery_list_id": final_state["grocery_list_id"],
                "num_items": len(final_state["consolidated_items"]),
                "items": [item.to_dict() for item in grocery_list.items],
                "store_sections": {
                    section: [item.to_dict() for item in items]
                    for section, items in grocery_list.store_sections.items()
                },
            }

        except Exception as e:
            logger.error(f"Error creating grocery list: {e}", exc_info=True)
            return {
                "success": False,
                "error": str(e),
            }

    def _collect_ingredients_node(self, state: ShoppingState) -> ShoppingState:
        """
        LangGraph node: Collect all ingredients from meal plan recipes.

        Uses cached recipes from meal plan (ZERO DB queries!) instead of re-fetching.
        """
        try:
            meal_plan = self.db.get_meal_plan(state["meal_plan_id"])
            if not meal_plan:
                state["error"] = "Meal plan not found"
                return state

            raw_ingredients = []

            for planned_meal in meal_plan.meals:
                # Use cached recipe (ZERO DB queries!)
                recipe = meal_plan.recipes_cache.get(planned_meal.recipe_id)

                # Fallback to DB query if cache is empty (backward compatibility)
                if not recipe:
                    logger.warning(f"Recipe {planned_meal.recipe_id} not in cache, fetching from DB")
                    recipe = self.db.get_recipe(planned_meal.recipe_id)
                    if not recipe:
                        continue

                for ingredient_raw in recipe.ingredients_raw:
                    raw_ingredients.append({
                        "ingredient": ingredient_raw,
                        "recipe": planned_meal.recipe_name,
                    })

            state["raw_ingredients"] = raw_ingredients
            logger.info(f"Collected {len(raw_ingredients)} raw ingredients from {len(meal_plan.meals)} recipes (using cache)")

            return state

        except Exception as e:
            logger.error(f"Error in collect_ingredients_node: {e}")
            state["error"] = f"Ingredient collection failed: {str(e)}"
            return state

    def _consolidate_with_llm_node(self, state: ShoppingState) -> ShoppingState:
        """
        LangGraph node: Use LLM to intelligently consolidate ingredients.

        The LLM handles:
        - Parsing quantities and units
        - Merging similar ingredients (e.g., "2 cups flour" + "1 cup flour" = "3 cups flour")
        - Categorizing by store section
        - Handling different units intelligently
        - Applying scaling instructions (e.g., "double the Italian sandwiches")
        """
        try:
            raw_ingredients = state["raw_ingredients"]

            if not raw_ingredients:
                state["error"] = "No ingredients to consolidate"
                return state

            # Format ingredients for LLM
            ingredients_text = ""
            for i, item in enumerate(raw_ingredients, 1):
                ingredients_text += f"{i}. {item['ingredient']} (from: {item['recipe']})\n"

            # Check for scaling instructions
            scaling_instructions = state.get("scaling_instructions", "")
            scaling_note = ""
            if scaling_instructions:
                scaling_note = f"""

**IMPORTANT SCALING INSTRUCTIONS:**
{scaling_instructions}

Please apply these scaling instructions to the relevant recipes when consolidating.
For example, if asked to "double the Italian sandwiches", multiply all ingredient
quantities from that recipe by 2 before consolidating with other ingredients.
"""

            # Ask LLM to consolidate (optimized: shorter prompt, fewer tokens)
            prompt = f"""Consolidate these recipe ingredients into a shopping list:

{ingredients_text}{scaling_note}

Merge duplicates, normalize names, categorize by store section (produce/meat/seafood/dairy/pantry/frozen/bakery/other).

Output format (one per line):
ITEM_NAME | QUANTITY | CATEGORY | RECIPES

Example:
flour | 3 cups | pantry | Pancakes, Cookies
chicken breast | 1.5 lbs | meat | Stir Fry
onions | 2 medium | produce | Stir Fry, Pasta"""

            response = self.client.messages.create(
                model=self.model,  # Haiku (3-5x faster than Sonnet)
                max_tokens=1024,  # Reduced from 2048 for faster response
                messages=[{"role": "user", "content": prompt}]
            )

            consolidation_text = response.content[0].text
            logger.info(f"LLM consolidation completed")

            # Parse LLM output
            consolidated_items = []

            for line in consolidation_text.split("\n"):
                line = line.strip()

                # Skip empty lines and non-data lines
                if not line or "|" not in line:
                    continue

                # Skip header-like lines
                if "ITEM_NAME" in line or "----" in line:
                    continue

                parts = [p.strip() for p in line.split("|")]

                if len(parts) < 4:
                    continue

                item_name = parts[0]
                quantity = parts[1]
                category = parts[2].lower()
                recipes_str = parts[3]

                # Parse recipe sources
                recipe_sources = [r.strip() for r in recipes_str.split(",")]

                consolidated_items.append({
                    "name": item_name,
                    "quantity": quantity,
                    "category": category,
                    "recipe_sources": recipe_sources,
                })

            state["consolidated_items"] = consolidated_items
            logger.info(f"Consolidated into {len(consolidated_items)} unique items")

            return state

        except Exception as e:
            logger.error(f"Error in consolidate_with_llm_node: {e}")
            state["error"] = f"Consolidation failed: {str(e)}"
            return state

    def _save_list_node(self, state: ShoppingState) -> ShoppingState:
        """
        LangGraph node: Save the consolidated grocery list to database.
        """
        try:
            consolidated_items = state["consolidated_items"]

            if not consolidated_items:
                state["error"] = "No consolidated items to save"
                return state

            # Create GroceryItem objects
            grocery_items = []

            for item_data in consolidated_items:
                notes = None
                if len(item_data["recipe_sources"]) > 1:
                    notes = f"Needed for {len(item_data['recipe_sources'])} recipes"

                item = GroceryItem(
                    name=item_data["name"].title(),
                    quantity=item_data["quantity"],
                    category=item_data["category"],
                    recipe_sources=item_data["recipe_sources"],
                    notes=notes,
                )

                grocery_items.append(item)

            # Create grocery list
            grocery_list = GroceryList(
                week_of=state["week_of"],
                items=grocery_items,
            )

            # Save to database
            list_id = self.db.save_grocery_list(grocery_list)

            state["grocery_list_id"] = list_id
            logger.info(f"Saved grocery list {list_id} with {len(grocery_items)} items")

            return state

        except Exception as e:
            logger.error(f"Error in save_list_node: {e}")
            state["error"] = f"Save failed: {str(e)}"
            return state

    def format_shopping_list(self, grocery_list_id: str) -> str:
        """
        Format a grocery list for display using LLM for friendly presentation.

        Args:
            grocery_list_id: ID of the grocery list

        Returns:
            Formatted shopping list string
        """
        grocery_list = self.db.get_grocery_list(grocery_list_id)

        if not grocery_list:
            return "Grocery list not found."

        # Format items by section for LLM
        sections_text = ""
        for section, items in sorted(grocery_list.store_sections.items()):
            sections_text += f"\n{section.upper()}:\n"
            for item in items:
                recipes = ", ".join(item.recipe_sources[:2])
                if len(item.recipe_sources) > 2:
                    recipes += f", +{len(item.recipe_sources) - 2} more"
                sections_text += f"  - {item.name}: {item.quantity} (for: {recipes})\n"

        # Ask LLM to format nicely
        try:
            prompt = f"""You are a shopping assistant. Please format this grocery list in a friendly, easy-to-read way.

Shopping List for Week of {grocery_list.week_of}
Total Items: {len(grocery_list.items)}

Items by Section:
{sections_text}

Please create a well-formatted shopping list with:
1. Clear section headers
2. Checkboxes (☐) for each item
3. Brief notes about which recipes need each item
4. A friendly, organized layout

Keep it concise and scannable for grocery shopping."""

            response = self.client.messages.create(
                model=self.model,
                max_tokens=2048,
                messages=[{"role": "user", "content": prompt}]
            )

            formatted_list = response.content[0].text

            return formatted_list

        except Exception as e:
            logger.error(f"Error formatting with LLM: {e}")

            # Fallback to simple format
            lines = [
                f"Shopping List for Week of {grocery_list.week_of}",
                f"{'='*60}",
                f"\nTotal Items: {len(grocery_list.items)}",
                "",
            ]

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
