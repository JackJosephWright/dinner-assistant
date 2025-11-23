"""
Planning tools for the MCP server.

These tools enable the Planning Agent to search recipes, access meal history,
save meal plans, and retrieve user preferences.
"""

import logging
from typing import List, Optional, Dict, Any
from datetime import datetime

from data.database import DatabaseInterface
from data.models import Recipe, MealPlan, PlannedMeal, MealEvent

logger = logging.getLogger(__name__)


class PlanningTools:
    """Planning-related tools for meal planning agent."""

    def __init__(self, db: DatabaseInterface):
        """
        Initialize planning tools.

        Args:
            db: Database interface instance
        """
        self.db = db

    def search_recipes(
        self,
        query: Optional[str] = None,
        max_time: Optional[int] = None,
        tags: Optional[List[str]] = None,
        exclude_ids: Optional[List[str]] = None,
        limit: int = 20,
    ) -> List[Dict[str, Any]]:
        """
        Search recipes by keywords, tags, and time.

        Tool contract as specified in HANDOFF.md.

        Args:
            query: Keywords to search (optional)
            max_time: Maximum cooking time in minutes (optional)
            tags: Required tags (optional)
            exclude_ids: Recipe IDs to skip (optional)
            limit: Maximum results (default: 20)

        Returns:
            List of recipe dictionaries with id, name, tags, estimated_time
        """
        try:
            recipes = self.db.search_recipes(
                query=query,
                max_time=max_time,
                tags=tags,
                exclude_ids=exclude_ids,
                limit=limit,
            )

            # Return simplified format for planning
            return [
                {
                    "id": recipe.id,
                    "name": recipe.name,
                    "tags": recipe.tags,
                    "estimated_time": recipe.estimated_time,
                    "cuisine": recipe.cuisine,
                    "difficulty": recipe.difficulty,
                    "servings": recipe.servings,
                }
                for recipe in recipes
            ]

        except Exception as e:
            logger.error(f"Error searching recipes: {e}")
            return []

    def get_meal_history(self, weeks_back: int = 8) -> List[Dict[str, Any]]:
        """
        Retrieve past meal events to avoid repetition and understand preferences.

        Now uses the rich meal_events table instead of simple meal_history.

        Args:
            weeks_back: Number of weeks to look back (default: 8)

        Returns:
            List of meal event dictionaries with recipe details and ratings
        """
        try:
            # Get meal events (replaces old meal_history)
            events = self.db.get_meal_events(weeks_back=weeks_back)

            # If no events yet, fall back to old history for backward compatibility
            if not events:
                try:
                    meals = self.db.get_meal_history(weeks_back=weeks_back)
                    return [
                        {
                            "date": meal.date,
                            "meal_type": meal.meal_type,
                            "recipe_name": meal.recipe_name,
                            "servings": meal.servings,
                            "recipe_id": meal.recipe_id or "",
                        }
                        for meal in meals
                    ]
                except:
                    return []

            return [
                {
                    "date": event.date,
                    "meal_type": event.meal_type,
                    "recipe_id": event.recipe_id,
                    "recipe_name": event.recipe_name,
                    "recipe_cuisine": event.recipe_cuisine,
                    "servings": event.servings_planned or event.servings_actual,
                    "user_rating": event.user_rating,
                    "would_make_again": event.would_make_again,
                }
                for event in events
            ]

        except Exception as e:
            logger.error(f"Error retrieving meal history: {e}")
            return []

    def _get_recipe_safely(self, recipe_id: str) -> Optional[Recipe]:
        """
        Safely retrieve recipe details, handling missing recipes.db.

        Args:
            recipe_id: Recipe ID to look up

        Returns:
            Recipe object if found, None otherwise
        """
        try:
            return self.db.get_recipe(recipe_id)
        except Exception as e:
            logger.debug(f"Could not load recipe {recipe_id}: {e}")
            return None

    def _create_meal_event_from_plan(
        self, meal_dict: Dict[str, Any], meal_plan_id: str
    ) -> MealEvent:
        """
        Create a MealEvent from a planned meal dictionary.

        This method enriches the meal plan data with recipe details if available,
        but works gracefully without them (e.g., in test environments).

        Args:
            meal_dict: Meal dictionary with date, recipe_id, recipe_name, etc.
            meal_plan_id: ID of the meal plan this event belongs to

        Returns:
            MealEvent object ready to be saved
        """
        # Get day of week from date
        meal_date = datetime.fromisoformat(meal_dict["date"])
        day_of_week = meal_date.strftime("%A")

        # Try to enrich with recipe details
        recipe = self._get_recipe_safely(meal_dict["recipe_id"])

        # Create meal event (works with or without recipe details)
        return MealEvent(
            date=meal_dict["date"],
            day_of_week=day_of_week,
            meal_type=meal_dict.get("meal_type", "dinner"),
            recipe_id=meal_dict["recipe_id"],
            recipe_name=meal_dict["recipe_name"],
            recipe_cuisine=recipe.cuisine if recipe else None,
            recipe_difficulty=recipe.difficulty if recipe else None,
            servings_planned=meal_dict.get("servings", 4),
            ingredients_snapshot=recipe.ingredients_raw if recipe else [],
            meal_plan_id=meal_plan_id,
            created_at=datetime.now(),
        )

    def save_meal_plan(
        self,
        week_of: str,
        meals: List[Dict[str, Any]],
        preferences_applied: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        """
        Save a generated meal plan and automatically create meal events.

        This method performs two operations:
        1. Saves the meal plan to the meal_plans table
        2. Creates individual meal_events for tracking and learning

        Meal events enable the system to learn from user behavior by capturing
        recipe details, planned servings, and linking to the meal plan. These
        events can later be updated with cooking feedback (ratings, modifications).

        Args:
            week_of: ISO date of Monday for the week (e.g., "2025-01-20")
            meals: List of meal dictionaries, each containing:
                - date: ISO date string (required)
                - recipe_id: Recipe identifier (required)
                - recipe_name: Human-readable recipe name (required)
                - meal_type: Type of meal (default: "dinner")
                - servings: Number of servings planned (default: 4)
                - notes: Optional notes about the meal
            preferences_applied: List of preference names that were applied
                during planning (e.g., ["variety", "time_constraints"])

        Returns:
            Dictionary with keys:
                - success: Boolean indicating if save succeeded
                - meal_plan_id: ID of saved meal plan (if successful)
                - week_of: Echo of the week_of parameter
                - num_meals: Number of meals in the plan
                - error: Error message (if unsuccessful)

        Note:
            Recipe enrichment is attempted but gracefully handled if recipes.db
            is unavailable. Meal events are created even without full recipe details.
        """
        try:
            # Convert meal dicts to PlannedMeal objects
            planned_meals = []
            for meal_dict in meals:
                # Use from_dict to handle recipe_id/recipe object compatibility
                planned_meals.append(PlannedMeal.from_dict(meal_dict))

            # Create MealPlan
            meal_plan = MealPlan(
                week_of=week_of,
                meals=planned_meals,
                preferences_applied=preferences_applied or [],
            )

            # Save meal plan to database
            plan_id = self.db.save_meal_plan(meal_plan)

            # Create meal events for each planned meal
            events_created = 0
            for meal_dict in meals:
                try:
                    event = self._create_meal_event_from_plan(meal_dict, plan_id)
                    self.db.add_meal_event(event)
                    events_created += 1

                except Exception as e:
                    logger.warning(f"Failed to create meal event for {meal_dict['recipe_name']}: {e}")
                    # Continue even if event creation fails

            logger.info(f"Saved meal plan {plan_id} with {len(planned_meals)} meal events")

            return {
                "success": True,
                "meal_plan_id": plan_id,
                "week_of": week_of,
                "num_meals": len(planned_meals),
            }

        except Exception as e:
            logger.error(f"Error saving meal plan: {e}")
            return {
                "success": False,
                "error": str(e),
            }

    def get_user_preferences(self) -> Dict[str, Any]:
        """
        Load user preferences for meal planning.

        Now uses the user_profile table from onboarding.

        Returns:
            Dictionary of user preferences
        """
        try:
            # Get user profile (from onboarding)
            profile = self.db.get_user_profile()

            if profile:
                # Get learned preferences from meal events
                cuisine_prefs = self.db.get_cuisine_preferences()
                favorite_recipes = self.db.get_favorite_recipes(limit=20)

                return {
                    "household_size": profile.household_size,
                    "cooking_for": profile.cooking_for,
                    "dietary_restrictions": profile.dietary_restrictions,
                    "allergens": profile.allergens,
                    "favorite_cuisines": profile.favorite_cuisines,
                    "disliked_ingredients": profile.disliked_ingredients,
                    "preferred_proteins": profile.preferred_proteins,
                    "spice_tolerance": profile.spice_tolerance,
                    "max_weeknight_time": profile.max_weeknight_cooking_time,
                    "max_weekend_time": profile.max_weekend_cooking_time,
                    "budget_per_week": profile.budget_per_week,
                    "variety_preference": profile.variety_preference,
                    "health_focus": profile.health_focus,
                    # Learned preferences from meal events
                    "cuisine_stats": cuisine_prefs,
                    "favorite_recipes": favorite_recipes,
                }

            # Fall back to old preferences if no profile
            prefs = self.db.get_all_preferences()
            if not prefs:
                return {
                    "variety_window_weeks": 2,
                    "preferred_cuisines": [],
                    "dietary_restrictions": [],
                    "cooking_skill": "medium",
                    "max_weeknight_time": 45,
                    "max_weekend_time": 90,
                }

            return prefs

        except Exception as e:
            logger.error(f"Error retrieving preferences: {e}")
            return {}

    def get_recipe_details(self, recipe_id: str) -> Optional[Dict[str, Any]]:
        """
        Get full recipe details by ID.

        Args:
            recipe_id: Recipe ID

        Returns:
            Full recipe dictionary or None
        """
        try:
            recipe = self.db.get_recipe(recipe_id)
            if recipe:
                return recipe.to_dict()
            return None

        except Exception as e:
            logger.error(f"Error retrieving recipe {recipe_id}: {e}")
            return None


# Tool definitions for MCP registration
PLANNING_TOOL_DEFINITIONS = [
    {
        "name": "search_recipes",
        "description": (
            "Search for recipes by keywords, tags, and cooking time. "
            "Returns recipes with id, name, tags, and estimated cooking time."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "Keywords to search in recipe name/description",
                },
                "max_time": {
                    "type": "integer",
                    "description": "Maximum cooking time in minutes",
                },
                "tags": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Required tags (e.g., ['healthy', 'easy'])",
                },
                "exclude_ids": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Recipe IDs to exclude from results",
                },
                "limit": {
                    "type": "integer",
                    "description": "Maximum number of results (default: 20)",
                    "default": 20,
                },
            },
        },
    },
    {
        "name": "get_meal_history",
        "description": (
            "Retrieve past meals to understand preferences and avoid repetition. "
            "Returns meals from the specified number of weeks back."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "weeks_back": {
                    "type": "integer",
                    "description": "Number of weeks to look back (default: 8)",
                    "default": 8,
                },
            },
        },
    },
    {
        "name": "save_meal_plan",
        "description": "Save a generated meal plan for a week.",
        "input_schema": {
            "type": "object",
            "properties": {
                "week_of": {
                    "type": "string",
                    "description": "ISO date of Monday (e.g., '2025-01-20')",
                },
                "meals": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "date": {"type": "string"},
                            "meal_type": {"type": "string"},
                            "recipe_id": {"type": "string"},
                            "recipe_name": {"type": "string"},
                            "servings": {"type": "integer"},
                            "notes": {"type": "string"},
                        },
                        "required": ["date", "recipe_id", "recipe_name"],
                    },
                },
                "preferences_applied": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "List of preferences that were applied",
                },
            },
            "required": ["week_of", "meals"],
        },
    },
    {
        "name": "get_user_preferences",
        "description": "Load user preferences for meal planning.",
        "input_schema": {
            "type": "object",
            "properties": {},
        },
    },
    {
        "name": "get_recipe_details",
        "description": "Get full recipe details including ingredients and steps.",
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
