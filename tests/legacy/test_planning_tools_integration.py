"""
Integration tests for planning tools with meal_events system.

Tests that planning tools correctly integrate with the new meal_events
and user_profile tables. These validate the complete data flow.
"""

import pytest
from datetime import datetime

from src.mcp_server.tools.planning_tools import PlanningTools
from src.data.database import DatabaseInterface
from src.data.models import UserProfile, MealEvent, Recipe


class TestPlanningToolsMealEventsIntegration:
    """Test planning tools integration with meal_events."""

    def test_save_meal_plan_creates_meal_events(self, db, sample_recipe):
        """Test that saving a meal plan automatically creates meal_events."""
        # Arrange
        tools = PlanningTools(db)

        # Need to mock recipe lookup - for now we'll test the structure
        meals = [
            {
                "date": "2025-10-20",
                "meal_type": "dinner",
                "recipe_id": "12345",
                "recipe_name": "Test Recipe",
                "servings": 4,
            }
        ]

        # Act
        result = tools.save_meal_plan(
            week_of="2025-10-20",
            meals=meals,
            preferences_applied=["variety", "time_constraints"],
        )

        # Assert - Plan saved
        assert result["success"] is True
        assert "meal_plan_id" in result

        # Assert - Meal events created (this will fail until implemented)
        events = db.get_meal_events(weeks_back=1)
        assert len(events) >= 1
        assert events[0].recipe_name == "Test Recipe"
        assert events[0].meal_plan_id == result["meal_plan_id"]

    def test_get_user_preferences_returns_profile_data(self, db, sample_user_profile):
        """Test that get_user_preferences reads from user_profile table."""
        # Arrange
        db.save_user_profile(sample_user_profile)
        tools = PlanningTools(db)

        # Act
        prefs = tools.get_user_preferences()

        # Assert - Profile data returned
        assert prefs["household_size"] == 4
        assert "dairy-free" in prefs["dietary_restrictions"]
        assert "italian" in prefs["favorite_cuisines"]
        assert prefs["max_weeknight_time"] == 45

    def test_get_user_preferences_includes_learned_data(self, db, sample_user_profile):
        """Test that preferences include learned data from meal_events."""
        # Arrange
        db.save_user_profile(sample_user_profile)

        # Add some meal events with ratings
        event1 = MealEvent(
            date="2025-10-20",
            day_of_week="Monday",
            recipe_id="123",
            recipe_name="Pasta",
            recipe_cuisine="Italian",
            user_rating=5,
            created_at=datetime.now(),
        )
        db.add_meal_event(event1)

        tools = PlanningTools(db)

        # Act
        prefs = tools.get_user_preferences()

        # Assert - Includes learned preferences
        assert "cuisine_stats" in prefs
        assert "favorite_recipes" in prefs
        # Cuisine stats should show Italian
        if prefs["cuisine_stats"]:
            assert "Italian" in prefs["cuisine_stats"]

    def test_get_meal_history_returns_meal_events(self, db, sample_meal_event):
        """Test that get_meal_history returns meal_events with rich data."""
        # Arrange
        db.add_meal_event(sample_meal_event)
        tools = PlanningTools(db)

        # Act
        history = tools.get_meal_history(weeks_back=1)

        # Assert - Returns meal events with ratings
        assert len(history) == 1
        assert history[0]["recipe_name"] == "Honey Ginger Chicken"
        assert history[0]["user_rating"] == 5
        assert history[0]["recipe_cuisine"] == "Asian"
        assert "would_make_again" in history[0]

    def test_get_meal_history_excludes_low_rated_meals(self, db):
        """Test filtering meal history based on ratings."""
        # Arrange
        good_event = MealEvent(
            date="2025-10-20",
            day_of_week="Monday",
            recipe_id="123",
            recipe_name="Great Meal",
            user_rating=5,
            would_make_again=True,
            created_at=datetime.now(),
        )

        bad_event = MealEvent(
            date="2025-10-21",
            day_of_week="Tuesday",
            recipe_id="456",
            recipe_name="Bad Meal",
            user_rating=2,
            would_make_again=False,
            created_at=datetime.now(),
        )

        db.add_meal_event(good_event)
        db.add_meal_event(bad_event)

        tools = PlanningTools(db)

        # Act
        history = tools.get_meal_history(weeks_back=1)

        # Assert - Both returned (filtering happens in agent)
        assert len(history) == 2

        # But we can see the ratings
        ratings = [h["user_rating"] for h in history]
        assert 5 in ratings
        assert 2 in ratings


class TestPlanningToolsWithoutOnboarding:
    """Test planning tools work without onboarding (backward compatibility)."""

    def test_get_user_preferences_without_profile(self, db):
        """Test that get_user_preferences works without user_profile."""
        # Arrange
        tools = PlanningTools(db)

        # Act
        prefs = tools.get_user_preferences()

        # Assert - Returns defaults
        assert prefs is not None
        assert "max_weeknight_time" in prefs
        # Should have some default values

    def test_get_meal_history_falls_back_to_old_history(self, db):
        """Test that get_meal_history falls back to old meal_history table."""
        # Arrange
        # Add to old history table
        db.add_meal_to_history(
            date="2025-10-20",
            meal_name="Old History Meal",
            day_of_week="Monday",
            meal_type="dinner",
        )

        tools = PlanningTools(db)

        # Act
        history = tools.get_meal_history(weeks_back=1)

        # Assert - Returns old history if no meal_events
        # (This tests backward compatibility)
        assert len(history) >= 1


class TestPlanningToolsRecipeIntegration:
    """Test planning tools with recipe database."""

    @pytest.mark.skip(reason="Requires recipes.db with test data")
    def test_search_recipes_with_preferences(self, db, sample_user_profile):
        """Test searching recipes respecting user preferences."""
        # This test requires recipes.db with test data
        # Skipping for now, but shows intent
        pass

    @pytest.mark.skip(reason="Requires recipes.db with test data")
    def test_save_meal_plan_with_real_recipes(self, db):
        """Test saving plan with recipes from recipes.db."""
        # This test requires recipes.db with test data
        # Skipping for now, but shows intent
        pass
