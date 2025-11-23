"""
Integration tests for shopping list extra items persistence.
"""

import pytest
from datetime import datetime
from src.data.models import MealPlan, PlannedMeal, Recipe
from src.mcp_server.tools.shopping_tools import ShoppingTools

@pytest.fixture
def shopping_tools(db):
    return ShoppingTools(db)

def test_extra_items_persistence(db, shopping_tools):
    """Test that extra items persist when shopping list is regenerated."""
    
    # 1. Create a meal plan
    week_of = "2025-01-20"
    recipe = Recipe(
        id="test_recipe",
        name="Test Recipe",
        description="Test",
        ingredients=["chicken"],
        ingredients_raw=["1 lb chicken"],
        steps=[],
        servings=4,
        serving_size="1 portion",
        tags=[]
    )
    # Manually insert recipe into the test database
    import sqlite3
    import json
    
    with sqlite3.connect(db.recipes_db) as conn:
        cursor = conn.cursor()
        # Create recipes table if it doesn't exist (it might not in a fresh test db)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS recipes (
                id INTEGER PRIMARY KEY,
                name TEXT,
                description TEXT,
                ingredients TEXT,
                ingredients_raw TEXT,
                steps TEXT,
                servings INTEGER,
                serving_size TEXT,
                tags TEXT,
                minutes INTEGER,
                contributor_id INTEGER,
                submitted TEXT,
                n_steps INTEGER,
                n_ingredients INTEGER
            )
        """)
        
        cursor.execute("""
            INSERT INTO recipes (
                id, name, description, ingredients, ingredients_raw, steps, 
                servings, serving_size, tags, minutes, n_steps, n_ingredients
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            12345, # Numeric ID for DB
            recipe.name,
            recipe.description,
            str(recipe.ingredients),
            str(recipe.ingredients_raw),
            str(recipe.steps),
            recipe.servings,
            recipe.serving_size,
            str(recipe.tags),
            30, 5, 5
        ))
        
    # Update recipe object with the numeric ID we just used
    recipe.id = "12345"
    
    meal_plan = MealPlan(
        week_of=week_of,
        meals=[
            PlannedMeal(
                date="2025-01-20",
                meal_type="dinner",
                recipe=recipe,
                servings=4
            )
        ]
    )
    meal_plan_id = db.save_meal_plan(meal_plan)
    
    # 2. Generate initial shopping list
    result1 = shopping_tools.consolidate_ingredients(meal_plan_id)
    assert result1["success"]
    list_id = result1["grocery_list_id"]
    
    # 3. Add extra items
    extras = [
        {"name": "Bananas", "quantity": "6", "category": "produce"},
        {"name": "Milk", "quantity": "1 gallon", "category": "dairy"}
    ]
    add_result = shopping_tools.add_extra_items(list_id, extras)
    assert add_result["success"]
    assert add_result["total_extra_items"] == 2
    
    # Verify extras are there and in correct sections
    grocery_list = db.get_grocery_list(list_id)
    assert len(grocery_list.extra_items) == 2
    assert grocery_list.extra_items[0].name == "Bananas"
    
    # Check integration into store_sections
    assert "produce" in grocery_list.store_sections
    produce_names = [item.name for item in grocery_list.store_sections["produce"]]
    assert "Bananas" in produce_names
    
    assert "dairy" in grocery_list.store_sections
    dairy_names = [item.name for item in grocery_list.store_sections["dairy"]]
    assert "Milk" in dairy_names
    
    # 4. Regenerate shopping list (simulate meal plan update)
    # This calls consolidate_ingredients again
    result2 = shopping_tools.consolidate_ingredients(meal_plan_id)
    assert result2["success"]
    new_list_id = result2["grocery_list_id"]
    
    # 5. Verify extras persisted
    new_list = db.get_grocery_list(new_list_id)
    assert len(new_list.extra_items) == 2
    assert new_list.extra_items[0].name == "Bananas"
    assert new_list.extra_items[1].name == "Milk"
    
    # 6. Test clearing extras
    clear_result = shopping_tools.clear_extra_items(new_list_id)
    assert clear_result["success"]
    
    # Verify empty
    final_list = db.get_grocery_list(new_list_id)
    assert len(final_list.extra_items) == 0

def test_sequential_adds(db, shopping_tools):
    """Test adding items sequentially preserves previous items."""
    
    # 1. Create a meal plan
    week_of = "2025-02-01"
    meal_plan = MealPlan(
        week_of=week_of,
        meals=[]
    )
    meal_plan_id = db.save_meal_plan(meal_plan)
    
    # 2. Generate initial shopping list
    result1 = shopping_tools.consolidate_ingredients(meal_plan_id)
    list_id = result1["grocery_list_id"]
    
    # 3. Add Bananas
    shopping_tools.add_extra_items(list_id, [{"name": "Bananas", "quantity": "6"}])
    
    # Verify Bananas
    list_after_bananas = db.get_grocery_list(list_id)
    assert len(list_after_bananas.extra_items) == 1
    assert list_after_bananas.extra_items[0].name == "Bananas"
    # Check auto-categorization
    assert list_after_bananas.extra_items[0].category == "produce"
    
    # 4. Add Bread
    shopping_tools.add_extra_items(list_id, [{"name": "Bread", "quantity": "1 loaf"}])
    
    # Verify BOTH are present
    list_after_bread = db.get_grocery_list(list_id)
    assert len(list_after_bread.extra_items) == 2
    names = [item.name for item in list_after_bread.extra_items]
    assert "Bananas" in names
    assert "Bread" in names
    
    # Verify Bread categorization
    bread_item = next(item for item in list_after_bread.extra_items if item.name == "Bread")
    assert bread_item.category == "bakery"
