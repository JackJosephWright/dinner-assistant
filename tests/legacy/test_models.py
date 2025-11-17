"""
Unit tests for data models.

Tests individual model methods in isolation without database.
"""

import pytest
from datetime import datetime

from src.data.models import Recipe, MealEvent, UserProfile, PlannedMeal, MealPlan


class TestRecipe:
    """Test Recipe model."""

    def test_recipe_creation(self, sample_recipe):
        """Test creating a recipe with all fields."""
        assert sample_recipe.id == "12345"
        assert sample_recipe.name == "Honey Ginger Chicken"
        assert sample_recipe.servings == 4
        assert len(sample_recipe.ingredients) == 4

    def test_recipe_time_extraction(self):
        """Test that estimated_time is extracted from tags."""
        recipe = Recipe(
            id="1",
            name="Quick Pasta",
            description="Fast meal",
            ingredients=["pasta"],
            ingredients_raw=["1 lb pasta"],
            steps=["Boil", "Serve"],
            servings=2,
            serving_size="1 bowl",
            tags=["15-minutes-or-less", "easy"],
        )

        assert recipe.estimated_time == 15

    def test_recipe_cuisine_extraction(self):
        """Test that cuisine is extracted from tags."""
        recipe = Recipe(
            id="1",
            name="Spaghetti",
            description="Italian classic",
            ingredients=["pasta"],
            ingredients_raw=["1 lb pasta"],
            steps=["Cook"],
            servings=2,
            serving_size="1 bowl",
            tags=["italian", "pasta"],
        )

        assert recipe.cuisine == "Italian"

    def test_recipe_difficulty_extraction(self):
        """Test that difficulty is extracted from tags."""
        recipe = Recipe(
            id="1",
            name="Simple Dish",
            description="Easy to make",
            ingredients=["ingredient"],
            ingredients_raw=["1 unit"],
            steps=["Mix"],
            servings=1,
            serving_size="1 serving",
            tags=["easy", "quick"],
        )

        assert recipe.difficulty == "easy"

    def test_recipe_to_dict(self, sample_recipe):
        """Test converting recipe to dictionary."""
        recipe_dict = sample_recipe.to_dict()

        assert recipe_dict["id"] == "12345"
        assert recipe_dict["name"] == "Honey Ginger Chicken"
        assert recipe_dict["cuisine"] == "Asian"
        assert recipe_dict["estimated_time"] == 30
        assert isinstance(recipe_dict["ingredients"], list)

    def test_recipe_from_dict(self):
        """Test creating recipe from dictionary."""
        data = {
            "id": "999",
            "name": "Test Recipe",
            "description": "Test",
            "ingredients": ["a", "b"],
            "ingredients_raw": ["1 a", "2 b"],
            "steps": ["step1"],
            "servings": 2,
            "serving_size": "1 portion",
            "tags": ["test"],
            "estimated_time": 20,
            "cuisine": "Test",
            "difficulty": "easy",
        }

        recipe = Recipe.from_dict(data)

        assert recipe.id == "999"
        assert recipe.name == "Test Recipe"
        assert recipe.estimated_time == 20


class TestMealEvent:
    """Test MealEvent model."""

    def test_meal_event_creation(self, sample_meal_event):
        """Test creating a meal event with all fields."""
        assert sample_meal_event.date == "2025-10-20"
        assert sample_meal_event.recipe_name == "Honey Ginger Chicken"
        assert sample_meal_event.servings_planned == 4
        assert sample_meal_event.servings_actual == 6
        assert sample_meal_event.user_rating == 5

    def test_meal_event_to_dict(self, sample_meal_event):
        """Test converting meal event to dictionary."""
        event_dict = sample_meal_event.to_dict()

        assert event_dict["date"] == "2025-10-20"
        assert event_dict["recipe_name"] == "Honey Ginger Chicken"
        assert event_dict["user_rating"] == 5
        assert event_dict["modifications"]["doubled_garlic"] is True
        assert event_dict["substitutions"]["soy_sauce"] == "tamari"
        assert isinstance(event_dict["created_at"], str)

    def test_meal_event_from_dict(self):
        """Test creating meal event from dictionary."""
        data = {
            "id": 1,
            "date": "2025-10-20",
            "day_of_week": "Monday",
            "meal_type": "dinner",
            "recipe_id": "123",
            "recipe_name": "Test Meal",
            "recipe_cuisine": "Test",
            "recipe_difficulty": "easy",
            "servings_planned": 4,
            "servings_actual": 4,
            "ingredients_snapshot": ["ingredient1"],
            "modifications": {},
            "substitutions": {},
            "user_rating": 4,
            "cooking_time_actual": 30,
            "notes": "Great!",
            "would_make_again": True,
            "meal_plan_id": "mp_123",
            "created_at": "2025-10-20T18:00:00",
        }

        event = MealEvent.from_dict(data)

        assert event.date == "2025-10-20"
        assert event.recipe_name == "Test Meal"
        assert event.user_rating == 4
        assert event.would_make_again is True

    def test_meal_event_minimal_creation(self):
        """Test creating meal event with only required fields."""
        event = MealEvent(
            date="2025-10-20",
            day_of_week="Monday",
            recipe_name="Minimal Meal",
        )

        assert event.date == "2025-10-20"
        assert event.day_of_week == "Monday"
        assert event.recipe_name == "Minimal Meal"
        assert event.user_rating is None
        assert event.modifications == {}


class TestUserProfile:
    """Test UserProfile model."""

    def test_user_profile_creation(self, sample_user_profile):
        """Test creating a user profile with all fields."""
        assert sample_user_profile.household_size == 4
        assert sample_user_profile.cooking_for["adults"] == 2
        assert sample_user_profile.cooking_for["kids"] == 2
        assert "dairy-free" in sample_user_profile.dietary_restrictions
        assert sample_user_profile.onboarding_completed is True

    def test_user_profile_defaults(self):
        """Test user profile with default values."""
        profile = UserProfile()

        assert profile.household_size == 4
        assert profile.spice_tolerance == "medium"
        assert profile.max_weeknight_cooking_time == 45
        assert profile.variety_preference == "high"
        assert profile.onboarding_completed is False
        assert profile.id == 1  # Always 1 for single row

    def test_user_profile_to_dict(self, sample_user_profile):
        """Test converting user profile to dictionary."""
        profile_dict = sample_user_profile.to_dict()

        assert profile_dict["household_size"] == 4
        assert profile_dict["favorite_cuisines"] == ["italian", "mexican", "asian"]
        assert profile_dict["spice_tolerance"] == "medium"
        assert isinstance(profile_dict["created_at"], str)

    def test_user_profile_from_dict(self):
        """Test creating user profile from dictionary."""
        data = {
            "id": 1,
            "household_size": 2,
            "cooking_for": {"adults": 2, "kids": 0},
            "dietary_restrictions": ["vegan"],
            "allergens": [],
            "favorite_cuisines": ["thai"],
            "disliked_ingredients": [],
            "preferred_proteins": ["tofu"],
            "spice_tolerance": "spicy",
            "max_weeknight_cooking_time": 30,
            "max_weekend_cooking_time": 60,
            "budget_per_week": 100.0,
            "variety_preference": "medium",
            "health_focus": "low-carb",
            "onboarding_completed": True,
            "created_at": "2025-10-13T10:00:00",
            "updated_at": "2025-10-13T10:00:00",
        }

        profile = UserProfile.from_dict(data)

        assert profile.household_size == 2
        assert profile.spice_tolerance == "spicy"
        assert profile.favorite_cuisines == ["thai"]
        assert profile.budget_per_week == 100.0


class TestPlannedMeal:
    """Test PlannedMeal model."""

    def test_planned_meal_creation(self):
        """Test creating a planned meal."""
        meal = PlannedMeal(
            date="2025-10-20",
            meal_type="dinner",
            recipe_id="123",
            recipe_name="Test Meal",
            servings=4,
            notes="Use less salt",
        )

        assert meal.date == "2025-10-20"
        assert meal.recipe_name == "Test Meal"
        assert meal.notes == "Use less salt"

    def test_planned_meal_to_dict(self):
        """Test converting planned meal to dictionary."""
        meal = PlannedMeal(
            date="2025-10-20",
            meal_type="dinner",
            recipe_id="123",
            recipe_name="Test Meal",
            servings=4,
        )

        meal_dict = meal.to_dict()

        assert meal_dict["date"] == "2025-10-20"
        assert meal_dict["recipe_id"] == "123"
        assert meal_dict["servings"] == 4


class TestMealPlan:
    """Test MealPlan model."""

    def test_meal_plan_creation(self, sample_meal_plan):
        """Test creating a meal plan."""
        assert sample_meal_plan.week_of == "2025-10-20"
        assert len(sample_meal_plan.meals) == 2
        assert "variety" in sample_meal_plan.preferences_applied

    def test_meal_plan_to_dict(self, sample_meal_plan):
        """Test converting meal plan to dictionary."""
        plan_dict = sample_meal_plan.to_dict()

        assert plan_dict["week_of"] == "2025-10-20"
        assert len(plan_dict["meals"]) == 2
        assert isinstance(plan_dict["meals"][0], dict)
        assert isinstance(plan_dict["created_at"], str)

    def test_meal_plan_from_dict(self):
        """Test creating meal plan from dictionary."""
        data = {
            "id": "mp_123",
            "week_of": "2025-10-20",
            "meals": [
                {
                    "date": "2025-10-20",
                    "meal_type": "dinner",
                    "recipe_id": "123",
                    "recipe_name": "Meal 1",
                    "servings": 4,
                    "notes": None,
                }
            ],
            "created_at": "2025-10-20T10:00:00",
            "preferences_applied": ["variety"],
        }

        plan = MealPlan.from_dict(data)

        assert plan.id == "mp_123"
        assert plan.week_of == "2025-10-20"
        assert len(plan.meals) == 1
        assert plan.meals[0].recipe_name == "Meal 1"
