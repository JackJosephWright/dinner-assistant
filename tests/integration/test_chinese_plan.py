#!/usr/bin/env python3
"""
Integration test for 7-day Chinese meal plan.

This test requires ANTHROPIC_API_KEY and will be skipped without it.
"""
import sys
import os
import pytest
from datetime import datetime, timedelta

# Add src to path
sys.path.insert(0, 'src')


# Skip entire module if no API key
pytestmark = pytest.mark.skipif(
    not os.environ.get("ANTHROPIC_API_KEY"),
    reason="Requires ANTHROPIC_API_KEY environment variable"
)


@pytest.fixture
def assistant():
    """Create MealPlanningAssistant - only runs if API key is available."""
    from main import MealPlanningAssistant
    return MealPlanningAssistant(
        db_dir="data",
        use_agentic=True
    )


@pytest.fixture
def next_week_of():
    """Get next Monday's date string."""
    today = datetime.now()
    days_until_monday = (7 - today.weekday()) % 7
    if days_until_monday == 0:
        days_until_monday = 7
    next_monday = today + timedelta(days=days_until_monday)
    return next_monday.strftime("%Y-%m-%d")


def test_chinese_meal_plan(assistant, next_week_of):
    """
    Test creating a 7-day Chinese meal plan.

    This is an integration test that exercises the full planning pipeline
    including LLM calls, database queries, and meal plan creation.
    """
    print("\n" + "=" * 60)
    print("Testing: 7-Day Chinese Meal Plan")
    print("=" * 60)

    print(f"\n1. Planning meals for week of {next_week_of}")
    print("   Requesting: 7-day Chinese meal plan")

    # Create plan
    result = assistant.plan_week(
        week_of=next_week_of,
        num_days=7
    )

    print(f"\n2. Result:")
    print(f"   Success: {result['success']}")

    assert result['success'], f"Plan creation failed: {result.get('error', 'Unknown error')}"

    meal_plan_id = result['meal_plan_id']
    print(f"   Meal Plan ID: {meal_plan_id}")

    # Load the meal plan
    print(f"\n3. Loading meal plan details...")
    meal_plan = assistant.db.get_meal_plan(meal_plan_id)

    assert meal_plan is not None, "Could not load meal plan"

    print(f"\n" + "=" * 60)
    print(f"MEAL PLAN: {meal_plan.week_of}")
    print("=" * 60)

    for i, meal in enumerate(meal_plan.meals, 1):
        print(f"\nDay {i}: {meal.date} ({meal.meal_type})")
        print(f"  Recipe: {meal.recipe.name}")
        print(f"  Cuisine: {meal.recipe.cuisine}")
        print(f"  Time: {meal.recipe.estimated_time} min")
        print(f"  Difficulty: {meal.recipe.difficulty}")
        print(f"  Servings: {meal.servings}")

    print("\n" + "=" * 60)
    print("✓ SUCCESS - Meal plan created!")
    print("=" * 60)

    # Verify we got the expected number of meals
    assert len(meal_plan.meals) == 7, f"Expected 7 meals, got {len(meal_plan.meals)}"


if __name__ == "__main__":
    # Allow running directly for debugging
    if not os.environ.get("ANTHROPIC_API_KEY"):
        print("ERROR: ANTHROPIC_API_KEY required")
        print("Set the environment variable and run again.")
        sys.exit(1)

    from main import MealPlanningAssistant

    assistant = MealPlanningAssistant(db_dir="data", use_agentic=True)
    today = datetime.now()
    days_until_monday = (7 - today.weekday()) % 7
    if days_until_monday == 0:
        days_until_monday = 7
    next_monday = today + timedelta(days=days_until_monday)
    week_of = next_monday.strftime("%Y-%m-%d")

    test_chinese_meal_plan(assistant, week_of)
