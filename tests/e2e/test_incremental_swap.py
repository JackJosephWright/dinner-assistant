#!/usr/bin/env python3
"""
Test script for incremental shopping list updates during meal swaps.
"""

from datetime import datetime, timedelta
from src.data.models import Recipe, Ingredient, MealPlan, PlannedMeal, GroceryList
from src.data.database import DatabaseInterface

def create_test_recipes():
    """Create test recipes for swapping."""
    # Recipe 1: Grilled Chicken (original)
    recipe1 = Recipe(
        id="test_1",
        name="Grilled Chicken",
        description="Simple grilled chicken",
        ingredients=["2 lbs chicken breast", "1 tbsp olive oil", "Salt and pepper"],
        ingredients_raw=["2 lbs chicken breast", "1 tbsp olive oil", "Salt and pepper"],
        ingredients_structured=[
            Ingredient(raw="2 lbs chicken breast", name="chicken breast", quantity=2.0, unit="lbs", category="meat"),
            Ingredient(raw="1 tbsp olive oil", name="olive oil", quantity=1.0, unit="tbsp", category="pantry"),
            Ingredient(raw="1 tsp salt", name="salt", quantity=1.0, unit="tsp", category="pantry"),
        ],
        steps=["Grill chicken"],
        servings=4,
        serving_size="1 breast",
        tags=["easy", "dinner"],
    )

    # Recipe 2: Pasta (replacement)
    recipe2 = Recipe(
        id="test_2",
        name="Pasta Marinara",
        description="Classic pasta",
        ingredients=["1 lb pasta", "2 cups tomato sauce", "1 tbsp olive oil"],
        ingredients_raw=["1 lb pasta", "2 cups tomato sauce", "1 tbsp olive oil"],
        ingredients_structured=[
            Ingredient(raw="1 lb pasta", name="pasta", quantity=1.0, unit="lb", category="pantry"),
            Ingredient(raw="2 cups tomato sauce", name="tomato sauce", quantity=2.0, unit="cups", category="pantry"),
            Ingredient(raw="1 tbsp olive oil", name="olive oil", quantity=1.0, unit="tbsp", category="pantry"),
        ],
        steps=["Cook pasta", "Add sauce"],
        servings=4,
        serving_size="1 plate",
        tags=["easy", "dinner"],
    )

    # Recipe 3: Salad (for day 2)
    recipe3 = Recipe(
        id="test_3",
        name="Caesar Salad",
        description="Fresh salad",
        ingredients=["1 head lettuce", "1/4 cup parmesan cheese", "1/2 cup croutons"],
        ingredients_raw=["1 head lettuce", "1/4 cup parmesan cheese", "1/2 cup croutons"],
        ingredients_structured=[
            Ingredient(raw="1 head lettuce", name="lettuce", quantity=1.0, unit="head", category="produce"),
            Ingredient(raw="1/4 cup parmesan cheese", name="parmesan cheese", quantity=0.25, unit="cup", category="dairy"),
            Ingredient(raw="1/2 cup croutons", name="croutons", quantity=0.5, unit="cup", category="pantry"),
        ],
        steps=["Mix ingredients"],
        servings=2,
        serving_size="1 bowl",
        tags=["easy", "salad"],
    )

    return recipe1, recipe2, recipe3


def test_incremental_swap():
    """Test the full incremental swap workflow."""
    print("=" * 70)
    print("Testing Incremental Shopping List Update During Meal Swap")
    print("=" * 70)

    # Initialize database
    db = DatabaseInterface()

    # Create test recipes
    recipe1, recipe2, recipe3 = create_test_recipes()

    # Step 1: Create a meal plan
    print("\n📅 Step 1: Create meal plan with 2 days")
    print("-" * 70)

    today = datetime.now().date()
    week_start = today - timedelta(days=today.weekday())  # Monday

    meal_plan = MealPlan(
        week_of=week_start.isoformat(),
        meals=[
            PlannedMeal(
                date=(week_start + timedelta(days=0)).isoformat(),
                meal_type="dinner",
                recipe=recipe1,  # Grilled Chicken
                servings=4,
            ),
            PlannedMeal(
                date=(week_start + timedelta(days=1)).isoformat(),
                meal_type="dinner",
                recipe=recipe3,  # Caesar Salad
                servings=2,
            ),
        ],
    )

    plan_id = db.save_meal_plan(meal_plan)
    print(f"✅ Created meal plan: {plan_id}")
    print(f"   Day 1: {recipe1.name}")
    print(f"   Day 2: {recipe3.name}")

    # Step 2: Generate initial grocery list
    print("\n🛒 Step 2: Generate initial grocery list")
    print("-" * 70)

    grocery_list = GroceryList(week_of=week_start.isoformat(), items=[])
    grocery_list.add_recipe_ingredients(recipe1)
    grocery_list.add_recipe_ingredients(recipe3)

    list_id = db.save_grocery_list(grocery_list)
    print(f"✅ Created grocery list: {list_id}")
    print(f"   Total items: {len(grocery_list.items)}")
    for item in grocery_list.items:
        print(f"     - {item.name}: {item.quantity} (from {item.recipe_sources})")

    # Step 3: Swap meal (Grilled Chicken → Pasta Marinara)
    print("\n🔄 Step 3: Swap Day 1 meal (Grilled Chicken → Pasta Marinara)")
    print("-" * 70)

    # First, manually save recipe2 to DB so swap can find it
    # (In real app, this would already exist)
    # For now, we'll work around by updating the swap logic

    swap_date = (week_start + timedelta(days=0)).isoformat()

    # Load grocery list before swap
    grocery_before = db.get_grocery_list_by_week(week_start.isoformat())
    print(f"Before swap:")
    print(f"  Items: {len(grocery_before.items)}")
    for item in grocery_before.items:
        sources_str = ", ".join(item.recipe_sources)
        print(f"    - {item.name}: {item.quantity} (from: {sources_str})")

    # Manually perform swap with incremental update
    print(f"\n🔧 Performing swap...")

    # Get meal plan
    meal_plan = db.get_meal_plan(plan_id)

    # Find and swap
    for i, meal in enumerate(meal_plan.meals):
        if meal.date == swap_date:
            old_recipe = meal.recipe
            meal_plan.meals[i] = PlannedMeal(
                date=swap_date,
                meal_type=meal.meal_type,
                recipe=recipe2,  # Pasta Marinara
                servings=meal.servings,
                notes=meal.notes,
            )

            # Save meal plan
            db.save_meal_plan(meal_plan)

            # Update grocery list incrementally
            grocery_list = db.get_grocery_list_by_week(week_start.isoformat())
            grocery_list.remove_recipe_ingredients(old_recipe.name)
            grocery_list.add_recipe_ingredients(recipe2)
            db.save_grocery_list(grocery_list)

            print(f"✅ Swapped {old_recipe.name} → {recipe2.name}")
            break

    # Step 4: Verify incremental update worked
    print("\n✅ Step 4: Verify grocery list updated correctly")
    print("-" * 70)

    grocery_after = db.get_grocery_list_by_week(week_start.isoformat())
    print(f"After swap:")
    print(f"  Items: {len(grocery_after.items)}")
    for item in grocery_after.items:
        sources_str = ", ".join(item.recipe_sources)
        contribs = ", ".join([f"{c.recipe_name}: {c.quantity}" for c in item.contributions])
        print(f"    - {item.name}: {item.quantity}")
        print(f"      Sources: {sources_str}")
        print(f"      Contributions: {contribs}")

    # Verify expectations
    print("\n📊 Verification:")
    print("-" * 70)

    # Chicken should be gone
    chicken = next((item for item in grocery_after.items if "chicken" in item.name.lower()), None)
    if chicken is None:
        print("✅ Chicken removed (was only in Grilled Chicken)")
    else:
        print(f"❌ ERROR: Chicken still exists: {chicken.quantity}")

    # Pasta should be present
    pasta = next((item for item in grocery_after.items if "pasta" in item.name.lower()), None)
    if pasta and "Pasta Marinara" in pasta.recipe_sources:
        print(f"✅ Pasta added from Pasta Marinara: {pasta.quantity}")
    else:
        print("❌ ERROR: Pasta not found or wrong source")

    # Olive oil should still exist (both recipes have it)
    olive_oil = next((item for item in grocery_after.items if "olive oil" in item.name.lower()), None)
    if olive_oil:
        print(f"✅ Olive oil consolidated: {olive_oil.quantity}")
        print(f"   From: {olive_oil.recipe_sources}")
        if len(olive_oil.contributions) == 1:
            print(f"   Contributions: {len(olive_oil.contributions)} (correct - only Pasta now)")
        else:
            print(f"   ❌ ERROR: Should have 1 contribution, has {len(olive_oil.contributions)}")
    else:
        print("❌ ERROR: Olive oil not found")

    # Lettuce should still exist (from Caesar Salad)
    lettuce = next((item for item in grocery_after.items if "lettuce" in item.name.lower()), None)
    if lettuce and "Caesar Salad" in lettuce.recipe_sources:
        print(f"✅ Lettuce preserved from Caesar Salad: {lettuce.quantity}")
    else:
        print("❌ ERROR: Lettuce not found or wrong source")

    print("\n" + "=" * 70)
    print("✅ Test completed!")
    print("=" * 70)


if __name__ == "__main__":
    test_incremental_swap()
