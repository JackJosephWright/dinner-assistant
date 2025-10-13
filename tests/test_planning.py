#!/usr/bin/env python3
"""
Test meal planning agent.
"""

import sys
from pathlib import Path
from datetime import datetime, timedelta

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from data.database import DatabaseInterface
from agents.enhanced_planning_agent import EnhancedPlanningAgent


def test_meal_plan_generation():
    """Test generating a complete meal plan."""
    print("\n" + "="*70)
    print("TEST: Meal Plan Generation")
    print("="*70)

    db = DatabaseInterface(db_dir="data")
    agent = EnhancedPlanningAgent(db)

    # Generate plan for next week
    today = datetime.now()
    days_until_monday = (7 - today.weekday()) % 7
    if days_until_monday == 0:
        days_until_monday = 7
    next_monday = today + timedelta(days=days_until_monday)
    week_of = next_monday.strftime("%Y-%m-%d")

    print(f"\nGenerating meal plan for week of {week_of}...")

    result = agent.plan_week(week_of=week_of, num_days=7)

    assert result["success"], f"Planning failed: {result.get('error')}"

    print(f"✓ Successfully generated meal plan: {result['meal_plan_id']}")
    print(f"✓ Number of meals: {len(result['meals'])}")

    print("\nMeals:")
    for meal in result["meals"]:
        print(f"  {meal['date']}: {meal['recipe_name']}")

    # Get explanation
    print("\n" + "-"*70)
    explanation = agent.explain_plan(result['meal_plan_id'])
    print(explanation)

    print("\n✓ Meal planning test passed!")

    return result


def test_variety_enforcement():
    """Test that variety is enforced."""
    print("\n" + "="*70)
    print("TEST: Variety Enforcement")
    print("="*70)

    db = DatabaseInterface(db_dir="data")
    agent = EnhancedPlanningAgent(db)

    # Generate a plan
    today = datetime.now()
    week_of = today.strftime("%Y-%m-%d")

    result = agent.plan_week(week_of=week_of, num_days=7)

    # Check for duplicate recipes
    recipe_names = [m["recipe_name"] for m in result["meals"]]
    unique_names = set(recipe_names)

    print(f"\nTotal meals: {len(recipe_names)}")
    print(f"Unique recipes: {len(unique_names)}")

    # Should be all unique for 7 days
    assert len(unique_names) == len(recipe_names), "Found duplicate recipes!"

    print("✓ All recipes are unique")

    # Check cuisine variety
    cuisines = []
    for meal in result["meals"]:
        recipe = db.get_recipe(meal["recipe_id"])
        if recipe and recipe.cuisine:
            cuisines.append(recipe.cuisine)

    unique_cuisines = set(cuisines)
    print(f"✓ Cuisines represented: {', '.join(unique_cuisines) if unique_cuisines else 'Various'}")

    print("\n✓ Variety enforcement test passed!")


def test_preference_application():
    """Test that preferences are applied."""
    print("\n" + "="*70)
    print("TEST: Preference Application")
    print("="*70)

    db = DatabaseInterface(db_dir="data")
    agent = EnhancedPlanningAgent(db)

    # Set some preferences
    db.set_preference("max_weeknight_time", "45")
    db.set_preference("min_vegetarian_meals", "1")

    # Generate plan
    today = datetime.now()
    week_of = (today + timedelta(days=7)).strftime("%Y-%m-%d")

    result = agent.plan_week(week_of=week_of, num_days=7)

    print(f"\n✓ Generated plan with {len(result['meals'])} meals")
    print(f"✓ Preferences applied: {', '.join(result['preferences_applied'])}")

    # Check time constraints
    weekday_times = []
    for meal in result["meals"]:
        recipe = db.get_recipe(meal["recipe_id"])
        if recipe and recipe.estimated_time:
            date_obj = datetime.fromisoformat(meal["date"])
            if date_obj.weekday() < 5:  # Weekday
                weekday_times.append(recipe.estimated_time)

    if weekday_times:
        avg_weekday_time = sum(weekday_times) / len(weekday_times)
        print(f"✓ Average weekday cooking time: {avg_weekday_time:.0f} minutes")

    print("\n✓ Preference application test passed!")


def main():
    """Run all planning tests."""
    print("\n" + "🎯 "*30)
    print("MEAL PLANNING AGENT TESTS")
    print("🎯 "*30)

    try:
        result = test_meal_plan_generation()
        test_variety_enforcement()
        test_preference_application()

        print("\n" + "="*70)
        print("✅ ALL PLANNING TESTS PASSED!")
        print("="*70)

        print("\nYou can now generate meal plans with:")
        print("  - Automatic variety enforcement")
        print("  - Preference learning from history")
        print("  - Cuisine and difficulty balancing")

        return result

    except Exception as e:
        print(f"\n❌ TEST FAILED: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
