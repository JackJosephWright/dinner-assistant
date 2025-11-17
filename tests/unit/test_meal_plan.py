#!/usr/bin/env python3
"""
Test script for enhanced MealPlan implementation.

Tests the new MealPlan with embedded PlannedMeal/Recipe objects.
"""

import json
from datetime import datetime
from src.data.models import Recipe, PlannedMeal, MealPlan, Ingredient
from src.data.database import DatabaseInterface


def test_create_meal_plan():
    """Test creating a MealPlan with embedded PlannedMeals."""
    print("=" * 60)
    print("TEST 1: Create MealPlan with Embedded Recipes")
    print("=" * 60)

    # Load enriched recipes from dev database
    db = DatabaseInterface('data')
    recipe1 = db.get_recipe('71247')  # Cherry Streusel Cobbler
    recipe2 = db.get_recipe('76133')  # Reuben and Swiss Casserole Bake

    print(f"Recipe 1: {recipe1.name}")
    print(f"Recipe 2: {recipe2.name}")

    # Create meals
    meal1 = PlannedMeal(
        date="2025-10-28",
        meal_type="dinner",
        recipe=recipe1,
        servings=4
    )

    meal2 = PlannedMeal(
        date="2025-10-29",
        meal_type="dinner",
        recipe=recipe2,
        servings=6
    )

    # Create meal plan
    plan = MealPlan(
        week_of="2025-10-28",
        meals=[meal1, meal2],
        preferences_applied=["quick-meals"]
    )

    print(f"\nMeal Plan: {plan}")

    assert len(plan.meals) == 2, "Should have 2 meals"
    assert all(m.recipe is not None for m in plan.meals), "All meals should have embedded recipes"

    print("\n✅ PASSED\n")


def test_get_meals_for_day():
    """Test getting meals for a specific day."""
    print("=" * 60)
    print("TEST 2: Get Meals for Day")
    print("=" * 60)

    db = DatabaseInterface('data')
    recipe1 = db.get_recipe('71247')  # Cherry Streusel Cobbler
    recipe2 = db.get_recipe('76133')  # Reuben and Swiss Casserole Bake

    # Create meals for different days
    meal1 = PlannedMeal(date="2025-10-28", meal_type="lunch", recipe=recipe1, servings=2)
    meal2 = PlannedMeal(date="2025-10-28", meal_type="dinner", recipe=recipe2, servings=4)
    meal3 = PlannedMeal(date="2025-10-29", meal_type="dinner", recipe=recipe1, servings=4)

    plan = MealPlan(week_of="2025-10-28", meals=[meal1, meal2, meal3])

    # Get meals for Oct 28
    oct28_meals = plan.get_meals_for_day("2025-10-28")

    print(f"Meals for 2025-10-28: {len(oct28_meals)}")
    for meal in oct28_meals:
        print(f"  - {meal.meal_type}: {meal.recipe.name}")

    assert len(oct28_meals) == 2, "Should have 2 meals for Oct 28"
    assert all(m.date == "2025-10-28" for m in oct28_meals), "All should be Oct 28"

    # Get meals for Oct 29
    oct29_meals = plan.get_meals_for_day("2025-10-29")
    assert len(oct29_meals) == 1, "Should have 1 meal for Oct 29"

    print("\n✅ PASSED\n")


def test_get_meals_by_type():
    """Test getting meals by type."""
    print("=" * 60)
    print("TEST 3: Get Meals by Type")
    print("=" * 60)

    db = DatabaseInterface('data')
    recipe = db.get_recipe('71247')

    # Create meals of different types
    meal1 = PlannedMeal(date="2025-10-28", meal_type="breakfast", recipe=recipe, servings=2)
    meal2 = PlannedMeal(date="2025-10-28", meal_type="dinner", recipe=recipe, servings=4)
    meal3 = PlannedMeal(date="2025-10-29", meal_type="dinner", recipe=recipe, servings=4)

    plan = MealPlan(week_of="2025-10-28", meals=[meal1, meal2, meal3])

    # Get dinners
    dinners = plan.get_meals_by_type("dinner")

    print(f"Dinners: {len(dinners)}")
    for meal in dinners:
        print(f"  - {meal.date}: {meal.recipe.name}")

    assert len(dinners) == 2, "Should have 2 dinners"
    assert all(m.meal_type == "dinner" for m in dinners), "All should be dinner"

    # Get breakfasts
    breakfasts = plan.get_meals_by_type("breakfast")
    assert len(breakfasts) == 1, "Should have 1 breakfast"

    print("\n✅ PASSED\n")


def test_get_date_range():
    """Test getting date range."""
    print("=" * 60)
    print("TEST 4: Get Date Range")
    print("=" * 60)

    db = DatabaseInterface('data')
    recipe = db.get_recipe('71247')

    # Create meals across a week
    meal1 = PlannedMeal(date="2025-10-28", meal_type="dinner", recipe=recipe, servings=4)
    meal2 = PlannedMeal(date="2025-10-30", meal_type="dinner", recipe=recipe, servings=4)
    meal3 = PlannedMeal(date="2025-11-02", meal_type="dinner", recipe=recipe, servings=4)

    plan = MealPlan(week_of="2025-10-28", meals=[meal1, meal2, meal3])

    start, end = plan.get_date_range()

    print(f"Date range: {start} to {end}")

    assert start == "2025-10-28", "Start should be Oct 28"
    assert end == "2025-11-02", "End should be Nov 2"

    # Test empty plan
    empty_plan = MealPlan(week_of="2025-10-28", meals=[])
    start_empty, end_empty = empty_plan.get_date_range()
    assert start_empty == "2025-10-28", "Empty plan should return week_of"

    print("\n✅ PASSED\n")


def test_get_all_ingredients():
    """Test getting all ingredients for shopping list."""
    print("=" * 60)
    print("TEST 5: Get All Ingredients")
    print("=" * 60)

    db = DatabaseInterface('data')
    recipe1 = db.get_recipe('71247')  # Cherry Streusel Cobbler
    recipe2 = db.get_recipe('76133')  # Reuben and Swiss Casserole Bake

    meal1 = PlannedMeal(date="2025-10-28", meal_type="dinner", recipe=recipe1, servings=4)
    meal2 = PlannedMeal(date="2025-10-29", meal_type="dinner", recipe=recipe2, servings=4)

    plan = MealPlan(week_of="2025-10-28", meals=[meal1, meal2])

    # Get all ingredients
    all_ingredients = plan.get_all_ingredients()

    print(f"Total ingredients across all meals: {len(all_ingredients)}")
    print(f"\nFirst 5 ingredients:")
    for i, ing in enumerate(all_ingredients[:5], 1):
        print(f"  {i}. {ing.quantity} {ing.unit or ''} {ing.name} ({ing.category})")

    assert len(all_ingredients) > 0, "Should have ingredients"
    assert all(isinstance(ing, Ingredient) for ing in all_ingredients), "All should be Ingredient objects"

    print("\n✅ PASSED\n")


def test_get_shopping_list_by_category():
    """Test getting shopping list grouped by category."""
    print("=" * 60)
    print("TEST 6: Get Shopping List by Category")
    print("=" * 60)

    db = DatabaseInterface('data')
    recipe1 = db.get_recipe('71247')  # Cherry Streusel Cobbler
    recipe2 = db.get_recipe('76133')  # Reuben and Swiss Casserole Bake

    meal1 = PlannedMeal(date="2025-10-28", meal_type="dinner", recipe=recipe1, servings=4)
    meal2 = PlannedMeal(date="2025-10-29", meal_type="dinner", recipe=recipe2, servings=4)

    plan = MealPlan(week_of="2025-10-28", meals=[meal1, meal2])

    # Get shopping list by category
    by_category = plan.get_shopping_list_by_category()

    print(f"Categories: {list(by_category.keys())}")

    for category, ingredients in by_category.items():
        print(f"\n{category.upper()}: ({len(ingredients)} items)")
        for ing in ingredients[:3]:  # Show first 3 per category
            print(f"  - {ing.quantity} {ing.unit or ''} {ing.name}")

    assert isinstance(by_category, dict), "Should return dictionary"
    assert len(by_category) > 0, "Should have at least one category"

    print("\n✅ PASSED\n")


def test_allergen_detection():
    """Test allergen detection across meal plan."""
    print("=" * 60)
    print("TEST 7: Allergen Detection")
    print("=" * 60)

    db = DatabaseInterface('data')
    recipe1 = db.get_recipe('71247')  # Cherry Streusel Cobbler
    recipe2 = db.get_recipe('76133')  # Reuben and Swiss Casserole Bake

    meal1 = PlannedMeal(date="2025-10-28", meal_type="dinner", recipe=recipe1, servings=4)
    meal2 = PlannedMeal(date="2025-10-29", meal_type="dinner", recipe=recipe2, servings=4)

    plan = MealPlan(week_of="2025-10-28", meals=[meal1, meal2])

    # Get all allergens
    allergens = plan.get_all_allergens()
    print(f"All allergens in plan: {allergens}")

    # Check specific allergens
    test_allergens = ["gluten", "dairy", "eggs", "peanuts"]
    for allergen in test_allergens:
        has_it = plan.has_allergen(allergen)
        print(f"  Contains {allergen}: {has_it}")

        if has_it:
            meals_with = plan.get_meals_with_allergen(allergen)
            print(f"    Found in {len(meals_with)} meals")

    assert isinstance(allergens, list), "Should return list"

    print("\n✅ PASSED\n")


def test_get_meals_by_date():
    """Test getting meals organized by date."""
    print("=" * 60)
    print("TEST 8: Get Meals by Date")
    print("=" * 60)

    db = DatabaseInterface('data')
    recipe = db.get_recipe('71247')

    meal1 = PlannedMeal(date="2025-10-28", meal_type="lunch", recipe=recipe, servings=2)
    meal2 = PlannedMeal(date="2025-10-28", meal_type="dinner", recipe=recipe, servings=4)
    meal3 = PlannedMeal(date="2025-10-29", meal_type="dinner", recipe=recipe, servings=4)

    plan = MealPlan(week_of="2025-10-28", meals=[meal1, meal2, meal3])

    # Get meals by date
    by_date = plan.get_meals_by_date()

    print(f"Dates with meals: {list(by_date.keys())}")

    for date, meals in by_date.items():
        print(f"\n{date}:")
        for meal in meals:
            print(f"  - {meal.meal_type}: {meal.recipe.name}")

    assert "2025-10-28" in by_date, "Should have Oct 28"
    assert "2025-10-29" in by_date, "Should have Oct 29"
    assert len(by_date["2025-10-28"]) == 2, "Oct 28 should have 2 meals"

    print("\n✅ PASSED\n")


def test_serialization():
    """Test serialization round-trip."""
    print("=" * 60)
    print("TEST 9: Serialization Round-Trip")
    print("=" * 60)

    db = DatabaseInterface('data')
    recipe1 = db.get_recipe('71247')  # Cherry Streusel Cobbler
    recipe2 = db.get_recipe('76133')  # Reuben and Swiss Casserole Bake

    meal1 = PlannedMeal(date="2025-10-28", meal_type="dinner", recipe=recipe1, servings=4)
    meal2 = PlannedMeal(date="2025-10-29", meal_type="dinner", recipe=recipe2, servings=6)

    plan = MealPlan(
        week_of="2025-10-28",
        meals=[meal1, meal2],
        preferences_applied=["quick-meals", "dairy-free"]
    )

    print(f"Original plan: {plan}")

    # Serialize
    data = plan.to_dict()
    print(f"\nSerialized to dict with {len(data)} keys")

    # Convert to JSON and back
    json_str = json.dumps(data)
    data_restored = json.loads(json_str)

    # Deserialize
    restored_plan = MealPlan.from_dict(data_restored)

    print(f"\nRestored plan: {restored_plan}")

    # Verify
    assert restored_plan.week_of == plan.week_of, "Week should match"
    assert len(restored_plan.meals) == len(plan.meals), "Meal count should match"
    assert restored_plan.preferences_applied == plan.preferences_applied, "Preferences should match"

    # Verify embedded recipes preserved
    for i, meal in enumerate(restored_plan.meals):
        assert meal.recipe.id == plan.meals[i].recipe.id, f"Recipe {i} ID should match"
        assert meal.recipe.name == plan.meals[i].recipe.name, f"Recipe {i} name should match"
        if plan.meals[i].recipe.has_structured_ingredients():
            assert meal.recipe.has_structured_ingredients(), f"Recipe {i} should have structured ingredients"

    print(f"\n✅ Serialization round-trip successful")
    print("\n✅ PASSED\n")


def test_display_methods():
    """Test display methods."""
    print("=" * 60)
    print("TEST 10: Display Methods")
    print("=" * 60)

    db = DatabaseInterface('data')
    recipe = db.get_recipe('71247')

    meal1 = PlannedMeal(date="2025-10-28", meal_type="dinner", recipe=recipe, servings=4)
    meal2 = PlannedMeal(date="2025-11-01", meal_type="dinner", recipe=recipe, servings=4)

    plan = MealPlan(week_of="2025-10-28", meals=[meal1, meal2])

    print(f"__str__: {plan}")
    print(f"get_summary(): {plan.get_summary()}")

    str_repr = str(plan)
    summary = plan.get_summary()

    assert "2025-10-28" in str_repr, "Should mention start date"
    assert "2025-11-01" in str_repr, "Should mention end date"
    assert "2" in str_repr, "Should mention meal count"

    assert str_repr == summary, "__str__ and get_summary should be the same"

    print("\n✅ PASSED\n")


def main():
    """Run all tests."""
    print("\n" + "=" * 60)
    print("MEAL PLAN IMPLEMENTATION TESTS")
    print("=" * 60 + "\n")

    try:
        test_create_meal_plan()
        test_get_meals_for_day()
        test_get_meals_by_type()
        test_get_date_range()
        test_get_all_ingredients()
        test_get_shopping_list_by_category()
        test_allergen_detection()
        test_get_meals_by_date()
        test_serialization()
        test_display_methods()

        print("=" * 60)
        print("ALL TESTS PASSED! ✅")
        print("=" * 60)
        print("\n✅ MealPlan successfully works with embedded recipes")
        print("✅ Shopping list generation, allergen detection, and filtering all work")
        print("✅ Serialization preserves full recipe data")

    except Exception as e:
        print(f"\n❌ TEST FAILED:")
        print(f"   {type(e).__name__}: {e}")
        import traceback
        traceback.print_exc()
        return 1

    return 0


if __name__ == "__main__":
    exit(main())
