#!/usr/bin/env python3
"""
Test script for enhanced Recipe implementation.

Tests the new Ingredient and Recipe features with enriched data from database.
"""

import sqlite3
import json
from src.data.models import Recipe, Ingredient, NutritionInfo


def load_enriched_recipe(recipe_id: str) -> Recipe:
    """Load an enriched recipe from database."""
    conn = sqlite3.connect('data/recipes_dev.db')  # Use dev database
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    cursor.execute("""
        SELECT id, name, description, ingredients, ingredients_raw,
               ingredients_structured, steps, servings, serving_size, tags
        FROM recipes
        WHERE id = ?
    """, (recipe_id,))

    row = cursor.fetchone()
    conn.close()

    if not row:
        raise ValueError(f"Recipe {recipe_id} not found")

    # Parse ingredients_structured JSON
    ingredients_structured = None
    if row['ingredients_structured']:
        ing_data = json.loads(row['ingredients_structured'])
        ingredients_structured = [Ingredient(**ing) for ing in ing_data]

    return Recipe(
        id=row['id'],
        name=row['name'],
        description=row['description'],
        ingredients=json.loads(row['ingredients']),
        ingredients_raw=json.loads(row['ingredients_raw']),
        ingredients_structured=ingredients_structured,
        steps=json.loads(row['steps']),
        servings=row['servings'],
        serving_size=row['serving_size'],
        tags=json.loads(row['tags']),
    )


def test_has_structured_ingredients():
    """Test checking for enriched data."""
    print("=" * 60)
    print("TEST 1: has_structured_ingredients()")
    print("=" * 60)

    # First enriched recipe (Cherry Streusel Cobbler)
    recipe = load_enriched_recipe('71247')

    print(f"Recipe: {recipe.name}")
    print(f"Has structured ingredients: {recipe.has_structured_ingredients()}")
    assert recipe.has_structured_ingredients(), "Should have structured ingredients"
    print("✅ PASSED\n")


def test_get_ingredients():
    """Test getting structured ingredients."""
    print("=" * 60)
    print("TEST 2: get_ingredients()")
    print("=" * 60)

    recipe = load_enriched_recipe('71247')

    print(f"Recipe: {recipe.name}")
    print(f"Number of ingredients: {len(recipe.ingredients_raw)}")

    ingredients = recipe.get_ingredients()

    print(f"\nFirst 3 ingredients:")
    for i, ing in enumerate(ingredients[:3], 1):
        print(f"  {i}. {ing}")
        print(f"     Quantity: {ing.quantity}, Unit: {ing.unit}, Name: {ing.name}")
        print(f"     Category: {ing.category}, Confidence: {ing.confidence}")

    assert len(ingredients) > 0, "Should have ingredients"
    assert all(isinstance(ing, Ingredient) for ing in ingredients), "All should be Ingredient objects"
    print("\n✅ PASSED\n")


def test_allergen_detection():
    """Test allergen detection."""
    print("=" * 60)
    print("TEST 3: Allergen Detection")
    print("=" * 60)

    recipe = load_enriched_recipe('71247')

    print(f"Recipe: {recipe.name}")

    all_allergens = recipe.get_all_allergens()
    print(f"All allergens: {all_allergens}")

    # Test specific allergen checks
    test_allergens = ["gluten", "dairy", "eggs", "peanuts"]
    for allergen in test_allergens:
        has_it = recipe.has_allergen(allergen)
        print(f"  Contains {allergen}: {has_it}")

    print("\n✅ PASSED\n")


def test_recipe_scaling():
    """Test recipe scaling."""
    print("=" * 60)
    print("TEST 4: Recipe Scaling")
    print("=" * 60)

    recipe = load_enriched_recipe('71247')

    print(f"Original Recipe: {recipe.name}")
    print(f"Original servings: {recipe.servings}")

    # Get first ingredient
    orig_ingredients = recipe.get_ingredients()
    first_ing = orig_ingredients[0]
    print(f"Original first ingredient: {first_ing}")

    # Scale to double
    scaled_recipe = recipe.scale_ingredients(target_servings=recipe.servings * 2)

    print(f"\nScaled Recipe: {scaled_recipe.name}")
    print(f"Scaled servings: {scaled_recipe.servings}")

    scaled_ingredients = scaled_recipe.get_ingredients()
    scaled_first_ing = scaled_ingredients[0]
    print(f"Scaled first ingredient: {scaled_first_ing}")

    # Verify scaling
    if first_ing.quantity and scaled_first_ing.quantity:
        assert scaled_first_ing.quantity == first_ing.quantity * 2, "Quantity should be doubled"
        print(f"\n✅ Quantity correctly scaled: {first_ing.quantity} → {scaled_first_ing.quantity}")

    # Verify original unchanged
    assert recipe.servings != scaled_recipe.servings, "Original should be unchanged"
    print(f"✅ Original recipe unchanged: {recipe.servings} servings")

    print("\n✅ PASSED\n")


def test_serialization():
    """Test to_dict and from_dict."""
    print("=" * 60)
    print("TEST 5: Serialization")
    print("=" * 60)

    recipe = load_enriched_recipe('71247')

    print(f"Original Recipe: {recipe.name}")
    print(f"Has structured ingredients: {recipe.has_structured_ingredients()}")

    # Serialize
    data = recipe.to_dict()
    print(f"\nSerialized to dict with {len(data)} keys")
    print(f"Has 'ingredients_structured' key: {'ingredients_structured' in data}")

    # Deserialize
    restored_recipe = Recipe.from_dict(data)

    print(f"\nRestored Recipe: {restored_recipe.name}")
    print(f"Has structured ingredients: {restored_recipe.has_structured_ingredients()}")

    # Verify
    assert restored_recipe.id == recipe.id, "ID should match"
    assert restored_recipe.name == recipe.name, "Name should match"
    assert restored_recipe.has_structured_ingredients() == recipe.has_structured_ingredients(), "Structured ingredients should match"

    if recipe.has_structured_ingredients():
        assert len(restored_recipe.ingredients_structured) == len(recipe.ingredients_structured), "Ingredient count should match"

    print(f"\n✅ Serialization round-trip successful")
    print("\n✅ PASSED\n")


def test_ingredient_scaling():
    """Test individual ingredient scaling."""
    print("=" * 60)
    print("TEST 6: Ingredient Scaling")
    print("=" * 60)

    # Create test ingredient
    ing = Ingredient(
        raw="2 cups flour",
        quantity=2.0,
        unit="cup",
        name="flour",
        category="baking",
        allergens=["gluten"]
    )

    print(f"Original: {ing}")
    print(f"  Quantity: {ing.quantity} {ing.unit}")

    # Scale by 1.5
    scaled = ing.scale(1.5)

    print(f"\nScaled (1.5x): {scaled}")
    print(f"  Quantity: {scaled.quantity} {scaled.unit}")

    assert scaled.quantity == 3.0, "Should be 3.0"
    assert scaled.unit == "cup", "Unit should be preserved"
    assert scaled.name == "flour", "Name should be preserved"
    assert ing.quantity == 2.0, "Original should be unchanged"

    print("\n✅ PASSED\n")


def test_non_enriched_recipe():
    """Test behavior with non-enriched recipe."""
    print("=" * 60)
    print("TEST 7: Non-Enriched Recipe Handling")
    print("=" * 60)

    # Create a mock non-enriched recipe for testing
    print(f"Testing with mock non-enriched recipe")

    recipe = Recipe(
        id="test_non_enriched",
        name="Test Non-Enriched Recipe",
        description="Test recipe without structured ingredients",
        ingredients=["flour", "sugar", "eggs"],
        ingredients_raw=["2 cups flour", "1 cup sugar", "3 eggs"],
        steps=["Mix", "Bake"],
        servings=4,
        serving_size="1 serving",
        tags=["dessert"],
        ingredients_structured=None,  # Not enriched
        nutrition=None
    )

    print(f"Has structured ingredients: {recipe.has_structured_ingredients()}")
    assert not recipe.has_structured_ingredients(), "Should not have structured ingredients"

    # Try to get ingredients - should raise ValueError
    try:
        ingredients = recipe.get_ingredients()
        print("❌ FAILED - Should have raised ValueError")
    except ValueError as e:
        print(f"✅ Correctly raised ValueError: {str(e)[:100]}...")

    # Try to check allergens - should raise ValueError
    try:
        has_gluten = recipe.has_allergen("gluten")
        print("❌ FAILED - Should have raised ValueError")
    except ValueError as e:
        print(f"✅ Correctly raised ValueError for allergen check")

    # Try to scale - should raise ValueError
    try:
        scaled = recipe.scale_ingredients(8)
        print("❌ FAILED - Should have raised ValueError")
    except ValueError as e:
        print(f"✅ Correctly raised ValueError for scaling")

    print("\n✅ PASSED\n")


def main():
    """Run all tests."""
    print("\n" + "=" * 60)
    print("ENHANCED RECIPE IMPLEMENTATION TESTS")
    print("=" * 60 + "\n")

    try:
        test_has_structured_ingredients()
        test_get_ingredients()
        test_allergen_detection()
        test_recipe_scaling()
        test_serialization()
        test_ingredient_scaling()
        test_non_enriched_recipe()

        print("=" * 60)
        print("ALL TESTS PASSED! ✅")
        print("=" * 60)

    except Exception as e:
        print(f"\n❌ TEST FAILED:")
        print(f"   {type(e).__name__}: {e}")
        import traceback
        traceback.print_exc()
        return 1

    return 0


if __name__ == "__main__":
    exit(main())
