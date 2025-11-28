"""
Enhanced Planning Agent for meal planning.

Generates balanced weekly meal plans using direct database access.
Learns from user history and applies preferences.
"""

import logging
from typing import Dict, List, Any, Optional, Set
from datetime import datetime, timedelta
from collections import Counter

import sys
from pathlib import Path

# Add src to path if needed
if __name__ == "__main__":
    sys.path.insert(0, str(Path(__file__).parent.parent))

from data.database import DatabaseInterface
from data.models import MealPlan, PlannedMeal, Recipe

logger = logging.getLogger(__name__)


class EnhancedPlanningAgent:
    """Agent for generating intelligent weekly meal plans."""

    def __init__(self, db: DatabaseInterface):
        """
        Initialize Planning Agent.

        Args:
            db: Database interface instance
        """
        self.db = db
        logger.info("Enhanced Planning Agent initialized")

    def plan_week(
        self,
        week_of: str,
        num_days: int = 7,
        preferences: Optional[Dict[str, Any]] = None,
        user_id: int = 1,
    ) -> Dict[str, Any]:
        """
        Generate a meal plan for a week.

        Args:
            week_of: ISO date string for Monday (e.g., "2025-01-20")
            num_days: Number of days to plan (default: 7)
            preferences: Optional preferences override
            user_id: User ID (defaults to 1 for backward compatibility)

        Returns:
            Dictionary with meal plan results
        """
        try:
            # Load preferences
            if preferences is None:
                preferences = self._get_preferences(user_id=user_id)

            # Analyze meal history
            history_analysis = self._analyze_history(user_id=user_id)

            # Get recently used recipes to avoid
            recent_names = self._get_recent_recipe_names(weeks_back=2, user_id=user_id)

            # Generate meal selections
            meals = self._generate_meals(
                week_of=week_of,
                num_days=num_days,
                preferences=preferences,
                history_analysis=history_analysis,
                avoid_recipes=recent_names,
            )

            # Save the meal plan
            meal_plan = MealPlan(
                week_of=week_of,
                meals=meals,
                preferences_applied=list(preferences.keys()),
            )

            plan_id = self.db.save_meal_plan(meal_plan, user_id=user_id)

            logger.info(f"Generated meal plan {plan_id} with {len(meals)} meals")

            return {
                "success": True,
                "meal_plan_id": plan_id,
                "week_of": week_of,
                "meals": [
                    {
                        "date": m.date,
                        "recipe_name": m.recipe_name,
                        "recipe_id": m.recipe_id,
                        "servings": m.servings,
                    }
                    for m in meals
                ],
                "preferences_applied": list(preferences.keys()),
            }

        except Exception as e:
            logger.error(f"Error planning week: {e}", exc_info=True)
            return {
                "success": False,
                "error": str(e),
            }

    def _get_preferences(self, user_id: int = 1) -> Dict[str, Any]:
        """Load user preferences."""
        prefs = self.db.get_all_preferences(user_id=user_id)

        # Default preferences
        defaults = {
            "variety_window_weeks": 2,
            "max_weeknight_time": 45,
            "max_weekend_time": 90,
            "preferred_cuisines": ["italian", "mexican", "asian"],
            "min_vegetarian_meals": 1,
        }

        # Merge with stored preferences
        for key, value in prefs.items():
            try:
                # Try to parse as int/list
                if key.endswith("_time") or key.endswith("_weeks") or key.endswith("_meals"):
                    defaults[key] = int(value)
                elif key.endswith("_cuisines"):
                    defaults[key] = value.split(",")
            except (ValueError, AttributeError):
                defaults[key] = value

        return defaults

    def _analyze_history(self, user_id: int = 1) -> Dict[str, Any]:
        """Analyze meal history to extract patterns."""
        history = self.db.get_meal_history(user_id=user_id, weeks_back=8)

        if not history:
            return {
                "favorite_keywords": [],
                "common_ingredients": [],
                "cuisine_preferences": [],
            }

        # Extract keywords from meal names
        meal_names = [m.recipe_name.lower() for m in history]

        # Find common words (potential favorites)
        all_words = []
        for name in meal_names:
            words = name.replace(",", " ").split()
            all_words.extend([w.strip() for w in words if len(w) > 3])

        # Count frequency
        word_counts = Counter(all_words)

        # Common ingredients/keywords
        common_keywords = [word for word, count in word_counts.most_common(10) if count >= 2]

        logger.info(f"Analyzed {len(history)} meals, found favorite keywords: {common_keywords}")

        return {
            "favorite_keywords": common_keywords,
            "common_ingredients": common_keywords[:5],  # Top 5
            "total_meals": len(history),
        }

    def _get_recent_recipe_names(self, weeks_back: int = 2, user_id: int = 1) -> Set[str]:
        """Get recipe names from recent history to avoid repetition."""
        history = self.db.get_meal_history(user_id=user_id, weeks_back=weeks_back)
        return {m.recipe_name.lower() for m in history}

    def _generate_meals(
        self,
        week_of: str,
        num_days: int,
        preferences: Dict[str, Any],
        history_analysis: Dict[str, Any],
        avoid_recipes: Set[str],
    ) -> List[PlannedMeal]:
        """Generate meal selections for the week."""

        meals = []
        week_start = datetime.fromisoformat(week_of)

        # Categories to search for variety
        search_categories = [
            {"query": "chicken", "weight": 2},
            {"query": "salmon", "weight": 2},
            {"query": "beef", "weight": 1},
            {"query": "pasta", "weight": 1},
            {"query": "vegetarian", "tags": ["vegetarian"], "weight": 1},
            {"query": "soup", "weight": 0.5},
            {"query": "tacos", "weight": 1},
        ]

        # Add favorite keywords to search
        for keyword in history_analysis.get("favorite_keywords", [])[:3]:
            if keyword not in ["with", "and", "the"]:
                search_categories.append({"query": keyword, "weight": 1.5})

        # Collect recipe pool
        recipe_pool = []
        used_cuisines = set()

        for category in search_categories:
            max_time = preferences.get("max_weeknight_time", 45)

            recipes = self.db.search_recipes(
                query=category.get("query"),
                tags=category.get("tags"),
                max_time=max_time,
                limit=10,
            )

            # Filter out recent recipes
            recipes = [r for r in recipes if r.name.lower() not in avoid_recipes]

            # Weight recipes
            for recipe in recipes:
                recipe_pool.append({
                    "recipe": recipe,
                    "weight": category.get("weight", 1.0),
                    "category": category.get("query"),
                })

        if not recipe_pool:
            logger.warning("No recipes found in pool, using fallback search")
            # Fallback: just get any recipes
            recipes = self.db.search_recipes(limit=50)
            recipe_pool = [{"recipe": r, "weight": 1.0, "category": "general"} for r in recipes]

        # Select meals with variety
        selected_recipes = []
        used_recipe_ids = set()
        used_categories = Counter()

        for day in range(num_days):
            # Try to find a diverse recipe
            best_recipe = None
            best_score = -1

            for item in recipe_pool:
                recipe = item["recipe"]

                # Skip if already used
                if recipe.id in used_recipe_ids:
                    continue

                # Calculate variety score
                score = item["weight"]

                # Bonus for different cuisine
                if recipe.cuisine and recipe.cuisine not in used_cuisines:
                    score += 2.0

                # Penalty for repeated category
                category_count = used_categories.get(item["category"], 0)
                score -= category_count * 0.5

                # Prefer medium difficulty on weekdays, any on weekends
                day_of_week = (week_start + timedelta(days=day)).weekday()
                if day_of_week < 5:  # Weekday
                    if recipe.difficulty == "easy":
                        score += 0.5
                else:  # Weekend
                    if recipe.difficulty == "hard":
                        score += 0.3

                if score > best_score:
                    best_score = score
                    best_recipe = recipe

            if not best_recipe:
                # Fallback: use any unused recipe
                for item in recipe_pool:
                    if item["recipe"].id not in used_recipe_ids:
                        best_recipe = item["recipe"]
                        break

            if best_recipe:
                selected_recipes.append(best_recipe)
                used_recipe_ids.add(best_recipe.id)
                if best_recipe.cuisine:
                    used_cuisines.add(best_recipe.cuisine)

                # Find category
                for item in recipe_pool:
                    if item["recipe"].id == best_recipe.id:
                        used_categories[item["category"]] += 1
                        break

        # Create PlannedMeal objects
        for day, recipe in enumerate(selected_recipes):
            meal_date = (week_start + timedelta(days=day)).strftime("%Y-%m-%d")

            meals.append(
                PlannedMeal(
                    date=meal_date,
                    meal_type="dinner",
                    recipe_id=recipe.id,
                    recipe_name=recipe.name,
                    servings=4,
                )
            )

        logger.info(f"Generated {len(meals)} meals with variety across {len(used_cuisines)} cuisines")

        return meals

    def explain_plan(self, meal_plan_id: str, user_id: int = 1) -> str:
        """
        Generate a human-readable explanation of a meal plan.

        Args:
            meal_plan_id: ID of saved meal plan
            user_id: User ID (defaults to 1 for backward compatibility)

        Returns:
            Explanation text
        """
        plan = self.db.get_meal_plan(meal_plan_id, user_id=user_id)

        if not plan:
            return "Meal plan not found."

        explanation = [
            f"Meal Plan for Week of {plan.week_of}",
            f"{'='*50}",
            "",
        ]

        # Group by cuisine
        cuisines = Counter()
        difficulties = Counter()

        for meal in plan.meals:
            recipe = self.db.get_recipe(meal.recipe_id)
            if recipe:
                if recipe.cuisine:
                    cuisines[recipe.cuisine] += 1
                difficulties[recipe.difficulty] += 1

                # Format date nicely
                date_obj = datetime.fromisoformat(meal.date)
                day_name = date_obj.strftime("%A")

                explanation.append(
                    f"{day_name}, {meal.date}: {meal.recipe_name}"
                )
                explanation.append(
                    f"  ({recipe.estimated_time or '?'} min, {recipe.difficulty}, {recipe.servings} servings)"
                )
                explanation.append("")

        # Add variety summary
        explanation.append("")
        explanation.append("Variety Summary:")
        explanation.append(f"  Cuisines: {', '.join([f'{c} ({n})' for c, n in cuisines.most_common()])}")
        explanation.append(f"  Difficulty: {', '.join([f'{d} ({n})' for d, n in difficulties.items()])}")

        return "\n".join(explanation)
