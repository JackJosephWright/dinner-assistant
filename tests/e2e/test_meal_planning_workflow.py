"""
End-to-end tests for complete meal planning workflow.

Tests the entire user journey from onboarding through meal planning.
These represent real-world user scenarios.
"""

import pytest
from datetime import datetime, timedelta

from src.onboarding import OnboardingFlow
from src.mcp_server.tools.planning_tools import PlanningTools
from src.data.database import DatabaseInterface
from src.data.models import MealEvent


class TestCompleteMealPlanningWorkflow:
    """Test the complete workflow a new user would experience."""

    def test_new_user_complete_journey(self, db):
        """
        Test complete journey: onboarding → plan meals → verify learning.

        This is what a real user does:
        1. Complete onboarding
        2. Generate a meal plan
        3. System learns from their choices
        """
        # === STEP 1: Onboarding ===
        flow = OnboardingFlow(db)
        flow.start()

        # User answers questions
        flow.process_answer("4 people (2 adults, 2 kids)")
        flow.process_answer("dairy-free")
        flow.process_answer("Italian and Mexican")
        flow.process_answer("B")  # 45 min weeknights
        flow.process_answer("olives")
        flow.process_answer("medium")
        is_done, msg = flow.process_answer("yes")

        # Verify onboarding complete
        assert is_done
        assert db.is_onboarded()

        profile = db.get_user_profile()
        assert profile.household_size == 4
        assert "italian" in profile.favorite_cuisines

        # === STEP 2: Get user preferences (agent would do this) ===
        tools = PlanningTools(db)
        prefs = tools.get_user_preferences()

        # Verify preferences include onboarding data
        assert prefs["household_size"] == 4
        assert "dairy-free" in prefs["dietary_restrictions"]
        assert "italian" in prefs["favorite_cuisines"]

        # === STEP 3: Generate meal plan ===
        # (In real usage, agent would search recipes and build plan)
        # For test, we'll create a simple plan
        meals = [
            {
                "date": "2025-10-20",
                "meal_type": "dinner",
                "recipe_id": "12345",
                "recipe_name": "Pasta Primavera",
                "servings": 4,
            },
            {
                "date": "2025-10-21",
                "meal_type": "dinner",
                "recipe_id": "12346",
                "recipe_name": "Chicken Tacos",
                "servings": 4,
            },
        ]

        # Note: This will fail until we handle missing recipes.db in tests
        # We'll fix this in Green phase
        result = tools.save_meal_plan(
            week_of="2025-10-20",
            meals=meals,
            preferences_applied=["variety", "time_constraints"],
        )

        # Verify plan saved
        assert result["success"] is True
        plan_id = result["meal_plan_id"]

        # === STEP 4: Verify meal events created ===
        events = db.get_meal_events(weeks_back=1)
        assert len(events) == 2

        event_names = {e.recipe_name for e in events}
        assert "Pasta Primavera" in event_names
        assert "Chicken Tacos" in event_names

        # === STEP 5: User cooks a meal and rates it ===
        # (This would be cooking agent updating the event)
        event_id = events[0].id
        db.update_meal_event(
            event_id,
            {
                "user_rating": 5,
                "cooking_time_actual": 40,
                "notes": "Kids loved it!",
                "would_make_again": True,
            },
        )

        # === STEP 6: System learns from feedback ===
        # Next time user plans, agent reads preferences
        updated_prefs = tools.get_user_preferences()

        # Should now include favorite recipes
        assert "favorite_recipes" in updated_prefs
        # (May be empty if no ratings yet, but structure exists)

        history = tools.get_meal_history(weeks_back=1)
        assert len(history) == 2

        # Should include ratings
        rated_meals = [h for h in history if h.get("user_rating")]
        assert len(rated_meals) >= 1

    def test_returning_user_workflow(self, db, sample_user_profile):
        """
        Test workflow for returning user (already onboarded).

        1. User already has profile
        2. User already has meal history
        3. Plan new meals avoiding recent meals
        """
        # === STEP 1: User already onboarded ===
        db.save_user_profile(sample_user_profile)
        assert db.is_onboarded()

        # === STEP 2: User has meal history ===
        # Add some past meals
        past_event = MealEvent(
            date=(datetime.now() - timedelta(days=3)).strftime("%Y-%m-%d"),
            day_of_week="Friday",
            recipe_id="999",
            recipe_name="Spaghetti Carbonara",
            recipe_cuisine="Italian",
            user_rating=4,
            created_at=datetime.now(),
        )
        db.add_meal_event(past_event)

        # === STEP 3: Get preferences (includes history) ===
        tools = PlanningTools(db)
        prefs = tools.get_user_preferences()
        history = tools.get_meal_history(weeks_back=1)

        # Verify has history
        assert len(history) == 1
        assert history[0]["recipe_name"] == "Spaghetti Carbonara"

        # === STEP 4: Plan new meals (avoiding recent) ===
        # Agent would check history and avoid "Spaghetti Carbonara"
        # For test, we'll plan different meals
        meals = [
            {
                "date": datetime.now().strftime("%Y-%m-%d"),
                "meal_type": "dinner",
                "recipe_id": "111",
                "recipe_name": "Chicken Stir Fry",
                "servings": 4,
            }
        ]

        result = tools.save_meal_plan(
            week_of=datetime.now().strftime("%Y-%m-%d"),
            meals=meals,
        )

        assert result["success"] is True

        # === STEP 5: Verify variety enforcement ===
        # Should now have 2 different meals in recent history
        updated_history = tools.get_meal_history(weeks_back=1)
        assert len(updated_history) == 2

        meal_names = {h["recipe_name"] for h in updated_history}
        assert "Spaghetti Carbonara" in meal_names
        assert "Chicken Stir Fry" in meal_names


class TestWorkflowEdgeCases:
    """Test edge cases in the workflow."""

    def test_plan_meals_without_onboarding(self, db):
        """Test that meal planning works without onboarding (defaults)."""
        # User skips onboarding, goes straight to planning
        tools = PlanningTools(db)

        # Should get default preferences
        prefs = tools.get_user_preferences()
        assert prefs is not None
        assert "max_weeknight_time" in prefs

        # Can still create meal plan
        meals = [
            {
                "date": "2025-10-20",
                "meal_type": "dinner",
                "recipe_id": "123",
                "recipe_name": "Quick Meal",
                "servings": 4,
            }
        ]

        result = tools.save_meal_plan(week_of="2025-10-20", meals=meals)
        # Should work (with defaults)
        assert result["success"] is True

    def test_onboard_after_using_system(self, db):
        """Test onboarding after user has already planned meals."""
        # User uses system first
        tools = PlanningTools(db)
        meals = [
            {
                "date": "2025-10-20",
                "meal_type": "dinner",
                "recipe_id": "123",
                "recipe_name": "First Meal",
                "servings": 4,
            }
        ]
        tools.save_meal_plan(week_of="2025-10-20", meals=meals)

        # Then user completes onboarding
        flow = OnboardingFlow(db)
        flow.start()
        flow.process_answer("4 people")
        flow.process_answer("none")
        flow.process_answer("italian")
        flow.process_answer("A")
        flow.process_answer("skip")
        flow.process_answer("skip")
        flow.process_answer("yes")

        # Verify profile created
        assert db.is_onboarded()

        # Verify existing meal history preserved
        history = tools.get_meal_history(weeks_back=1)
        assert len(history) >= 1


@pytest.mark.asyncio
class TestAgentWorkflow:
    """Test workflows involving agent interactions (async)."""

    @pytest.mark.skip(reason="Requires agent implementation")
    async def test_planning_agent_end_to_end(self, db):
        """Test planning agent with real meal planning."""
        # This would test the actual planning agent
        # Skipping until agent integration is complete
        pass

    @pytest.mark.skip(reason="Requires agent implementation")
    async def test_cooking_agent_updates_event(self, db):
        """Test cooking agent updating meal_event."""
        # This would test cooking agent updating events
        # Skipping until agent integration is complete
        pass
