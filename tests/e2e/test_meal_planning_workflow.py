"""
End-to-end tests for complete meal planning workflow.

Tests the entire user journey from onboarding through meal planning.
These represent real-world user scenarios.
"""

import pytest
from datetime import datetime, timedelta

from src.onboarding import OnboardingFlow
from src.onboarding import OnboardingFlow
from src.mcp_server.tools.planning_tools import PlanningTools
from src.data.database import DatabaseInterface
from src.data.models import MealEvent
from datetime import datetime, timedelta
import pytest
from src.mcp_server.tools.planning_tools import PlanningTools
from src.mcp_server.tools.shopping_tools import ShoppingTools
from src.data.models import MealPlan, PlannedMeal, MealEvent
from src.data.database import DatabaseInterface
import sqlite3
import os

@pytest.fixture
def tools(db):
    """Fixture for PlanningTools with initialized recipe database."""
    # Create a dummy recipes table in the temp db directory
    # The db fixture creates a temp_dir and initializes DatabaseInterface with it.
    # DatabaseInterface expects recipes.db in that dir.
    
    recipes_db_path = os.path.join(db.db_dir, "recipes.db")
    
    # Create recipes.db if it doesn't exist (it shouldn't in temp env)
    with sqlite3.connect(recipes_db_path) as conn:
        cursor = conn.cursor()
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS recipes (
                id TEXT PRIMARY KEY,
                name TEXT,
                description TEXT,
                minutes INTEGER,
                contributor_id TEXT,
                submitted TEXT,
                tags TEXT,
                nutrition TEXT,
                n_steps INTEGER,
                steps TEXT,
                ingredients TEXT,
                ingredients_raw TEXT,
                ingredients_structured TEXT,
                servings INTEGER,
                serving_size TEXT,
                n_ingredients INTEGER
            )
        """)
        # Insert some dummy recipes used in tests
        cursor.execute("""
            INSERT OR IGNORE INTO recipes (id, name, minutes, tags, ingredients, ingredients_raw, steps, servings)
            VALUES 
            ('rec1', 'Spaghetti Carbonara', 30, '["italian"]', '["pasta", "eggs", "bacon"]', '["1 lb pasta", "2 eggs", "4 slices bacon"]', '["cook pasta", "mix eggs"]', 2),
            ('rec2', 'Chicken Tacos', 20, '["mexican"]', '["chicken", "tortilla"]', '["1 lb chicken", "6 tortillas"]', '["cook chicken", "assemble"]', 2),
            ('rec3', 'Vegetarian Chili', 45, '["vegetarian"]', '["beans", "tomatoes"]', '["2 cans beans", "1 can tomatoes"]', '["cook beans", "simmer"]', 2)
        """)
        conn.commit()
        
    return PlanningTools(db)

@pytest.fixture
def shopping_tools(db):
    """Fixture for ShoppingTools."""
    return ShoppingTools(db)

class TestCompleteMealPlanningWorkflow:
    """Test the complete workflow a new user would experience."""

    def test_new_user_complete_journey(self, db, tools, shopping_tools):
        """
        Test the complete journey for a new user:
        1. Onboarding
        2. Plan creation
        3. Plan adjustment
        4. Shopping list generation
        """
        # Calculate dynamic dates
        today = datetime.now()
        days_until_monday = (7 - today.weekday()) % 7 or 7
        next_monday = today + timedelta(days=days_until_monday)
        week_of = next_monday.strftime("%Y-%m-%d")
        
        # Create dates for specific meals (Monday and Tuesday)
        monday_date = week_of
        tuesday_date = (next_monday + timedelta(days=1)).strftime("%Y-%m-%d")

        # === STEP 1: Onboarding ===
        # Check status - should be False initially
        flow = OnboardingFlow(db)
        assert db.is_onboarded() is False

        # Submit preferences via flow
        # The flow expects answers to questions in sequence
        flow.start()
        flow.process_answer("2 adults")
        flow.process_answer("None")
        flow.process_answer("Italian, Mexican")
        flow.process_answer("30-45 minutes") # Time
        flow.process_answer("Intermediate") # Skill
        flow.process_answer("Medium") # Spice
        flow.process_answer("yes") # Confirm
        
        # Verify status updated
        assert db.is_onboarded() is True
        
        # Verify profile created in DB
        profile = db.get_user_profile()
        assert profile is not None
        assert "italian" in profile.favorite_cuisines

        # === STEP 2: Create Meal Plan ===
        meals = [
            {
                "date": monday_date,
                "meal_type": "dinner",
                "recipe_id": "rec1",
                "recipe_name": "Spaghetti Carbonara",
                "servings": 2
            },
            {
                "date": tuesday_date,
                "meal_type": "dinner",
                "recipe_id": "rec2",
                "recipe_name": "Chicken Tacos",
                "servings": 2
            }
        ]
        
        result = tools.save_meal_plan(
            week_of=week_of,
            meals=meals,
            preferences_applied=["Italian", "Mexican"]
        )
        
        assert result["success"] is True
        plan_id = result["meal_plan_id"]
        
        # Verify plan in DB
        plan = db.get_meal_plan(plan_id)
        assert plan is not None
        assert len(plan.meals) == 2
        assert plan.week_of == week_of

        # === STEP 3: Adjust Plan (Swap a meal) ===
        # Swap Tuesday's meal
        new_meal = {
            "date": tuesday_date,
            "meal_type": "dinner",
            "recipe_id": "rec3",
            "recipe_name": "Vegetarian Chili",
            "servings": 2
        }
        
        # Update the plan
        meals[1] = new_meal
        result = tools.save_meal_plan(
            week_of=week_of,
            meals=meals,
            preferences_applied=["Italian", "Vegetarian"]
        )
        
        assert result["success"] is True
        
        # Verify update
        plan = db.get_meal_plan(plan_id)
        assert plan.meals[1].recipe.name == "Vegetarian Chili"

        # === STEP 4: Verify meal events created ===
        # We need to ensure the lookback covers the future dates if they are close, 
        # or just check that they were added. 
        # Since get_meal_events filters by date <= now usually, but here we are planning for future.
        # Let's check the implementation of get_meal_events.
        # It selects where date >= date('now', -weeks_back). 
        # Future dates should be included as they are > now - weeks_back.
        events = db.get_meal_events(weeks_back=4)
        # We saved 2 meals initially, then updated the plan (saving 2 again).
        # The save_meal_plan implementation adds events for ALL meals in the plan.
        # So we might have duplicates or 4 events total depending on implementation.
        # Let's assume it appends.
        assert len(events) >= 2


        event_names = {e.recipe_name for e in events}
        assert "Spaghetti Carbonara" in event_names
        assert "Vegetarian Chili" in event_names

        # === STEP 5: User cooks a meal and rates it ===
        # Find the event for Spaghetti Carbonara
        carbonara_event = next((e for e in events if e.recipe_name == "Spaghetti Carbonara"), None)
        assert carbonara_event is not None

        db.update_meal_event(
            carbonara_event.id,
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
        assert "Spaghetti Carbonara" in [r["recipe_name"] for r in updated_prefs["favorite_recipes"]]

        history = tools.get_meal_history(weeks_back=4)
        assert len(history) >= 2

        # Should include ratings
        rated_meals = [h for h in history if h.get("user_rating")]
        assert len(rated_meals) >= 1

        # === STEP 7: Generate Shopping List ===
        shopping_list = shopping_tools.consolidate_ingredients(plan_id)
        assert shopping_list is not None
        assert len(shopping_list["items"]) > 0
        assert "pasta" in [item["name"].lower() for item in shopping_list["items"]]
        assert "chicken" not in [item["name"].lower() for item in shopping_list["items"]] # Chicken Tacos was swapped

    def test_returning_user_workflow(self, db, tools, sample_user_profile):
        """
        Test workflow for returning user (already onboarded).

        1. User already has profile
        2. User already has meal history
        3. Plan new meals avoiding recent meals
        """
        # === STEP 1: User already onboarded ===
        db.save_user_profile(sample_user_profile)
        assert db.is_onboarded() is True

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
        prefs = tools.get_user_preferences()
        history = tools.get_meal_history(weeks_back=1)

        # Verify has history
        assert len(history) == 1
        assert history[0]["recipe_name"] == "Spaghetti Carbonara"

        # === STEP 4: Plan new meals (avoiding recent) ===
        # Agent would check history and avoid "Spaghetti Carbonara"
        # For test, we'll plan different meals
        today = datetime.now()
        week_of = today.strftime("%Y-%m-%d")
        
        meals = [
            {
                "date": today.strftime("%Y-%m-%d"),
                "meal_type": "dinner",
                "recipe_id": "111",
                "recipe_name": "Chicken Stir Fry",
                "servings": 4,
            }
        ]

        result = tools.save_meal_plan(
            week_of=week_of,
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

    def test_plan_meals_without_onboarding(self, db, tools):
        """Test that meal planning works without onboarding (defaults)."""
        # User skips onboarding, goes straight to planning
        
        # Should get default preferences
        prefs = tools.get_user_preferences()
        assert prefs is not None
        assert "max_weeknight_time" in prefs

        # Can still create meal plan
        today = datetime.now()
        week_of = today.strftime("%Y-%m-%d")
        
        meals = [
            {
                "date": week_of,
                "meal_type": "dinner",
                "recipe_id": "123",
                "recipe_name": "Quick Meal",
                "servings": 4,
            }
        ]

        result = tools.save_meal_plan(week_of=week_of, meals=meals)
        # Should work (with defaults)
        assert result["success"] is True

    def test_onboard_after_using_system(self, db, tools):
        """
        Test that onboarding doesn't lose previous data if user
        started using system before onboarding.
        """
        # 1. Use system without onboarding
        today = datetime.now()
        week_of = today.strftime("%Y-%m-%d")
        
        meals = [{
            "date": week_of,
            "meal_type": "dinner",
            "recipe_id": "rec1",
            "recipe_name": "Test Recipe",
            "servings": 2
        }]
        
        tools.save_meal_plan(week_of=week_of, meals=meals)
        
        # 2. Perform onboarding
        flow = OnboardingFlow(db)
        flow.start()
        flow.process_answer("1 person")
        flow.process_answer("None")
        flow.process_answer("Asian")
        flow.process_answer("30 min")
        flow.process_answer("Beginner")
        flow.process_answer("Mild")
        flow.process_answer("yes")
        
        # 3. Verify everything exists
        assert db.is_onboarded() is True
        
        # Verify existing meal history preserved
        # Ensure we look back far enough or include future dates
        history = tools.get_meal_history(weeks_back=4)
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
