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
    user_id: int  # User ID for multi-user support

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
        self.model = "claude-sonnet-4-5-20250929"

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
        scaling_instructions: Optional[str] = None,
        user_id: int = 1,
    ) -> Dict[str, Any]:
        """
        Create a grocery list from a meal plan using LLM reasoning.

        Args:
            meal_plan_id: ID of the meal plan
            scaling_instructions: Optional natural language instructions for scaling
                                 specific recipes (e.g., "double the Italian sandwiches")
            user_id: User ID (defaults to 1 for backward compatibility)

        Returns:
            Dictionary with grocery list results
        """
        try:
            # Get meal plan to get week_of
            meal_plan = self.db.get_meal_plan(meal_plan_id, user_id=user_id)
            if not meal_plan:
                return {
                    "success": False,
                    "error": "Meal plan not found"
                }

            # Initialize state
            initial_state = ShoppingState(
                meal_plan_id=meal_plan_id,
                week_of=meal_plan.week_of,
                user_id=user_id,
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
            grocery_list = self.db.get_grocery_list(final_state["grocery_list_id"], user_id=user_id)

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
        """
        try:
            user_id = state["user_id"]
            meal_plan = self.db.get_meal_plan(state["meal_plan_id"], user_id=user_id)
            if not meal_plan:
                state["error"] = "Meal plan not found"
                return state

            raw_ingredients = []
            variant_count = 0

            for planned_meal in meal_plan.meals:
                # Use effective recipe (compiled variant if exists, else base recipe)
                # This ensures variant modifications appear in shopping list
                recipe = planned_meal.get_effective_recipe()
                if not recipe:
                    continue

                # Track variants for logging
                if planned_meal.has_variant():
                    variant_count += 1
                    logger.info(f"[SHOP] Using variant recipe for {planned_meal.date}: {recipe.name}")

                # Use structured ingredients if available (enriched recipes)
                if recipe.ingredients_structured:
                    for ingredient in recipe.ingredients_structured:
                        # Structured ingredient already has quantity, unit, name, category
                        raw_ingredients.append({
                            "ingredient": f"{ingredient.quantity} {ingredient.unit} {ingredient.name}".strip(),
                            "recipe": recipe.name,
                            "category": ingredient.category,  # Already categorized!
                            "allergens": ingredient.allergens,  # Already tracked!
                        })
                else:
                    # Fallback to raw ingredients for non-enriched recipes
                    for ingredient_raw in recipe.ingredients_raw:
                        raw_ingredients.append({
                            "ingredient": ingredient_raw,
                            "recipe": recipe.name,
                        })

            state["raw_ingredients"] = raw_ingredients
            enriched_count = sum(1 for m in meal_plan.meals if m.recipe and m.recipe.ingredients_structured)
            logger.info(f"Collected {len(raw_ingredients)} ingredients from {len(meal_plan.meals)} recipes ({enriched_count} enriched, {variant_count} variants)")

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
            # For enriched recipes with categories, include them to guide LLM
            ingredients_text = ""
            has_categories = any("category" in item for item in raw_ingredients)

            for i, item in enumerate(raw_ingredients, 1):
                if "category" in item and item["category"]:
                    # Enriched ingredient with pre-assigned category
                    ingredients_text += f"{i}. {item['ingredient']} [{item['category']}] (from: {item['recipe']})\n"
                else:
                    # Non-enriched ingredient - LLM will categorize
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
            category_note = ""
            if has_categories:
                category_note = "\n\nNote: Some ingredients already have categories [in brackets] - use those categories."

            prompt = f"""Consolidate these recipe ingredients into a shopping list:

{ingredients_text}{category_note}{scaling_note}

Merge duplicates, normalize names, categorize by store section (produce/meat/seafood/dairy/pantry/frozen/bakery/other).

Output format (one per line):
ITEM_NAME | QUANTITY | CATEGORY | RECIPES

Example:
flour | 3 cups | pantry | Pancakes, Cookies
chicken breast | 1.5 lbs | meat | Stir Fry
onions | 2 medium | produce | Stir Fry, Pasta"""

            response = self.client.messages.create(
                model=self.model,
                max_tokens=2048,  # Reduced from 4096 for faster response
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
            user_id = state["user_id"]
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
            list_id = self.db.save_grocery_list(grocery_list, user_id=user_id)

            state["grocery_list_id"] = list_id
            logger.info(f"Saved grocery list {list_id} with {len(grocery_items)} items")

            return state

        except Exception as e:
            logger.error(f"Error in save_list_node: {e}")
            state["error"] = f"Save failed: {str(e)}"
            return state

    def format_shopping_list(self, grocery_list_id: str, user_id: int = 1) -> str:
        """
        Format a grocery list for display using LLM for friendly presentation.

        Args:
            grocery_list_id: ID of the grocery list
            user_id: User ID (defaults to 1 for backward compatibility)

        Returns:
            Formatted shopping list string
        """
        grocery_list = self.db.get_grocery_list(grocery_list_id, user_id=user_id)

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
