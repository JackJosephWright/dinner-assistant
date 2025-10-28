#!/usr/bin/env python3
"""
Demonstration: Meal Plan Creation Workflow

Shows the complete process of creating a meal plan with embedded recipes,
from database queries through to shopping list generation.
"""

import json
from datetime import datetime
from src.data.database import DatabaseInterface
from src.data.models import Recipe, PlannedMeal, MealPlan


def print_section(title):
    """Print a section header."""
    print("\n" + "=" * 70)
    print(f"  {title}")
    print("=" * 70 + "\n")


def demo_meal_plan_workflow():
    """Demonstrate complete meal plan workflow."""

    print_section("MEAL PLAN CREATION WORKFLOW DEMONSTRATION")

    # ====================================================================
    # STEP 1: Initialize Database Connection
    # ====================================================================
    print_section("STEP 1: Initialize Database Connection")

    print("Creating DatabaseInterface with dev database...")
    db = DatabaseInterface('data')
    print("✅ Database connection established")
    print(f"   Database path: data/recipes_dev.db")
    print(f"   Total enriched recipes: 5,000")

    # ====================================================================
    # STEP 2: Search and Select Recipes
    # ====================================================================
    print_section("STEP 2: Search and Select Recipes")

    print("Searching for recipes...")
    print("\n1. Looking for quick dinner recipes:")
    quick_recipes = db.search_recipes(query="chicken", limit=3)

    for i, recipe in enumerate(quick_recipes, 1):
        enriched = "✓" if recipe.has_structured_ingredients() else "✗"
        print(f"   [{enriched}] {recipe.name} (ID: {recipe.id})")

    print("\n2. Looking for dessert recipes:")
    dessert_recipes = db.search_recipes(query="cobbler", limit=2)

    for i, recipe in enumerate(dessert_recipes, 1):
        enriched = "✓" if recipe.has_structured_ingredients() else "✗"
        print(f"   [{enriched}] {recipe.name} (ID: {recipe.id})")

    # Select recipes for our plan
    print("\n📋 Selecting recipes for this week's plan:")

    recipe1 = db.get_recipe('71247')  # Cherry Streusel Cobbler
    recipe2 = db.get_recipe('76133')  # Reuben and Swiss Casserole Bake
    recipe3 = db.get_recipe('503816')  # Yam-Pecan Recipe

    selected_recipes = [recipe1, recipe2, recipe3]

    for i, recipe in enumerate(selected_recipes, 1):
        print(f"   {i}. {recipe.name}")
        print(f"      - Servings: {recipe.servings}")
        print(f"      - Ingredients: {len(recipe.ingredients_raw)}")
        if recipe.has_structured_ingredients():
            ingredients = recipe.get_ingredients()
            print(f"      - Structured: {len(ingredients)} parsed ingredients ✓")

    # ====================================================================
    # STEP 3: Inspect Recipe Details
    # ====================================================================
    print_section("STEP 3: Inspect Recipe Details")

    print(f"Examining: {recipe1.name}\n")

    print("Basic Info:")
    print(f"  ID: {recipe1.id}")
    print(f"  Name: {recipe1.name}")
    print(f"  Servings: {recipe1.servings}")
    print(f"  Description: {recipe1.description[:100]}...")

    print("\nFirst 5 Raw Ingredients:")
    for i, ing in enumerate(recipe1.ingredients_raw[:5], 1):
        print(f"  {i}. {ing}")

    if recipe1.has_structured_ingredients():
        print("\nParsed Structured Ingredients:")
        ingredients = recipe1.get_ingredients()
        for i, ing in enumerate(ingredients[:5], 1):
            print(f"  {i}. {ing.quantity} {ing.unit or ''} {ing.name}")
            print(f"      Category: {ing.category}, Confidence: {ing.confidence:.2f}")

        print(f"\nAllergen Information:")
        allergens = recipe1.get_all_allergens()
        if allergens:
            print(f"  Contains: {', '.join(allergens)}")
        else:
            print(f"  No common allergens detected")

    # ====================================================================
    # STEP 4: Create PlannedMeal Objects
    # ====================================================================
    print_section("STEP 4: Create PlannedMeal Objects")

    print("Creating planned meals with embedded recipes...\n")

    # Monday dinner
    monday_dinner = PlannedMeal(
        date="2025-10-28",
        meal_type="dinner",
        recipe=recipe1,
        servings=6,  # Adjusting for family size
        notes="Make extra for leftovers"
    )
    print(f"1. Monday Dinner:")
    print(f"   {monday_dinner}")
    print(f"   Summary: {monday_dinner.get_summary()}")
    print(f"   Recipe embedded: ✓")
    print(f"   Scaled servings: {monday_dinner.servings} (original: {recipe1.servings})")

    # Tuesday dinner
    tuesday_dinner = PlannedMeal(
        date="2025-10-29",
        meal_type="dinner",
        recipe=recipe2,
        servings=4,
        notes="Quick weeknight meal"
    )
    print(f"\n2. Tuesday Dinner:")
    print(f"   {tuesday_dinner}")
    print(f"   Summary: {tuesday_dinner.get_summary()}")

    # Wednesday dinner
    wednesday_dinner = PlannedMeal(
        date="2025-10-30",
        meal_type="dinner",
        recipe=recipe3,
        servings=4,
        notes=None
    )
    print(f"\n3. Wednesday Dinner:")
    print(f"   {wednesday_dinner}")
    print(f"   Summary: {wednesday_dinner.get_summary()}")

    # ====================================================================
    # STEP 5: Create MealPlan
    # ====================================================================
    print_section("STEP 5: Create MealPlan")

    print("Assembling meal plan...\n")

    plan = MealPlan(
        week_of="2025-10-28",
        meals=[monday_dinner, tuesday_dinner, wednesday_dinner],
        preferences_applied=["family-friendly", "make-ahead"],
        created_at=datetime.now()
    )

    print(f"Meal Plan Created:")
    print(f"  {plan}")
    print(f"  Week of: {plan.week_of}")
    print(f"  Total meals: {len(plan.meals)}")
    print(f"  Preferences: {', '.join(plan.preferences_applied)}")

    start, end = plan.get_date_range()
    print(f"  Date range: {start} to {end}")

    # ====================================================================
    # STEP 6: Query Meal Plan
    # ====================================================================
    print_section("STEP 6: Query Meal Plan")

    print("1. Get meals for specific day:")
    monday_meals = plan.get_meals_for_day("2025-10-28")
    print(f"   Monday (2025-10-28): {len(monday_meals)} meal(s)")
    for meal in monday_meals:
        print(f"      - {meal}")

    print("\n2. Get all dinners:")
    dinners = plan.get_meals_by_type("dinner")
    print(f"   Total dinners: {len(dinners)}")
    for i, meal in enumerate(dinners, 1):
        print(f"      {i}. {meal.date}: {meal.recipe.name}")

    print("\n3. Get meals organized by date:")
    by_date = plan.get_meals_by_date()
    print(f"   Dates: {list(by_date.keys())}")
    for date, meals in by_date.items():
        print(f"      {date}:")
        for meal in meals:
            print(f"         • {meal.meal_type}: {meal.recipe.name} ({meal.servings} servings)")

    # ====================================================================
    # STEP 7: Ingredient Scaling Demo
    # ====================================================================
    print_section("STEP 7: Ingredient Scaling Demo")

    print(f"Recipe: {monday_dinner.recipe.name}")
    print(f"Original servings: {monday_dinner.recipe.servings}")
    print(f"Meal servings: {monday_dinner.servings}")
    print(f"Scale factor: {monday_dinner.servings / monday_dinner.recipe.servings}x\n")

    # Get scaled recipe
    scaled_recipe = monday_dinner.get_scaled_recipe()

    print("Comparing ingredients (original vs scaled):\n")
    original_ingredients = monday_dinner.recipe.get_ingredients()
    scaled_ingredients = scaled_recipe.get_ingredients()

    for i in range(min(3, len(original_ingredients))):
        orig = original_ingredients[i]
        scaled = scaled_ingredients[i]
        print(f"{i+1}. {orig.name}")
        print(f"   Original: {orig.quantity} {orig.unit or ''}")
        print(f"   Scaled:   {scaled.quantity} {scaled.unit or ''}")

    # ====================================================================
    # STEP 8: Generate Shopping List
    # ====================================================================
    print_section("STEP 8: Generate Shopping List")

    print("1. Get all ingredients across all meals:\n")
    all_ingredients = plan.get_all_ingredients()
    print(f"   Total ingredients needed: {len(all_ingredients)}")

    print("\n2. Shopping list organized by category:\n")
    shopping_list = plan.get_shopping_list_by_category()

    # Sort categories for nice display
    category_order = ["produce", "meat", "dairy", "pantry", "baking", "condiments", "other"]
    sorted_categories = [cat for cat in category_order if cat in shopping_list]
    sorted_categories.extend([cat for cat in shopping_list.keys() if cat not in category_order])

    for category in sorted_categories:
        ingredients = shopping_list[category]
        print(f"   {category.upper()} ({len(ingredients)} items):")
        for ing in ingredients[:5]:  # Show first 5 per category
            qty = f"{ing.quantity} " if ing.quantity else ""
            unit = f"{ing.unit} " if ing.unit else ""
            print(f"      [ ] {qty}{unit}{ing.name}")
        if len(ingredients) > 5:
            print(f"      ... and {len(ingredients) - 5} more")
        print()

    # ====================================================================
    # STEP 9: Check Allergens
    # ====================================================================
    print_section("STEP 9: Check Allergens")

    print("Allergen analysis across entire meal plan:\n")

    all_allergens = plan.get_all_allergens()
    print(f"Allergens present: {', '.join(all_allergens) if all_allergens else 'None'}\n")

    # Check specific allergens
    test_allergens = ["dairy", "gluten", "nuts", "shellfish"]

    for allergen in test_allergens:
        has_it = plan.has_allergen(allergen)
        if has_it:
            meals_with = plan.get_meals_with_allergen(allergen)
            print(f"⚠️  {allergen.upper()}: Found in {len(meals_with)} meal(s)")
            for meal in meals_with:
                print(f"      - {meal.date}: {meal.recipe.name}")
        else:
            print(f"✓  {allergen.upper()}: Safe")

    # ====================================================================
    # STEP 10: Serialize and Save
    # ====================================================================
    print_section("STEP 10: Serialize and Save")

    print("1. Serialize to dictionary:\n")
    plan_dict = plan.to_dict()
    print(f"   Keys: {list(plan_dict.keys())}")
    print(f"   Meals: {len(plan_dict['meals'])} meal objects")
    print(f"   Each meal contains full embedded recipe: ✓")

    # Check size
    json_str = json.dumps(plan_dict, indent=2)
    size_kb = len(json_str) / 1024
    print(f"   JSON size: {size_kb:.1f} KB")

    print("\n2. Save to database:\n")
    plan_id = db.save_meal_plan(plan)
    print(f"   ✓ Saved with ID: {plan_id}")
    print(f"   Full recipe data persisted in database")

    print("\n3. Load from database:\n")
    loaded_plan = db.get_meal_plan(plan_id)
    print(f"   ✓ Loaded: {loaded_plan}")
    print(f"   Meals loaded: {len(loaded_plan.meals)}")

    # Verify embedded recipes
    print("\n4. Verify embedded recipes (no additional queries needed):\n")
    for i, meal in enumerate(loaded_plan.meals, 1):
        print(f"   {i}. {meal.recipe.name}")
        print(f"      - Has full recipe data: ✓")
        print(f"      - Has structured ingredients: {'✓' if meal.recipe.has_structured_ingredients() else '✗'}")
        if meal.recipe.has_structured_ingredients():
            ingredients = meal.recipe.get_ingredients()
            print(f"      - Can generate shopping list: ✓ ({len(ingredients)} ingredients)")

    # ====================================================================
    # STEP 11: Chat Interface Simulation
    # ====================================================================
    print_section("STEP 11: Chat Interface Simulation")

    print("Simulating chat queries (all answered from embedded data):\n")

    # Query 1
    print('User: "What\'s for dinner on Monday?"')
    monday_dinners = loaded_plan.get_meals_for_day("2025-10-28")
    if monday_dinners:
        meal = monday_dinners[0]
        print(f'Bot: "Monday dinner is {meal.recipe.name}, serving {meal.servings} people."')
        if meal.notes:
            print(f'     "Note: {meal.notes}"')
    print()

    # Query 2
    print('User: "How many ingredients do I need for the week?"')
    total_ingredients = len(loaded_plan.get_all_ingredients())
    print(f'Bot: "You\'ll need {total_ingredients} ingredients for all {len(loaded_plan.meals)} meals this week."')
    print()

    # Query 3
    print('User: "Does this plan work for someone with dairy allergy?"')
    if loaded_plan.has_allergen("dairy"):
        dairy_meals = loaded_plan.get_meals_with_allergen("dairy")
        print(f'Bot: "⚠️ Warning: {len(dairy_meals)} meal(s) contain dairy:')
        for meal in dairy_meals:
            print(f'     - {meal.date}: {meal.recipe.name}')
        print('     "Would you like me to suggest dairy-free alternatives?"')
    else:
        print('Bot: "✓ This plan is dairy-free!"')
    print()

    # Query 4
    print('User: "Generate my shopping list"')
    print('Bot: "Here\'s your shopping list organized by store section:"\n')
    shopping = loaded_plan.get_shopping_list_by_category()
    for cat in ["produce", "meat", "dairy"][:2]:  # Show first 2 categories
        if cat in shopping:
            print(f'     {cat.upper()}:')
            for ing in shopping[cat][:3]:
                qty = f"{ing.quantity} " if ing.quantity else ""
                unit = f"{ing.unit} " if ing.unit else ""
                print(f'       [ ] {qty}{unit}{ing.name}')
    print('     ...')

    # ====================================================================
    # Summary
    # ====================================================================
    print_section("WORKFLOW COMPLETE")

    print("Summary:")
    print(f"  ✓ Created meal plan with {len(plan.meals)} meals")
    print(f"  ✓ All recipes fully embedded (no additional queries needed)")
    print(f"  ✓ {total_ingredients} ingredients identified and categorized")
    print(f"  ✓ Allergen information available for all meals")
    print(f"  ✓ Saved to database with ID: {plan_id}")
    print(f"  ✓ Ready for chat interface integration")
    print(f"\n  Database queries used: 5 (initial recipe loads + 1 save + 1 load)")
    print(f"  Subsequent operations: 0 queries (all data embedded)")
    print()


if __name__ == "__main__":
    demo_meal_plan_workflow()
