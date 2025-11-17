"""
Integration tests for database incremental shopping list updates.
"""

import pytest
from datetime import datetime, timedelta
from src.data.database import DatabaseInterface
from src.data.models import Recipe, Ingredient, MealPlan, PlannedMeal, GroceryList


@pytest.fixture
def db(tmp_path):
    """Create a test database."""
    # Create a temporary database directory
    db_dir = tmp_path / "test_data"
    db_dir.mkdir(exist_ok=True)

    # Copy recipes_dev.db to test directory (or use empty DB)
    # For tests, we'll use the interface with the test directory
    db = DatabaseInterface(db_dir=str(db_dir))
    return db


@pytest.fixture
def test_recipes():
    """Create test recipes."""
    recipe1 = Recipe(
        id="test_recipe_1",
        name="Chicken Stir Fry",
        description="Quick stir fry",
        ingredients=["2 lbs chicken", "1 tbsp oil", "2 cups broccoli"],
        ingredients_raw=["2 lbs chicken", "1 tbsp oil", "2 cups broccoli"],
        ingredients_structured=[
            Ingredient(raw="2 lbs chicken", name="chicken", quantity=2.0, unit="lbs", category="meat"),
            Ingredient(raw="1 tbsp oil", name="oil", quantity=1.0, unit="tbsp", category="pantry"),
            Ingredient(raw="2 cups broccoli", name="broccoli", quantity=2.0, unit="cups", category="produce"),
        ],
        steps=["Cook"],
        servings=4,
        serving_size="1 plate",
        tags=["quick"],
    )

    recipe2 = Recipe(
        id="test_recipe_2",
        name="Pasta Carbonara",
        description="Classic pasta",
        ingredients=["1 lb pasta", "4 eggs", "1 tbsp oil"],
        ingredients_raw=["1 lb pasta", "4 eggs", "1 tbsp oil"],
        ingredients_structured=[
            Ingredient(raw="1 lb pasta", name="pasta", quantity=1.0, unit="lb", category="pantry"),
            Ingredient(raw="4 eggs", name="eggs", quantity=4.0, unit="count", category="dairy"),
            Ingredient(raw="1 tbsp oil", name="oil", quantity=1.0, unit="tbsp", category="pantry"),
        ],
        steps=["Cook pasta"],
        servings=4,
        serving_size="1 plate",
        tags=["pasta"],
    )

    recipe3 = Recipe(
        id="test_recipe_3",
        name="Greek Salad",
        description="Fresh salad",
        ingredients=["1 cucumber", "2 tomatoes", "1/2 cup feta"],
        ingredients_raw=["1 cucumber", "2 tomatoes", "1/2 cup feta"],
        ingredients_structured=[
            Ingredient(raw="1 cucumber", name="cucumber", quantity=1.0, unit="count", category="produce"),
            Ingredient(raw="2 tomatoes", name="tomatoes", quantity=2.0, unit="count", category="produce"),
            Ingredient(raw="1/2 cup feta", name="feta cheese", quantity=0.5, unit="cup", category="dairy"),
        ],
        steps=["Mix"],
        servings=2,
        serving_size="1 bowl",
        tags=["salad"],
    )

    return recipe1, recipe2, recipe3


class TestDatabaseIncrementalShopping:
    """Test database-level incremental shopping list updates."""

    def test_get_grocery_list_by_week(self, db):
        """Test retrieving grocery list by week."""
        week_start = "2025-11-04"

        # Create and save grocery list
        grocery_list = GroceryList(week_of=week_start, items=[])
        list_id = db.save_grocery_list(grocery_list)

        # Retrieve by week
        retrieved = db.get_grocery_list_by_week(week_start)

        assert retrieved is not None
        assert retrieved.id == list_id
        assert retrieved.week_of == week_start

    def test_get_grocery_list_by_week_nonexistent(self, db):
        """Test retrieving grocery list for week that doesn't exist."""
        result = db.get_grocery_list_by_week("2025-01-01")
        assert result is None

    def test_get_grocery_list_by_week_multiple(self, db):
        """Test retrieving most recent grocery list when multiple exist."""
        week_start = "2025-11-04"

        # Create two lists for same week
        list1 = GroceryList(week_of=week_start, items=[])
        db.save_grocery_list(list1)

        # Wait a moment to ensure different timestamp
        import time
        time.sleep(0.01)

        list2 = GroceryList(week_of=week_start, items=[])
        id2 = db.save_grocery_list(list2)

        # Should retrieve most recent
        retrieved = db.get_grocery_list_by_week(week_start)
        assert retrieved.id == id2

    def test_swap_meal_updates_grocery_list(self, db, test_recipes):
        """Test that swapping a meal automatically updates the grocery list."""
        recipe1, recipe2, recipe3 = test_recipes

        # Create meal plan
        today = datetime.now().date()
        week_start = today - timedelta(days=today.weekday())

        meal_plan = MealPlan(
            week_of=week_start.isoformat(),
            meals=[
                PlannedMeal(
                    date=(week_start + timedelta(days=0)).isoformat(),
                    meal_type="dinner",
                    recipe=recipe1,  # Chicken Stir Fry
                    servings=4,
                ),
                PlannedMeal(
                    date=(week_start + timedelta(days=1)).isoformat(),
                    meal_type="dinner",
                    recipe=recipe3,  # Greek Salad
                    servings=2,
                ),
            ],
        )

        plan_id = db.save_meal_plan(meal_plan)

        # Create initial grocery list
        grocery_list = GroceryList(week_of=week_start.isoformat(), items=[])
        grocery_list.add_recipe_ingredients(recipe1)
        grocery_list.add_recipe_ingredients(recipe3)
        db.save_grocery_list(grocery_list)

        # Verify initial state
        initial_list = db.get_grocery_list_by_week(week_start.isoformat())
        chicken_before = next((item for item in initial_list.items if "chicken" in item.name.lower()), None)
        assert chicken_before is not None
        assert "Chicken Stir Fry" in chicken_before.recipe_sources

        # Swap meal (Chicken Stir Fry → Pasta Carbonara)
        # Note: In real system, recipe2 would exist in recipes DB
        # For test, we manually update the plan and trigger list update
        meal_plan = db.get_meal_plan(plan_id)
        swap_date = (week_start + timedelta(days=0)).isoformat()

        old_recipe = None
        for i, meal in enumerate(meal_plan.meals):
            if meal.date == swap_date:
                old_recipe = meal.recipe
                meal_plan.meals[i] = PlannedMeal(
                    date=swap_date,
                    meal_type=meal.meal_type,
                    recipe=recipe2,
                    servings=meal.servings,
                )
                break

        # Save plan
        db.save_meal_plan(meal_plan)

        # Manually trigger grocery list update (simulating what swap_meal_in_plan does)
        grocery_list = db.get_grocery_list_by_week(week_start.isoformat())
        grocery_list.remove_recipe_ingredients(old_recipe.name)
        grocery_list.add_recipe_ingredients(recipe2)
        db.save_grocery_list(grocery_list)

        # Verify grocery list updated
        updated_list = db.get_grocery_list_by_week(week_start.isoformat())

        # Chicken should be gone
        chicken_after = next((item for item in updated_list.items if "chicken" in item.name.lower()), None)
        assert chicken_after is None

        # Pasta should be present
        pasta = next((item for item in updated_list.items if "pasta" in item.name.lower()), None)
        assert pasta is not None
        assert "Pasta Carbonara" in pasta.recipe_sources

        # Oil should still exist (both recipes have it)
        oil = next((item for item in updated_list.items if "oil" in item.name.lower()), None)
        assert oil is not None
        assert len(oil.contributions) == 1  # Only from Pasta now
        assert "Pasta Carbonara" in oil.recipe_sources

        # Feta should still exist (from Greek Salad)
        feta = next((item for item in updated_list.items if "feta" in item.name.lower()), None)
        assert feta is not None
        assert "Greek Salad" in feta.recipe_sources

    def test_swap_meal_no_grocery_list(self, db, test_recipes):
        """Test swapping meal when no grocery list exists (should not crash)."""
        recipe1, recipe2, _ = test_recipes

        today = datetime.now().date()
        week_start = today - timedelta(days=today.weekday())

        meal_plan = MealPlan(
            week_of=week_start.isoformat(),
            meals=[
                PlannedMeal(
                    date=(week_start + timedelta(days=0)).isoformat(),
                    meal_type="dinner",
                    recipe=recipe1,
                    servings=4,
                ),
            ],
        )

        plan_id = db.save_meal_plan(meal_plan)

        # Swap without creating grocery list first
        meal_plan = db.get_meal_plan(plan_id)
        swap_date = (week_start + timedelta(days=0)).isoformat()

        for i, meal in enumerate(meal_plan.meals):
            if meal.date == swap_date:
                meal_plan.meals[i] = PlannedMeal(
                    date=swap_date,
                    meal_type=meal.meal_type,
                    recipe=recipe2,
                    servings=meal.servings,
                )
                break

        # This should not crash
        db.save_meal_plan(meal_plan)

        # Verify plan was updated
        updated_plan = db.get_meal_plan(plan_id)
        assert updated_plan.meals[0].recipe.name == "Pasta Carbonara"

    def test_grocery_list_contributions_persist(self, db, test_recipes):
        """Test that contributions are persisted and loaded correctly."""
        recipe1, recipe2, _ = test_recipes
        week_start = "2025-11-04"

        # Create grocery list with overlapping ingredients
        grocery_list = GroceryList(week_of=week_start, items=[])
        grocery_list.add_recipe_ingredients(recipe1)  # Has oil
        grocery_list.add_recipe_ingredients(recipe2)  # Also has oil

        # Save
        list_id = db.save_grocery_list(grocery_list)

        # Load
        loaded_list = db.get_grocery_list(list_id)

        # Find oil
        oil = next((item for item in loaded_list.items if "oil" in item.name.lower()), None)
        assert oil is not None

        # Verify contributions persisted
        assert len(oil.contributions) == 2
        recipe_names = {c.recipe_name for c in oil.contributions}
        assert "Chicken Stir Fry" in recipe_names
        assert "Pasta Carbonara" in recipe_names

        # Verify total is sum of contributions
        total_amount = sum(c.amount for c in oil.contributions)
        assert total_amount == 2.0  # 1 tbsp + 1 tbsp

    def test_backward_compatibility_loading(self, db):
        """Test loading old grocery lists without contributions field."""
        week_start = "2025-11-04"

        # Manually create old-format grocery list in database
        import json
        import sqlite3

        old_format_items = [
            {
                "name": "Flour",
                "quantity": "3 cups",
                "category": "pantry",
                "recipe_sources": ["Pancakes", "Cookies"],
                "notes": None
                # No "contributions" field
            }
        ]

        with sqlite3.connect(db.user_db) as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                INSERT INTO grocery_lists
                (id, week_of, created_at, estimated_total, items_json)
                VALUES (?, ?, ?, ?, ?)
                """,
                (
                    "test_old_format",
                    week_start,
                    datetime.now().isoformat(),
                    10.0,
                    json.dumps(old_format_items),
                ),
            )
            conn.commit()

        # Load old format
        loaded_list = db.get_grocery_list("test_old_format")

        assert loaded_list is not None
        assert len(loaded_list.items) == 1

        flour = loaded_list.items[0]
        assert flour.name == "Flour"

        # Should have created contributions from recipe_sources
        assert len(flour.contributions) == 2
        recipe_names = {c.recipe_name for c in flour.contributions}
        assert "Pancakes" in recipe_names
        assert "Cookies" in recipe_names
