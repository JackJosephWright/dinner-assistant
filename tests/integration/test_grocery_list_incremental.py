#!/usr/bin/env python3
"""
Test script for incremental GroceryList operations.
"""

from src.data.models import GroceryList, Recipe, Ingredient

def create_test_recipes():
    """Create test recipes with ingredients."""
    # Recipe 1: Grilled Chicken (enriched with structured ingredients)
    ingredients1 = ["2 lbs chicken breast", "1 tbsp olive oil", "Salt and pepper"]
    recipe1 = Recipe(
        id="1",
        name="Grilled Chicken",
        description="Simple grilled chicken",
        ingredients=ingredients1,  # Legacy field
        ingredients_raw=ingredients1,
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

    # Recipe 2: Pasta (enriched)
    ingredients2 = ["1 lb pasta", "2 cups tomato sauce", "1 tbsp olive oil"]
    recipe2 = Recipe(
        id="2",
        name="Pasta Marinara",
        description="Classic pasta",
        ingredients=ingredients2,  # Legacy field
        ingredients_raw=ingredients2,
        ingredients_structured=[
            Ingredient(raw="1 lb pasta", name="pasta", quantity=1.0, unit="lb", category="pantry"),
            Ingredient(raw="2 cups tomato sauce", name="tomato sauce", quantity=2.0, unit="cups", category="pantry"),
            Ingredient(raw="1 tbsp olive oil", name="olive oil", quantity=1.0, unit="tbsp", category="pantry"),
        ],
        steps=["Cook pasta"],
        servings=4,
        serving_size="1 plate",
        tags=["easy", "dinner"],
    )

    # Recipe 3: Salad (non-enriched, raw strings only)
    ingredients3 = ["1 head lettuce", "1/4 cup parmesan cheese", "1/2 cup croutons"]
    recipe3 = Recipe(
        id="3",
        name="Caesar Salad",
        description="Fresh salad",
        ingredients=ingredients3,  # Legacy field
        ingredients_raw=ingredients3,
        ingredients_structured=None,
        steps=["Mix ingredients"],
        servings=2,
        serving_size="1 bowl",
        tags=["easy", "salad"],
    )

    return recipe1, recipe2, recipe3


def test_add_recipe():
    """Test adding recipes to grocery list."""
    print("Test 1: Add single recipe")
    print("-" * 50)

    recipe1, _, _ = create_test_recipes()

    # Create empty grocery list
    grocery_list = GroceryList(
        week_of="2025-11-04",
        items=[],
    )

    # Add recipe
    grocery_list.add_recipe_ingredients(recipe1)

    print(f"Added '{recipe1.name}' to list")
    print(f"Total items: {len(grocery_list.items)}")
    for item in grocery_list.items:
        print(f"  - {item.name}: {item.quantity} ({item.category})")
        print(f"    Sources: {item.recipe_sources}")

    assert len(grocery_list.items) == 3
    assert any(item.name.lower() == "chicken breast" for item in grocery_list.items)
    assert any(item.name.lower() == "olive oil" for item in grocery_list.items)

    print("\n✓ Test 1 passed!")
    return grocery_list


def test_add_multiple_recipes(grocery_list):
    """Test adding multiple recipes with overlapping ingredients."""
    print("\n\nTest 2: Add recipe with overlapping ingredient")
    print("-" * 50)

    _, recipe2, _ = create_test_recipes()

    # Add second recipe (also has olive oil)
    grocery_list.add_recipe_ingredients(recipe2)

    print(f"Added '{recipe2.name}' to list")
    print(f"Total items: {len(grocery_list.items)}")

    # Find olive oil
    olive_oil = next((item for item in grocery_list.items if "olive oil" in item.name.lower()), None)

    if olive_oil:
        print(f"\nOlive Oil consolidation:")
        print(f"  Total: {olive_oil.quantity}")
        print(f"  Contributions:")
        for contrib in olive_oil.contributions:
            print(f"    - {contrib.recipe_name}: {contrib.quantity}")

        assert len(olive_oil.contributions) == 2
        assert "Grilled Chicken" in olive_oil.recipe_sources
        assert "Pasta Marinara" in olive_oil.recipe_sources

    print("\n✓ Test 2 passed!")
    return grocery_list


def test_add_non_enriched_recipe(grocery_list):
    """Test adding recipe without structured ingredients."""
    print("\n\nTest 3: Add non-enriched recipe")
    print("-" * 50)

    _, _, recipe3 = create_test_recipes()

    # Add recipe with raw ingredients only
    grocery_list.add_recipe_ingredients(recipe3)

    print(f"Added '{recipe3.name}' to list")
    print(f"Total items: {len(grocery_list.items)}")

    # Find lettuce (should be parsed from raw string)
    lettuce = next((item for item in grocery_list.items if "lettuce" in item.name.lower()), None)

    if lettuce:
        print(f"\nLettuce (parsed from raw string):")
        print(f"  Name: {lettuce.name}")
        print(f"  Quantity: {lettuce.quantity}")
        print(f"  Category: {lettuce.category}")
        print(f"  Sources: {lettuce.recipe_sources}")

        assert lettuce.category == "produce"  # Auto-categorized

    print("\n✓ Test 3 passed!")
    return grocery_list


def test_remove_recipe(grocery_list):
    """Test removing a recipe from grocery list."""
    print("\n\nTest 4: Remove recipe")
    print("-" * 50)

    initial_count = len(grocery_list.items)
    print(f"Before removal: {initial_count} items")

    # Remove Pasta Marinara
    grocery_list.remove_recipe_ingredients("Pasta Marinara")

    print(f"After removing 'Pasta Marinara': {len(grocery_list.items)} items")

    # Olive oil should still exist (from Grilled Chicken)
    olive_oil = next((item for item in grocery_list.items if "olive oil" in item.name.lower()), None)

    if olive_oil:
        print(f"\nOlive Oil after removal:")
        print(f"  Total: {olive_oil.quantity}")
        print(f"  Sources: {olive_oil.recipe_sources}")
        print(f"  Contributions: {len(olive_oil.contributions)}")

        assert len(olive_oil.contributions) == 1
        assert "Grilled Chicken" in olive_oil.recipe_sources
        assert "Pasta Marinara" not in olive_oil.recipe_sources

    # Pasta should be gone
    pasta = next((item for item in grocery_list.items if "pasta" in item.name.lower()), None)
    assert pasta is None, "Pasta should be removed"

    # Chicken should still be there
    chicken = next((item for item in grocery_list.items if "chicken" in item.name.lower()), None)
    assert chicken is not None, "Chicken should still exist"

    print("\n✓ Test 4 passed!")
    return grocery_list


def test_store_sections(grocery_list):
    """Test that store sections are organized correctly."""
    print("\n\nTest 5: Store sections")
    print("-" * 50)

    print(f"Store sections: {list(grocery_list.store_sections.keys())}")

    for section, items in grocery_list.store_sections.items():
        print(f"\n{section.upper()}:")
        for item in items:
            print(f"  - {item.name}: {item.quantity}")

    # Should have meat, pantry, produce
    assert "meat" in grocery_list.store_sections
    assert "pantry" in grocery_list.store_sections
    assert "produce" in grocery_list.store_sections

    print("\n✓ Test 5 passed!")


def test_serialization(grocery_list):
    """Test serialization with contributions."""
    print("\n\nTest 6: Serialization")
    print("-" * 50)

    # Serialize
    data = grocery_list.to_dict()
    print(f"Serialized {len(data['items'])} items")

    # Check contributions are included
    for item_data in data['items']:
        if 'contributions' in item_data and len(item_data['contributions']) > 0:
            print(f"\n{item_data['name']}:")
            print(f"  Contributions: {len(item_data['contributions'])}")
            for contrib in item_data['contributions']:
                print(f"    - {contrib['recipe_name']}: {contrib['quantity']}")

    # Deserialize
    grocery_list2 = GroceryList.from_dict(data)
    print(f"\nDeserialized {len(grocery_list2.items)} items")

    assert len(grocery_list2.items) == len(grocery_list.items)

    print("\n✓ Test 6 passed!")


def main():
    """Run all tests."""
    print("=" * 50)
    print("Testing Incremental GroceryList")
    print("=" * 50)

    grocery_list = test_add_recipe()
    grocery_list = test_add_multiple_recipes(grocery_list)
    grocery_list = test_add_non_enriched_recipe(grocery_list)
    grocery_list = test_remove_recipe(grocery_list)
    test_store_sections(grocery_list)
    test_serialization(grocery_list)

    print("\n" + "=" * 50)
    print("✓ All tests passed!")
    print("=" * 50)


if __name__ == "__main__":
    main()
