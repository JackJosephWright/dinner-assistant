"""
Shopping tools for the MCP server.

These tools enable the Shopping Agent to generate consolidated grocery lists
from meal plans.
"""

import logging
import re
from typing import List, Optional, Dict, Any
from collections import defaultdict

from data.database import DatabaseInterface
from data.models import GroceryList, GroceryItem

logger = logging.getLogger(__name__)


class ShoppingTools:
    """Shopping-related tools for grocery list generation."""

    def __init__(self, db: DatabaseInterface):
        """
        Initialize shopping tools.

        Args:
            db: Database interface instance
        """
        self.db = db

        # Store sections mapping
        self.category_mappings = {
            # Produce
            "onion": "produce",
            "garlic": "produce",
            "tomato": "produce",
            "lettuce": "produce",
            "spinach": "produce",
            "carrot": "produce",
            "potato": "produce",
            "broccoli": "produce",
            "pepper": "produce",
            "cucumber": "produce",
            "avocado": "produce",
            "lemon": "produce",
            "lime": "produce",
            "cilantro": "produce",
            "parsley": "produce",
            "basil": "produce",
            "mushroom": "produce",
            # Meat & Seafood
            "chicken": "meat",
            "beef": "meat",
            "pork": "meat",
            "turkey": "meat",
            "salmon": "seafood",
            "fish": "seafood",
            "shrimp": "seafood",
            "cod": "seafood",
            "tuna": "seafood",
            "sausage": "meat",
            "ground": "meat",
            # Dairy
            "milk": "dairy",
            "cheese": "dairy",
            "butter": "dairy",
            "cream": "dairy",
            "yogurt": "dairy",
            "sour cream": "dairy",
            "eggs": "dairy",
            # Pantry
            "flour": "pantry",
            "sugar": "pantry",
            "salt": "pantry",
            "pepper": "pantry",
            "oil": "pantry",
            "vinegar": "pantry",
            "rice": "pantry",
            "pasta": "pantry",
            "beans": "pantry",
            "stock": "pantry",
            "broth": "pantry",
            "sauce": "pantry",
            "can": "pantry",
            # Frozen
            "frozen": "frozen",
            # Bakery
            "bread": "bakery",
            "tortilla": "bakery",
            "bun": "bakery",
            "roll": "bakery",
        }

    def consolidate_ingredients(
        self, meal_plan_id: str
    ) -> Dict[str, Any]:
        """
        Consolidate ingredients from a meal plan into a grocery list.

        Args:
            meal_plan_id: ID of the meal plan

        Returns:
            Dictionary with grocery list data
        """
        try:
            # Get meal plan
            meal_plan = self.db.get_meal_plan(meal_plan_id)
            if not meal_plan:
                return {"success": False, "error": "Meal plan not found"}

            # Collect all ingredients
            all_ingredients = defaultdict(list)  # ingredient_name -> [(quantity, recipe_name)]

            for planned_meal in meal_plan.meals:
                recipe = self.db.get_recipe(planned_meal.recipe_id)
                if not recipe:
                    continue

                for ingredient_raw in recipe.ingredients_raw:
                    # Parse ingredient
                    parsed = self._parse_ingredient(ingredient_raw)

                    # Group by normalized name
                    normalized_name = parsed["name"].lower()
                    all_ingredients[normalized_name].append({
                        "quantity": parsed["quantity"],
                        "unit": parsed["unit"],
                        "raw": ingredient_raw,
                        "recipe": planned_meal.recipe_name,
                    })

            # Consolidate similar ingredients
            grocery_items = []

            for ingredient_name, occurrences in all_ingredients.items():
                # Simple consolidation: just list all quantities
                # In a full implementation, this would use LLM to intelligently merge
                quantities = [occ["raw"] for occ in occurrences]
                recipe_sources = list(set([occ["recipe"] for occ in occurrences]))

                # Determine category
                category = self._categorize_ingredient(ingredient_name)

                # If multiple recipes need it, try to consolidate
                if len(occurrences) > 1:
                    consolidated_qty = self._simple_consolidate(occurrences)
                else:
                    consolidated_qty = occurrences[0]["raw"]

                item = GroceryItem(
                    name=ingredient_name.title(),
                    quantity=consolidated_qty,
                    category=category,
                    recipe_sources=recipe_sources,
                    notes=f"Needed for {len(recipe_sources)} recipes" if len(recipe_sources) > 1 else None,
                )

                grocery_items.append(item)

            # Create grocery list
            grocery_list = GroceryList(
                week_of=meal_plan.week_of,
                items=grocery_items,
            )

            # Save to database
            list_id = self.db.save_grocery_list(grocery_list)

            logger.info(f"Created grocery list {list_id} with {len(grocery_items)} items")

            return {
                "success": True,
                "grocery_list_id": list_id,
                "num_items": len(grocery_items),
                "items": [item.to_dict() for item in grocery_items],
                "store_sections": {
                    section: [item.to_dict() for item in items]
                    for section, items in grocery_list.store_sections.items()
                },
            }

        except Exception as e:
            logger.error(f"Error consolidating ingredients: {e}")
            return {"success": False, "error": str(e)}

    def _parse_ingredient(self, ingredient_raw: str) -> Dict[str, str]:
        """
        Parse raw ingredient string into components.

        Args:
            ingredient_raw: e.g., "2 cups diced tomatoes"

        Returns:
            Dict with quantity, unit, and name
        """
        # Simple regex-based parsing
        # Pattern: optional quantity, optional unit, ingredient name
        pattern = r"^\s*([0-9\/\.\s]+)?\s*([a-z]+)?\s+(.+)$"

        match = re.match(pattern, ingredient_raw.lower().strip())

        if match:
            quantity = match.group(1).strip() if match.group(1) else ""
            unit = match.group(2).strip() if match.group(2) else ""
            name = match.group(3).strip()
        else:
            quantity = ""
            unit = ""
            name = ingredient_raw.strip()

        # Clean up name (remove extra words)
        name = re.sub(r"\(.*?\)", "", name)  # Remove parentheses content
        name = name.strip()

        return {
            "quantity": quantity,
            "unit": unit,
            "name": name,
        }

    def _categorize_ingredient(self, ingredient_name: str) -> str:
        """
        Categorize ingredient by store section.

        Args:
            ingredient_name: Normalized ingredient name

        Returns:
            Category/store section name
        """
        ingredient_lower = ingredient_name.lower()

        # Check mappings
        for keyword, category in self.category_mappings.items():
            if keyword in ingredient_lower:
                return category

        # Default to other
        return "other"

    def _simple_consolidate(self, occurrences: List[Dict]) -> str:
        """
        Simple consolidation of quantities.

        In a full implementation, this would use LLM to intelligently merge.
        For now, just list all quantities.

        Args:
            occurrences: List of ingredient occurrences

        Returns:
            Consolidated quantity string
        """
        # If all have same unit, try to add
        quantities = []
        units = set()

        for occ in occurrences:
            qty = occ["quantity"].strip()
            unit = occ["unit"].strip()

            if qty:
                try:
                    # Try to parse as number
                    num = float(qty)
                    quantities.append(num)
                    units.add(unit)
                except (ValueError, TypeError):
                    pass

        # If we can consolidate
        if quantities and len(units) == 1 and len(units) > 0:
            total = sum(quantities)
            unit = list(units)[0]
            return f"{total} {unit}"

        # Otherwise, just list count
        return f"{len(occurrences)}x"

    def get_grocery_list(self, list_id: str) -> Optional[Dict[str, Any]]:
        """
        Retrieve a saved grocery list.

        Args:
            list_id: Grocery list ID

        Returns:
            Grocery list dictionary or None
        """
        try:
            grocery_list = self.db.get_grocery_list(list_id)
            if grocery_list:
                return grocery_list.to_dict()
            return None

        except Exception as e:
            logger.error(f"Error retrieving grocery list {list_id}: {e}")
            return None

    def add_extra_items(
        self,
        grocery_list_id: str,
        items: List[Dict[str, str]]
    ) -> Dict[str, Any]:
        """
        Add extra items to an existing grocery list.

        Args:
            grocery_list_id: ID of the grocery list to update
            items: List of items to add, each with format:
                   {"name": "bananas", "quantity": "6", "category": "produce"}
                   category is optional and will be auto-detected if not provided

        Returns:
            Dictionary with success status and updated grocery list
        """
        try:
            # Get existing grocery list
            grocery_list = self.db.get_grocery_list(grocery_list_id)
            if not grocery_list:
                return {
                    "success": False,
                    "error": "Grocery list not found"
                }

            # Parse and add each item
            added_items = []
            for item_data in items:
                name = item_data.get("name", "").strip()
                quantity = item_data.get("quantity", "1").strip()

                if not name:
                    continue

                # Auto-detect category if not provided
                category = item_data.get("category")
                if not category:
                    category = self._categorize_ingredient(name.lower())

                # Create GroceryItem
                extra_item = GroceryItem(
                    name=name.title(),
                    quantity=quantity,
                    category=category,
                    recipe_sources=["User request"],
                    notes="Extra item (not from recipes)"
                )

                grocery_list.extra_items.append(extra_item)
                added_items.append(extra_item)

                logger.info(f"Added extra item: {name} ({quantity}) to grocery list {grocery_list_id}")

            # Save updated grocery list
            self.db.save_grocery_list(grocery_list)

            return {
                "success": True,
                "grocery_list_id": grocery_list_id,
                "added_items": [item.to_dict() for item in added_items],
                "total_extra_items": len(grocery_list.extra_items),
                "message": f"Added {len(added_items)} extra item(s) to your shopping list"
            }

        except Exception as e:
            logger.error(f"Error adding extra items: {e}", exc_info=True)
            return {
                "success": False,
                "error": str(e)
            }


# Tool definitions for MCP registration
SHOPPING_TOOL_DEFINITIONS = [
    {
        "name": "consolidate_ingredients",
        "description": (
            "Consolidate ingredients from a meal plan into a grocery list. "
            "Merges similar ingredients and organizes by store section."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "meal_plan_id": {
                    "type": "string",
                    "description": "ID of the meal plan to generate list from",
                },
            },
            "required": ["meal_plan_id"],
        },
    },
    {
        "name": "get_grocery_list",
        "description": "Retrieve a saved grocery list by ID.",
        "input_schema": {
            "type": "object",
            "properties": {
                "list_id": {
                    "type": "string",
                    "description": "Grocery list ID",
                },
            },
            "required": ["list_id"],
        },
    },
    {
        "name": "add_extra_items",
        "description": (
            "Add extra items to an existing grocery list that aren't from recipes. "
            "Use this when the user wants to add personal items like 'bananas', 'milk', or 'bread'. "
            "The category will be auto-detected if not provided."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "grocery_list_id": {
                    "type": "string",
                    "description": "ID of the grocery list to add items to",
                },
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
                                "description": "Quantity with unit (e.g., '6', '1 gallon', '2 loaves')"
                            },
                            "category": {
                                "type": "string",
                                "description": "Optional store section (produce/meat/dairy/pantry/bakery/frozen/other)",
                                "enum": ["produce", "meat", "seafood", "dairy", "pantry", "bakery", "frozen", "other"]
                            }
                        },
                        "required": ["name"]
                    }
                },
            },
            "required": ["grocery_list_id", "items"],
        },
    },
]
