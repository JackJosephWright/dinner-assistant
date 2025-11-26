#!/usr/bin/env python3
"""
Simple test to create a 7-day Chinese meal plan.
Run outside Flask to see what the planning agent returns.
"""
import sys
import os

# Add src to path
sys.path.insert(0, 'src')

from main import MealPlanningAssistant
from datetime import datetime, timedelta

print("=" * 60)
print("Testing: 7-Day Chinese Meal Plan")
print("=" * 60)

# Initialize assistant
print("\n1. Initializing assistant...")
assistant = MealPlanningAssistant(
    db_dir="data",
    use_agentic=True
)
print("✓ Assistant initialized")

# Get next Monday
today = datetime.now()
days_until_monday = (7 - today.weekday()) % 7
if days_until_monday == 0:
    days_until_monday = 7
next_monday = today + timedelta(days=days_until_monday)
week_of = next_monday.strftime("%Y-%m-%d")

print(f"\n2. Planning meals for week of {week_of}")
print("   Requesting: 7-day Chinese meal plan")

# Create plan (simple version - just 7 days)
result = assistant.plan_week(
    week_of=week_of,
    num_days=7
)

print(f"\n3. Result:")
print(f"   Success: {result['success']}")

if result['success']:
    meal_plan_id = result['meal_plan_id']
    print(f"   Meal Plan ID: {meal_plan_id}")

    # Load the meal plan
    print(f"\n4. Loading meal plan details...")
    meal_plan = assistant.db.get_meal_plan(meal_plan_id)

    if meal_plan:
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
    else:
        print("✗ ERROR: Could not load meal plan")
else:
    print(f"   Error: {result.get('error', 'Unknown error')}")
    print("\n✗ FAILED")
