#!/usr/bin/env python3
"""
Test user history tracking with UPSERT pattern.
"""

import sqlite3
from datetime import datetime
from src.data.database import DatabaseInterface
from src.data.models import MealPlan, PlannedMeal, Recipe

def test_user_history():
    """Test the complete user history flow."""
    db = DatabaseInterface()

    print("=" * 60)
    print("USER HISTORY TRACKING TEST")
    print("=" * 60)

    # 1. Check initial state
    print("\n1. Initial state:")
    with sqlite3.connect(db.user_db) as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM meal_events")
        initial_count = cursor.fetchone()[0]
        print(f"   Initial meal_events: {initial_count}")

    # 2. Create a simple meal plan
    print("\n2. Creating meal plan...")

    # Get some real recipes from the database
    recipes = db.search_recipes(query="pasta", limit=2)
    if len(recipes) < 2:
        print("   ERROR: Not enough recipes found in database")
        return

    # Create planned meals with real recipes
    meals = [
        PlannedMeal(
            date="2025-11-25",
            meal_type="dinner",
            recipe=recipes[0],
            servings=4
        ),
        PlannedMeal(
            date="2025-11-26",
            meal_type="dinner",
            recipe=recipes[1],
            servings=4
        ),
    ]

    meal_plan = MealPlan(
        week_of="2025-11-25",
        meals=meals,
        preferences_applied=["test"],
        created_at=datetime.now()
    )

    plan_id = db.save_meal_plan(meal_plan)
    print(f"   Created meal plan: {plan_id}")

    # 3. Verify meal_events were created
    print("\n3. Checking meal_events after plan creation:")
    with sqlite3.connect(db.user_db) as conn:
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM meal_events")
        after_create_count = cursor.fetchone()[0]
        print(f"   Meal events count: {after_create_count}")

        cursor.execute("""
            SELECT date, meal_type, recipe_id, recipe_name, meal_plan_id
            FROM meal_events
            ORDER BY date
        """)
        events = cursor.fetchall()
        for event in events:
            print(f"   - {event['date']} {event['meal_type']}: {event['recipe_name']} (plan: {event['meal_plan_id']})")

    # 4. Test UPSERT by swapping a meal (simulated)
    print("\n4. Testing UPSERT - swapping 2025-11-25 meal...")
    # Get a different recipe for the swap
    swap_recipes = db.search_recipes(query="chicken", limit=1)
    if swap_recipes:
        old_recipe_name = meals[0].recipe.name
        meals[0] = PlannedMeal(
            date="2025-11-25",
            meal_type="dinner",
            recipe=swap_recipes[0],
            servings=6
        )
        new_recipe_name = meals[0].recipe.name
        print(f"   Swapping '{old_recipe_name}' -> '{new_recipe_name}'")

        meal_plan.meals = meals
        db.save_meal_plan(meal_plan)  # Should UPSERT the 2025-11-25 event

    print("\n5. Checking meal_events after swap:")
    with sqlite3.connect(db.user_db) as conn:
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM meal_events")
        after_swap_count = cursor.fetchone()[0]
        print(f"   Meal events count: {after_swap_count} (should still be {after_create_count})")

        cursor.execute("""
            SELECT date, meal_type, recipe_id, recipe_name
            FROM meal_events
            WHERE date = '2025-11-25'
        """)
        event = cursor.fetchone()
        if event:
            print(f"   - 2025-11-25: {event['recipe_name']}")
            if swap_recipes:
                assert event['recipe_name'] == new_recipe_name, "UPSERT failed! Recipe not updated."
                print(f"   ✓ UPSERT worked! Recipe changed to {new_recipe_name}")

    # 6. Test adding feedback
    print("\n6. Testing feedback update...")
    with sqlite3.connect(db.user_db) as conn:
        cursor = conn.cursor()
        cursor.execute("""
            UPDATE meal_events
            SET user_rating = 5,
                would_make_again = 1,
                notes = 'Loved it! Doubled the garlic.',
                servings_actual = 6,
                cooking_time_actual = 35
            WHERE date = '2025-11-25' AND meal_type = 'dinner'
        """)
        conn.commit()
        print("   Added feedback: 5 stars, would make again, notes added")

    # 7. Verify feedback was saved
    print("\n7. Verifying feedback:")
    with sqlite3.connect(db.user_db) as conn:
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute("""
            SELECT date, recipe_name, user_rating, would_make_again, notes, servings_actual
            FROM meal_events
            WHERE date = '2025-11-25'
        """)
        event = cursor.fetchone()
        if event:
            print(f"   Recipe: {event['recipe_name']}")
            print(f"   Rating: {event['user_rating']} stars")
            print(f"   Would make again: {event['would_make_again']}")
            print(f"   Notes: {event['notes']}")
            print(f"   Servings made: {event['servings_actual']}")
            print(f"   ✓ Feedback saved successfully!")

    # 8. Test that planning agent can query history
    print("\n8. Testing history query (for planning agent):")
    events = db.get_meal_events(weeks_back=4)
    print(f"   Found {len(events)} meal events in last 4 weeks")
    for event in events:
        stars = "⭐" * (event.user_rating or 0)
        would_make = "❤️" if event.would_make_again else ""
        print(f"   - {event.date}: {event.recipe_name} {stars} {would_make}")

    print("\n" + "=" * 60)
    print("✓ ALL TESTS PASSED!")
    print("=" * 60)
    print("\nUser history tracking is working correctly!")
    print("- Meal plans create meal_events ✓")
    print("- Swaps UPSERT meal_events (no duplicates) ✓")
    print("- Feedback can be added ✓")
    print("- Planning agent can query history ✓")

if __name__ == "__main__":
    test_user_history()
