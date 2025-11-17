"""
Unit tests for database operations.

Tests CRUD operations with a temporary test database.
"""

import pytest
from datetime import datetime

from src.data.database import DatabaseInterface
from src.data.models import MealEvent, UserProfile, MealPlan, PlannedMeal


class TestDatabaseInitialization:
    """Test database initialization."""

    def test_database_creates_tables(self, db):
        """Test that database creates all required tables."""
        import sqlite3

        # Connect to the database and check tables exist
        with sqlite3.connect(db.user_db) as conn:
            cursor = conn.cursor()

            # Check meal_plans table
            cursor.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name='meal_plans'"
            )
            assert cursor.fetchone() is not None

            # Check meal_events table
            cursor.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name='meal_events'"
            )
            assert cursor.fetchone() is not None

            # Check user_profile table
            cursor.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name='user_profile'"
            )
            assert cursor.fetchone() is not None

    def test_database_creates_indexes(self, db):
        """Test that indexes are created."""
        import sqlite3

        with sqlite3.connect(db.user_db) as conn:
            cursor = conn.cursor()

            cursor.execute(
                "SELECT name FROM sqlite_master WHERE type='index' AND name='idx_meal_events_date'"
            )
            assert cursor.fetchone() is not None


class TestMealEventOperations:
    """Test meal event CRUD operations."""

    def test_add_meal_event(self, db, sample_meal_event):
        """Test adding a new meal event."""
        event_id = db.add_meal_event(sample_meal_event)

        assert event_id is not None
        assert isinstance(event_id, int)
        assert event_id > 0

    def test_get_meal_events(self, db, sample_meal_event):
        """Test retrieving meal events."""
        # Add an event
        db.add_meal_event(sample_meal_event)

        # Retrieve events
        events = db.get_meal_events(weeks_back=1)

        assert len(events) == 1
        assert events[0].recipe_name == "Honey Ginger Chicken"
        assert events[0].user_rating == 5

    def test_get_meal_events_empty(self, db):
        """Test getting events from empty database."""
        events = db.get_meal_events(weeks_back=1)

        assert len(events) == 0
        assert events == []

    def test_update_meal_event(self, db, sample_meal_event):
        """Test updating an existing meal event."""
        # Add event
        event_id = db.add_meal_event(sample_meal_event)

        # Update it
        updates = {
            "user_rating": 4,
            "notes": "Updated notes",
            "cooking_time_actual": 40,
        }

        success = db.update_meal_event(event_id, updates)
        assert success is True

        # Verify update
        events = db.get_meal_events(weeks_back=1)
        assert events[0].user_rating == 4
        assert events[0].notes == "Updated notes"
        assert events[0].cooking_time_actual == 40

    def test_get_favorite_recipes(self, db):
        """Test getting favorite recipes based on ratings."""
        # Add multiple events with ratings
        event1 = MealEvent(
            date="2025-10-20",
            day_of_week="Monday",
            recipe_id="123",
            recipe_name="Great Recipe",
            user_rating=5,
            created_at=datetime.now(),
        )

        event2 = MealEvent(
            date="2025-10-21",
            day_of_week="Tuesday",
            recipe_id="123",
            recipe_name="Great Recipe",
            user_rating=5,
            created_at=datetime.now(),
        )

        event3 = MealEvent(
            date="2025-10-22",
            day_of_week="Wednesday",
            recipe_id="456",
            recipe_name="OK Recipe",
            user_rating=3,
            created_at=datetime.now(),
        )

        db.add_meal_event(event1)
        db.add_meal_event(event2)
        db.add_meal_event(event3)

        # Get favorites
        favorites = db.get_favorite_recipes(limit=10)

        assert len(favorites) == 2
        assert favorites[0]["recipe_name"] == "Great Recipe"
        assert favorites[0]["avg_rating"] == 5.0
        assert favorites[0]["times_cooked"] == 2

    def test_get_recent_meals(self, db, sample_meal_event):
        """Test getting recent meals for variety enforcement."""
        db.add_meal_event(sample_meal_event)

        recent = db.get_recent_meals(days_back=7)

        assert len(recent) == 1
        assert recent[0].recipe_name == "Honey Ginger Chicken"

    def test_get_cuisine_preferences(self, db):
        """Test analyzing cuisine preferences."""
        # Add events with different cuisines
        event1 = MealEvent(
            date="2025-10-20",
            day_of_week="Monday",
            recipe_id="123",
            recipe_name="Pasta",
            recipe_cuisine="Italian",
            user_rating=5,
            created_at=datetime.now(),
        )

        event2 = MealEvent(
            date="2025-10-21",
            day_of_week="Tuesday",
            recipe_id="124",
            recipe_name="Tacos",
            recipe_cuisine="Mexican",
            user_rating=4,
            created_at=datetime.now(),
        )

        event3 = MealEvent(
            date="2025-10-22",
            day_of_week="Wednesday",
            recipe_id="125",
            recipe_name="Pizza",
            recipe_cuisine="Italian",
            user_rating=5,
            created_at=datetime.now(),
        )

        db.add_meal_event(event1)
        db.add_meal_event(event2)
        db.add_meal_event(event3)

        # Get cuisine preferences
        prefs = db.get_cuisine_preferences()

        assert "Italian" in prefs
        assert prefs["Italian"]["frequency"] == 2
        assert prefs["Italian"]["avg_rating"] == 5.0


class TestUserProfileOperations:
    """Test user profile CRUD operations."""

    def test_save_user_profile(self, db, sample_user_profile):
        """Test saving a user profile."""
        success = db.save_user_profile(sample_user_profile)

        assert success is True

    def test_get_user_profile(self, db, sample_user_profile):
        """Test retrieving user profile."""
        # Save profile
        db.save_user_profile(sample_user_profile)

        # Retrieve it
        profile = db.get_user_profile()

        assert profile is not None
        assert profile.household_size == 4
        assert profile.spice_tolerance == "medium"
        assert "italian" in profile.favorite_cuisines

    def test_get_user_profile_empty(self, db):
        """Test getting profile when none exists."""
        profile = db.get_user_profile()

        assert profile is None

    def test_update_user_profile(self, db, sample_user_profile):
        """Test updating user profile."""
        # Save initial profile
        db.save_user_profile(sample_user_profile)

        # Update it
        sample_user_profile.household_size = 6
        sample_user_profile.spice_tolerance = "spicy"

        db.save_user_profile(sample_user_profile)

        # Verify update
        profile = db.get_user_profile()
        assert profile.household_size == 6
        assert profile.spice_tolerance == "spicy"

    def test_is_onboarded(self, db, sample_user_profile):
        """Test checking onboarding status."""
        # Not onboarded initially
        assert db.is_onboarded() is False

        # Save profile with onboarding_completed=True
        db.save_user_profile(sample_user_profile)

        # Now onboarded
        assert db.is_onboarded() is True

    def test_single_profile_constraint(self, db, sample_user_profile):
        """Test that only one profile can exist (id=1)."""
        # Save profile
        db.save_user_profile(sample_user_profile)

        # Update and save again
        sample_user_profile.household_size = 10
        db.save_user_profile(sample_user_profile)

        # Should still be only one profile
        profile = db.get_user_profile()
        assert profile.id == 1
        assert profile.household_size == 10


class TestMealPlanOperations:
    """Test meal plan CRUD operations."""

    def test_save_meal_plan(self, db, sample_meal_plan):
        """Test saving a meal plan."""
        plan_id = db.save_meal_plan(sample_meal_plan)

        assert plan_id is not None
        assert isinstance(plan_id, str)
        assert plan_id.startswith("mp_")

    def test_get_meal_plan(self, db, sample_meal_plan):
        """Test retrieving a meal plan by ID."""
        # Save plan
        plan_id = db.save_meal_plan(sample_meal_plan)

        # Retrieve it
        plan = db.get_meal_plan(plan_id)

        assert plan is not None
        assert plan.week_of == "2025-10-20"
        assert len(plan.meals) == 2
        assert plan.meals[0].recipe_name == "Honey Ginger Chicken"

    def test_get_meal_plan_not_found(self, db):
        """Test getting a non-existent meal plan."""
        plan = db.get_meal_plan("nonexistent_id")

        assert plan is None

    def test_get_recent_meal_plans(self, db, sample_meal_plan):
        """Test getting recent meal plans."""
        # Save multiple plans
        plan1 = sample_meal_plan
        db.save_meal_plan(plan1)

        plan2 = MealPlan(
            week_of="2025-10-27",
            meals=[
                PlannedMeal(
                    date="2025-10-27",
                    meal_type="dinner",
                    recipe_id="999",
                    recipe_name="Another Meal",
                    servings=4,
                )
            ],
            created_at=datetime.now(),
        )
        db.save_meal_plan(plan2)

        # Get recent plans
        plans = db.get_recent_meal_plans(limit=10)

        assert len(plans) == 2
        # Verify both plans are returned
        week_ofs = {plan.week_of for plan in plans}
        assert "2025-10-20" in week_ofs
        assert "2025-10-27" in week_ofs

    def test_swap_meal_in_plan(self, db, sample_meal_plan, sample_recipe):
        """Test swapping a meal in an existing plan."""
        # We need a recipe in the recipes database for this test
        # For now, this test is a placeholder
        # TODO: Mock the recipe database or use a test recipe DB
        pass
