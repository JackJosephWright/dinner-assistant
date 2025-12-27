#!/usr/bin/env python3
"""
Test script for enhanced PlannedMeal implementation.

Tests the new PlannedMeal with embedded Recipe objects.
"""

import json
from datetime import datetime
from src.data.models import Recipe, PlannedMeal, Ingredient
from src.data.database import DatabaseInterface


def test_create_planned_meal():
    """Test creating a PlannedMeal with embedded Recipe."""
    print("=" * 60)
    print("TEST 1: Create PlannedMeal with Embedded Recipe")
    print("=" * 60)

    # Load recipe from database
    db = DatabaseInterface('data')
    recipe = db.get_recipe('71247')

    print(f"Loaded recipe: {recipe.name}")

    # Create planned meal
    meal = PlannedMeal(
        date="2025-10-29",
        meal_type="dinner",
        recipe=recipe,
        servings=6,
        notes="Make extra for leftovers"
    )

    print(f"\nPlannedMeal created: {meal}")
    print(f"Summary: {meal.get_summary()}")

    assert meal.recipe.name == recipe.name, "Recipe should be embedded"
    assert meal.servings == 6, "Servings should be set"
    assert meal.date == "2025-10-29", "Date should be set"

    print("\n✅ PASSED\n")


def test_get_scaled_recipe():
    """Test getting scaled recipe from PlannedMeal."""
    print("=" * 60)
    print("TEST 2: Get Scaled Recipe")
    print("=" * 60)

    db = DatabaseInterface('data')
    recipe = db.get_recipe('71247')

    print(f"Original recipe: {recipe.name}")
    print(f"Original servings: {recipe.servings}")

    # Create meal with different servings
    meal = PlannedMeal(
        date="2025-10-29",
        meal_type="dinner",
        recipe=recipe,
        servings=8  # Double the servings
    )

    # Get scaled recipe
    scaled_recipe = meal.get_scaled_recipe()

    print(f"\nScaled recipe servings: {scaled_recipe.servings}")

    assert scaled_recipe.servings == 8, "Scaled recipe should have 8 servings"
    assert recipe.servings == 4, "Original recipe should be unchanged"

    # Test when servings match
    meal_same = PlannedMeal(
        date="2025-10-29",
        meal_type="dinner",
        recipe=recipe,
        servings=4  # Same as recipe
    )

    scaled_same = meal_same.get_scaled_recipe()
    assert scaled_same is recipe, "Should return same recipe when servings match"

    print("✅ Scaling works correctly")
    print("\n✅ PASSED\n")


def test_get_ingredients():
    """Test getting scaled ingredients from PlannedMeal."""
    print("=" * 60)
    print("TEST 3: Get Scaled Ingredients")
    print("=" * 60)

    db = DatabaseInterface('data')
    recipe = db.get_recipe('71247')

    meal = PlannedMeal(
        date="2025-10-29",
        meal_type="dinner",
        recipe=recipe,
        servings=8  # Double servings
    )

    print(f"Meal: {meal.recipe.name} ({meal.servings} servings)")

    # Get ingredients
    ingredients = meal.get_ingredients()

    print(f"\nNumber of ingredients: {len(ingredients)}")
    print(f"\nFirst 3 scaled ingredients:")
    for i, ing in enumerate(ingredients[:3], 1):
        print(f"  {i}. {ing.quantity} {ing.unit or ''} {ing.name}")

    assert len(ingredients) > 0, "Should have ingredients"
    assert all(isinstance(ing, Ingredient) for ing in ingredients), "All should be Ingredient objects"

    # Verify scaling
    orig_ingredients = recipe.get_ingredients()
    if orig_ingredients[0].quantity:
        expected = orig_ingredients[0].quantity * 2
        assert ingredients[0].quantity == expected, f"First ingredient should be scaled 2x"
        print(f"\n✅ Ingredients correctly scaled: {orig_ingredients[0].quantity} → {ingredients[0].quantity}")

    print("\n✅ PASSED\n")


def test_allergen_detection():
    """Test allergen detection through PlannedMeal."""
    print("=" * 60)
    print("TEST 4: Allergen Detection")
    print("=" * 60)

    db = DatabaseInterface('data')
    recipe = db.get_recipe('71247')

    meal = PlannedMeal(
        date="2025-10-29",
        meal_type="dinner",
        recipe=recipe,
        servings=4
    )

    print(f"Meal: {meal.recipe.name}")

    # Get all allergens
    allergens = meal.get_all_allergens()
    print(f"All allergens: {allergens}")

    # Check specific allergens
    test_allergens = ["gluten", "dairy", "eggs", "peanuts"]
    for allergen in test_allergens:
        has_it = meal.has_allergen(allergen)
        print(f"  Contains {allergen}: {has_it}")

    assert isinstance(allergens, list), "Should return list of allergens"

    print("\n✅ PASSED\n")


def test_serialization():
    """Test to_dict and from_dict."""
    print("=" * 60)
    print("TEST 5: Serialization Round-Trip")
    print("=" * 60)

    db = DatabaseInterface('data')
    recipe = db.get_recipe('71247')

    meal = PlannedMeal(
        date="2025-10-29",
        meal_type="dinner",
        recipe=recipe,
        servings=6,
        notes="Extra spicy version"
    )

    print(f"Original meal: {meal}")
    print(f"Has structured ingredients: {meal.recipe.has_structured_ingredients()}")

    # Serialize
    data = meal.to_dict()
    print(f"\nSerialized to dict with {len(data)} keys")
    print(f"Recipe is nested dict: {isinstance(data['recipe'], dict)}")

    # Convert to JSON and back (simulate database storage)
    json_str = json.dumps(data)
    data_restored = json.loads(json_str)

    # Deserialize
    restored_meal = PlannedMeal.from_dict(data_restored)

    print(f"\nRestored meal: {restored_meal}")
    print(f"Has structured ingredients: {restored_meal.recipe.has_structured_ingredients()}")

    # Verify
    assert restored_meal.date == meal.date, "Date should match"
    assert restored_meal.meal_type == meal.meal_type, "Meal type should match"
    assert restored_meal.recipe.id == meal.recipe.id, "Recipe ID should match"
    assert restored_meal.recipe.name == meal.recipe.name, "Recipe name should match"
    assert restored_meal.servings == meal.servings, "Servings should match"
    assert restored_meal.notes == meal.notes, "Notes should match"

    if meal.recipe.has_structured_ingredients():
        assert restored_meal.recipe.has_structured_ingredients(), "Structured ingredients should be preserved"
        assert len(restored_meal.recipe.ingredients_structured) == len(meal.recipe.ingredients_structured), \
            "Ingredient count should match"

    print(f"\n✅ Serialization round-trip successful")
    print("\n✅ PASSED\n")


def test_backward_compatibility():
    """Test loading old PlannedMeal format (recipe_id only)."""
    print("=" * 60)
    print("TEST 6: Backward Compatibility")
    print("=" * 60)

    # Old format with recipe_id
    old_data = {
        "date": "2025-10-29",
        "meal_type": "dinner",
        "recipe_id": "71247",
        "recipe_name": "Cherry Streusel Cobbler",
        "servings": 4,
        "notes": "Old format test"
    }

    print("Loading old format PlannedMeal (recipe_id only)...")

    # Should create minimal Recipe object
    meal = PlannedMeal.from_dict(old_data)

    print(f"Meal created: {meal}")
    print(f"Recipe ID: {meal.recipe.id}")
    print(f"Recipe name: {meal.recipe.name}")

    assert meal.recipe.id == "71247", "Recipe ID should be preserved"
    assert meal.recipe.name == "Cherry Streusel Cobbler", "Recipe name should be preserved"
    assert meal.servings == 4, "Servings should be preserved"
    assert meal.notes == "Old format test", "Notes should be preserved"

    print("\n✅ Backward compatibility works")
    print("\n✅ PASSED\n")


def test_display_methods():
    """Test __str__ and get_summary methods."""
    print("=" * 60)
    print("TEST 7: Display Methods")
    print("=" * 60)

    db = DatabaseInterface('data')
    recipe = db.get_recipe('71247')

    meal = PlannedMeal(
        date="2025-10-29",
        meal_type="dinner",
        recipe=recipe,
        servings=6
    )

    print(f"__str__: {meal}")
    print(f"get_summary(): {meal.get_summary()}")

    str_repr = str(meal)
    summary = meal.get_summary()

    assert "dinner" in str_repr.lower(), "Should mention meal type"
    assert recipe.name in str_repr, "Should mention recipe name"
    assert "6" in str_repr, "Should mention servings"

    assert "2025-10-29" in summary, "Summary should include date"
    assert recipe.name in summary, "Summary should include recipe name"

    print("\n✅ PASSED\n")


def test_variant_without_variant():
    """Test PlannedMeal without variant."""
    print("=" * 60)
    print("TEST 8: Meal Without Variant")
    print("=" * 60)

    db = DatabaseInterface('data')
    recipe = db.get_recipe('71247')

    meal = PlannedMeal(
        date="2025-10-29",
        meal_type="dinner",
        recipe=recipe,
        servings=4
    )

    print(f"Meal: {meal.recipe.name}")
    print(f"has_variant(): {meal.has_variant()}")

    assert not meal.has_variant(), "Should not have variant"
    assert meal.get_effective_recipe() is recipe, "Effective recipe should be base recipe"
    assert meal.get_effective_ingredients_raw() == recipe.ingredients_raw, "Should use base ingredients"

    # Serialization should not include variant
    data = meal.to_dict()
    assert "variant" not in data, "Variant should not be in serialized data"

    print("\n✅ PASSED\n")


def test_variant_with_variant():
    """Test PlannedMeal with variant."""
    print("=" * 60)
    print("TEST 9: Meal With Variant")
    print("=" * 60)

    db = DatabaseInterface('data')
    recipe = db.get_recipe('71247')

    # Create a variant with modified ingredients
    variant = {
        "variant_id": "variant:snap_test123:2025-10-29:dinner",
        "base_recipe_id": recipe.id,
        "patch_ops": [
            {
                "op": "replace_ingredient",
                "target_index": 0,
                "target_name": "original",
                "replacement": {"name": "modified", "quantity": "2 cups"}
            }
        ],
        "compiled_recipe": {
            "id": "variant:snap_test123:2025-10-29:dinner",
            "name": f"{recipe.name} (modified)",
            "description": recipe.description,
            "ingredients": [],
            "ingredients_raw": ["2 cups modified ingredient", "remaining base ingredients"],
            "steps": recipe.steps,
            "servings": recipe.servings,
            "serving_size": recipe.serving_size,
            "tags": recipe.tags,
        },
        "warnings": [],
        "compiled_at": "2025-10-29T10:00:00Z",
        "compiler_version": "v0"
    }

    meal = PlannedMeal(
        date="2025-10-29",
        meal_type="dinner",
        recipe=recipe,
        servings=4,
        variant=variant
    )

    print(f"Base recipe: {meal.recipe.name}")
    print(f"has_variant(): {meal.has_variant()}")

    assert meal.has_variant(), "Should have variant"

    effective = meal.get_effective_recipe()
    print(f"Effective recipe: {effective.name}")

    assert effective.name == f"{recipe.name} (modified)", "Should use compiled recipe name"
    assert "modified" in meal.get_effective_ingredients_raw()[0], "Should use modified ingredients"

    print("\n✅ PASSED\n")


def test_variant_serialization():
    """Test variant survives serialization round-trip."""
    print("=" * 60)
    print("TEST 10: Variant Serialization")
    print("=" * 60)

    db = DatabaseInterface('data')
    recipe = db.get_recipe('71247')

    variant = {
        "variant_id": "variant:snap_test123:2025-10-29:dinner",
        "base_recipe_id": recipe.id,
        "patch_ops": [],
        "compiled_recipe": {
            "id": "variant:snap_test123:2025-10-29:dinner",
            "name": "Modified Recipe",
            "description": "",
            "ingredients": [],
            "ingredients_raw": ["test ingredient"],
            "steps": [],
            "servings": 4,
            "serving_size": "",
            "tags": [],
        },
        "warnings": ["Test warning"],
        "compiled_at": "2025-10-29T10:00:00Z",
        "compiler_version": "v0"
    }

    meal = PlannedMeal(
        date="2025-10-29",
        meal_type="dinner",
        recipe=recipe,
        servings=4,
        variant=variant
    )

    # Serialize
    data = meal.to_dict()
    print(f"Serialized with {len(data)} keys")
    assert "variant" in data, "Variant should be in serialized data"

    # Convert to JSON and back
    json_str = json.dumps(data)
    data_restored = json.loads(json_str)

    # Deserialize
    restored = PlannedMeal.from_dict(data_restored)

    print(f"Restored has_variant(): {restored.has_variant()}")
    assert restored.has_variant(), "Restored meal should have variant"
    assert restored.variant["variant_id"] == variant["variant_id"], "Variant ID should match"
    assert restored.get_effective_ingredients_raw() == ["test ingredient"], "Effective ingredients should match"

    print("\n✅ PASSED\n")


def main():
    """Run all tests."""
    print("\n" + "=" * 60)
    print("PLANNED MEAL IMPLEMENTATION TESTS")
    print("=" * 60 + "\n")

    try:
        test_create_planned_meal()
        test_get_scaled_recipe()
        test_get_ingredients()
        test_allergen_detection()
        test_serialization()
        test_backward_compatibility()
        test_display_methods()
        test_variant_without_variant()
        test_variant_with_variant()
        test_variant_serialization()

        print("=" * 60)
        print("ALL TESTS PASSED! ✅")
        print("=" * 60)
        print("\n✅ PlannedMeal successfully embeds Recipe objects")
        print("✅ Scaling, allergen detection, and serialization all work")
        print("✅ Backward compatibility maintained")
        print("✅ Variant support works correctly")

    except Exception as e:
        print(f"\n❌ TEST FAILED:")
        print(f"   {type(e).__name__}: {e}")
        import traceback
        traceback.print_exc()
        return 1

    return 0


if __name__ == "__main__":
    exit(main())
