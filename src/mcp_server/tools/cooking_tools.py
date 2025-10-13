"""
Cooking tools for the MCP server.

These tools enable the Cooking Agent to provide recipe guidance,
substitutions, and timing help.
"""

import logging
from typing import List, Optional, Dict, Any

from data.database import DatabaseInterface

logger = logging.getLogger(__name__)


class CookingTools:
    """Cooking-related tools for recipe guidance."""

    def __init__(self, db: DatabaseInterface):
        """
        Initialize cooking tools.

        Args:
            db: Database interface instance
        """
        self.db = db

        # Common ingredient substitutions
        self.substitutions = {
            "butter": ["margarine", "coconut oil", "olive oil"],
            "milk": ["almond milk", "soy milk", "oat milk"],
            "eggs": ["flax eggs", "chia eggs", "applesauce"],
            "cream": ["coconut cream", "cashew cream"],
            "sour cream": ["greek yogurt", "coconut cream"],
            "chicken": ["turkey", "tofu", "tempeh"],
            "beef": ["ground turkey", "lentils", "mushrooms"],
            "fish": ["tofu", "chicken"],
            "pasta": ["zucchini noodles", "spaghetti squash"],
            "rice": ["quinoa", "cauliflower rice"],
            "flour": ["almond flour", "coconut flour", "gluten-free flour"],
        }

    def get_recipe_with_guidance(self, recipe_id: str) -> Optional[Dict[str, Any]]:
        """
        Get recipe with step-by-step guidance.

        Args:
            recipe_id: Recipe ID

        Returns:
            Recipe with guidance information
        """
        try:
            recipe = self.db.get_recipe(recipe_id)
            if not recipe:
                return None

            # Add guidance information
            guidance = {
                "recipe": recipe.to_dict(),
                "total_steps": len(recipe.steps),
                "estimated_time": recipe.estimated_time,
                "tips": self._generate_tips(recipe),
                "prep_steps": self._extract_prep_steps(recipe),
                "cooking_steps": self._extract_cooking_steps(recipe),
            }

            return guidance

        except Exception as e:
            logger.error(f"Error getting recipe guidance: {e}")
            return None

    def suggest_substitution(
        self, ingredient: str, reason: Optional[str] = None
    ) -> List[str]:
        """
        Suggest substitutions for an ingredient.

        Args:
            ingredient: Ingredient name
            reason: Optional reason for substitution (e.g., "dairy-free")

        Returns:
            List of substitution suggestions
        """
        ingredient_lower = ingredient.lower()

        # Find matching substitutions
        suggestions = []

        for key, subs in self.substitutions.items():
            if key in ingredient_lower:
                suggestions.extend(subs)

        # If no direct match, provide general suggestions
        if not suggestions:
            if "meat" in ingredient_lower or "chicken" in ingredient_lower or "beef" in ingredient_lower:
                suggestions = ["tofu", "tempeh", "lentils", "mushrooms"]
            elif "dairy" in ingredient_lower or "milk" in ingredient_lower or "cheese" in ingredient_lower:
                suggestions = ["plant-based alternatives", "nut-based alternatives"]

        return suggestions[:3]  # Return top 3

    def calculate_timing(self, recipe_id: str) -> Dict[str, Any]:
        """
        Calculate timing breakdown for a recipe.

        Args:
            recipe_id: Recipe ID

        Returns:
            Timing information
        """
        try:
            recipe = self.db.get_recipe(recipe_id)
            if not recipe:
                return {"success": False, "error": "Recipe not found"}

            # Estimate prep vs cook time
            total_time = recipe.estimated_time or 30

            # Heuristic: 30% prep, 70% cooking
            prep_time = int(total_time * 0.3)
            cook_time = int(total_time * 0.7)

            return {
                "success": True,
                "total_time": total_time,
                "prep_time": prep_time,
                "cook_time": cook_time,
                "steps": [
                    {
                        "step_num": i + 1,
                        "description": step[:100] + "..." if len(step) > 100 else step,
                        "estimated_minutes": max(5, total_time // len(recipe.steps)),
                    }
                    for i, step in enumerate(recipe.steps)
                ],
            }

        except Exception as e:
            logger.error(f"Error calculating timing: {e}")
            return {"success": False, "error": str(e)}

    def _generate_tips(self, recipe) -> List[str]:
        """Generate helpful cooking tips."""
        tips = []

        # Based on difficulty
        if recipe.difficulty == "hard":
            tips.append("⏰ This is an advanced recipe - read through all steps first")

        # Based on time
        if recipe.estimated_time and recipe.estimated_time > 60:
            tips.append("🕐 Long cooking time - plan ahead")

        # Based on ingredients
        if any("fresh" in ing.lower() for ing in recipe.ingredients):
            tips.append("🌿 Fresh ingredients recommended for best flavor")

        return tips

    def _extract_prep_steps(self, recipe) -> List[str]:
        """Extract preparation steps."""
        prep_keywords = ["chop", "dice", "mince", "slice", "peel", "wash", "measure"]
        prep_steps = []

        for step in recipe.steps:
            if any(keyword in step.lower() for keyword in prep_keywords):
                prep_steps.append(step)

        return prep_steps

    def _extract_cooking_steps(self, recipe) -> List[str]:
        """Extract cooking steps."""
        cook_keywords = ["cook", "bake", "fry", "boil", "simmer", "roast", "grill", "heat"]
        cook_steps = []

        for step in recipe.steps:
            if any(keyword in step.lower() for keyword in cook_keywords):
                cook_steps.append(step)

        return cook_steps


# Tool definitions for MCP registration
COOKING_TOOL_DEFINITIONS = [
    {
        "name": "get_recipe_with_guidance",
        "description": (
            "Get full recipe details with step-by-step guidance, "
            "tips, and timing estimates."
        ),
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
        "name": "suggest_substitution",
        "description": (
            "Suggest ingredient substitutions for dietary restrictions "
            "or ingredient availability."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "ingredient": {
                    "type": "string",
                    "description": "Ingredient name",
                },
                "reason": {
                    "type": "string",
                    "description": "Optional reason (e.g., 'dairy-free', 'vegan')",
                },
            },
            "required": ["ingredient"],
        },
    },
    {
        "name": "calculate_timing",
        "description": (
            "Calculate timing breakdown for a recipe with "
            "prep time, cook time, and step estimates."
        ),
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
]
