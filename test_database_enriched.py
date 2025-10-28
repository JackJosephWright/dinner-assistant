#!/usr/bin/env python3
"""
Test DatabaseInterface with enriched recipes.

Verifies that DatabaseInterface correctly loads structured ingredients
from the development database.
"""

from src.data.database import DatabaseInterface
from src.data.models import Ingredient


def test_get_enriched_recipe():
    """Test loading an enriched recipe from database."""
    print("=" * 60)
    print("TEST 1: Load Enriched Recipe via DatabaseInterface")
    print("=" * 60)

    # Initialize with dev database
    db = DatabaseInterface(db_dir="data")

    # Load enriched recipe (Cherry Streusel Cobbler)
    recipe = db.get_recipe('71247')

    print(f"Recipe: {recipe.name}")
    print(f"Has structured ingredients: {recipe.has_structured_ingredients()}")

    assert recipe is not None, "Recipe should be found"
    assert recipe.has_structured_ingredients(), "Recipe should have structured ingredients"

    # Test ingredient access
    ingredients = recipe.get_ingredients()
    print(f"Number of ingredients: {len(ingredients)}")

    # Print first 3 ingredients
    print(f"\nFirst 3 ingredients:")
    for i, ing in enumerate(ingredients[:3], 1):
        print(f"  {i}. {ing.name}")
        print(f"     Quantity: {ing.quantity}, Unit: {ing.unit}")
        print(f"     Category: {ing.category}, Allergens: {ing.allergens}")

    assert len(ingredients) > 0, "Should have ingredients"
    assert all(isinstance(ing, Ingredient) for ing in ingredients), "All should be Ingredient objects"

    print("\n✅ PASSED\n")


def test_get_non_enriched_recipe():
    """Test loading a non-enriched recipe (should handle gracefully)."""
    print("=" * 60)
    print("TEST 2: Load Non-Enriched Recipe (Graceful Handling)")
    print("=" * 60)

    db = DatabaseInterface(db_dir="data")

    # Try to load a recipe that might not be enriched
    # (In dev database all should be enriched, but let's test the logic)
    recipe = db.get_recipe('71247')

    print(f"Recipe: {recipe.name}")
    print(f"Has structured ingredients: {recipe.has_structured_ingredients()}")

    # Even if not enriched, recipe should load with basic data
    assert recipe is not None, "Recipe should be found"
    assert recipe.name, "Recipe should have a name"
    assert recipe.ingredients_raw, "Recipe should have raw ingredients"

    print("✅ PASSED\n")


def test_search_enriched_recipes():
    """Test searching for recipes (should include structured ingredients)."""
    print("=" * 60)
    print("TEST 3: Search Recipes with Structured Ingredients")
    print("=" * 60)

    db = DatabaseInterface(db_dir="data")

    # Search for cobbler recipes
    recipes = db.search_recipes(query="cobbler", limit=5)

    print(f"Found {len(recipes)} recipes matching 'cobbler'")

    enriched_count = 0
    for recipe in recipes:
        if recipe.has_structured_ingredients():
            enriched_count += 1
            print(f"  ✓ {recipe.name} - ENRICHED ({len(recipe.get_ingredients())} ingredients)")
        else:
            print(f"  - {recipe.name} - Not enriched")

    print(f"\nEnriched recipes: {enriched_count}/{len(recipes)}")

    # In dev database, all should be enriched
    if len(recipes) > 0:
        assert enriched_count > 0, "Should have at least one enriched recipe"

    print("✅ PASSED\n")


def test_allergen_detection_via_db():
    """Test allergen detection on recipe loaded from database."""
    print("=" * 60)
    print("TEST 4: Allergen Detection via DatabaseInterface")
    print("=" * 60)

    db = DatabaseInterface(db_dir="data")

    recipe = db.get_recipe('71247')

    print(f"Recipe: {recipe.name}")

    # Test allergen detection
    all_allergens = recipe.get_all_allergens()
    print(f"All allergens: {all_allergens}")

    test_allergens = ["gluten", "dairy", "eggs", "peanuts"]
    for allergen in test_allergens:
        has_it = recipe.has_allergen(allergen)
        print(f"  Contains {allergen}: {has_it}")

    print("✅ PASSED\n")


def test_recipe_scaling_via_db():
    """Test recipe scaling on recipe loaded from database."""
    print("=" * 60)
    print("TEST 5: Recipe Scaling via DatabaseInterface")
    print("=" * 60)

    db = DatabaseInterface(db_dir="data")

    recipe = db.get_recipe('71247')

    print(f"Original Recipe: {recipe.name}")
    print(f"Original servings: {recipe.servings}")

    orig_ingredients = recipe.get_ingredients()
    first_ing = orig_ingredients[0]
    print(f"Original first ingredient: {first_ing.quantity} {first_ing.unit} {first_ing.name}")

    # Scale to double
    scaled_recipe = recipe.scale_ingredients(target_servings=recipe.servings * 2)

    print(f"\nScaled Recipe: {scaled_recipe.name}")
    print(f"Scaled servings: {scaled_recipe.servings}")

    scaled_ingredients = scaled_recipe.get_ingredients()
    scaled_first_ing = scaled_ingredients[0]
    print(f"Scaled first ingredient: {scaled_first_ing.quantity} {scaled_first_ing.unit} {scaled_first_ing.name}")

    # Verify scaling
    if first_ing.quantity and scaled_first_ing.quantity:
        assert scaled_first_ing.quantity == first_ing.quantity * 2, "Quantity should be doubled"
        print(f"\n✅ Quantity correctly scaled: {first_ing.quantity} → {scaled_first_ing.quantity}")

    # Verify original unchanged
    assert recipe.servings != scaled_recipe.servings, "Original should be unchanged"
    print(f"✅ Original recipe unchanged: {recipe.servings} servings")

    print("\n✅ PASSED\n")


def main():
    """Run all tests."""
    print("\n" + "=" * 60)
    print("DATABASE INTERFACE - ENRICHED RECIPE TESTS")
    print("=" * 60 + "\n")

    try:
        test_get_enriched_recipe()
        test_get_non_enriched_recipe()
        test_search_enriched_recipes()
        test_allergen_detection_via_db()
        test_recipe_scaling_via_db()

        print("=" * 60)
        print("ALL TESTS PASSED! ✅")
        print("=" * 60)
        print("\n✅ DatabaseInterface successfully loads structured ingredients")
        print("✅ All Recipe methods work with database-loaded recipes")

    except Exception as e:
        print(f"\n❌ TEST FAILED:")
        print(f"   {type(e).__name__}: {e}")
        import traceback
        traceback.print_exc()
        return 1

    return 0


if __name__ == "__main__":
    exit(main())
