"""
Cooking Agent for recipe guidance.

Provides step-by-step cooking instructions, substitutions, and timing help.
"""

import logging
from typing import Dict, Any, Optional

from data.database import DatabaseInterface
from mcp_server.tools.cooking_tools import CookingTools

logger = logging.getLogger(__name__)


class CookingAgent:
    """Agent for providing cooking guidance and recipe assistance."""

    def __init__(self, db: DatabaseInterface):
        """
        Initialize Cooking Agent.

        Args:
            db: Database interface instance
        """
        self.db = db
        self.tools = CookingTools(db)
        logger.info("Cooking Agent initialized")

    def get_cooking_guide(self, recipe_id: str) -> Dict[str, Any]:
        """
        Get a complete cooking guide for a recipe.

        Args:
            recipe_id: Recipe ID

        Returns:
            Cooking guide dictionary
        """
        try:
            guidance = self.tools.get_recipe_with_guidance(recipe_id)

            if not guidance:
                return {
                    "success": False,
                    "error": "Recipe not found"
                }

            return {
                "success": True,
                "recipe_name": guidance["recipe"]["name"],
                "servings": guidance["recipe"]["servings"],
                "estimated_time": guidance["estimated_time"],
                "difficulty": guidance["recipe"]["difficulty"],
                "ingredients": guidance["recipe"]["ingredients_raw"],
                "steps": guidance["recipe"]["steps"],
                "tips": guidance["tips"],
                "prep_steps": guidance["prep_steps"],
                "cooking_steps": guidance["cooking_steps"],
            }

        except Exception as e:
            logger.error(f"Error getting cooking guide: {e}", exc_info=True)
            return {
                "success": False,
                "error": str(e),
            }

    def get_substitutions(self, ingredient: str, reason: Optional[str] = None) -> Dict[str, Any]:
        """
        Get ingredient substitution suggestions.

        Args:
            ingredient: Ingredient name
            reason: Optional reason for substitution

        Returns:
            Substitution suggestions
        """
        try:
            suggestions = self.tools.suggest_substitution(ingredient, reason)

            return {
                "success": True,
                "ingredient": ingredient,
                "substitutions": suggestions,
                "reason": reason,
            }

        except Exception as e:
            logger.error(f"Error getting substitutions: {e}")
            return {
                "success": False,
                "error": str(e),
            }

    def format_cooking_instructions(self, recipe_id: str) -> str:
        """
        Format recipe as step-by-step cooking instructions.

        Args:
            recipe_id: Recipe ID

        Returns:
            Formatted cooking instructions
        """
        guide = self.get_cooking_guide(recipe_id)

        if not guide.get("success"):
            return f"Error: {guide.get('error')}"

        lines = [
            f"🍳 {guide['recipe_name']}",
            f"{'='*60}",
            f"⏱️  Time: {guide['estimated_time'] or '?'} minutes",
            f"🍽️  Servings: {guide['servings']}",
            f"📊 Difficulty: {guide['difficulty'].title()}",
            "",
        ]

        # Tips
        if guide.get("tips"):
            lines.append("💡 Tips:")
            for tip in guide["tips"]:
                lines.append(f"   {tip}")
            lines.append("")

        # Ingredients
        lines.append("📋 Ingredients:")
        for i, ingredient in enumerate(guide["ingredients"], 1):
            lines.append(f"   {i}. {ingredient}")
        lines.append("")

        # Steps
        lines.append("👨‍🍳 Instructions:")
        for i, step in enumerate(guide["steps"], 1):
            lines.append(f"   Step {i}:")
            lines.append(f"   {step}")
            lines.append("")

        return "\n".join(lines)
