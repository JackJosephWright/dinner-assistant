#!/usr/bin/env python3
"""
Test script for incremental shopping list contribution tracking.
"""

from src.data.models import IngredientContribution, GroceryItem

def test_add_contributions():
    """Test adding contributions to an item."""
    print("Test 1: Add contributions")
    print("-" * 50)

    item = GroceryItem(
        name="Chicken Breast",
        quantity="0 lbs",
        category="meat",
        recipe_sources=[],
        contributions=[]
    )

    # Add from first recipe
    item.add_contribution("Grilled Chicken", "2 lbs", "lbs", 2.0)
    print(f"After adding 2 lbs from 'Grilled Chicken':")
    print(f"  Total: {item.quantity}")
    print(f"  Sources: {item.recipe_sources}")
    print(f"  Contributions: {len(item.contributions)}")
    assert item.quantity == "2 lbs"
    assert "Grilled Chicken" in item.recipe_sources

    # Add from second recipe
    item.add_contribution("Stir Fry", "1 lbs", "lbs", 1.0)
    print(f"\nAfter adding 1 lb from 'Stir Fry':")
    print(f"  Total: {item.quantity}")
    print(f"  Sources: {item.recipe_sources}")
    print(f"  Contributions: {len(item.contributions)}")
    assert item.quantity == "3 lbs"
    assert "Stir Fry" in item.recipe_sources
    assert len(item.contributions) == 2

    # Add from user
    item.add_contribution("User", "1.5 lbs", "lbs", 1.5)
    print(f"\nAfter adding 1.5 lbs from 'User':")
    print(f"  Total: {item.quantity}")
    print(f"  Sources: {item.recipe_sources}")
    print(f"  Contributions: {len(item.contributions)}")
    assert item.quantity == "4.5 lbs"
    assert "User" in item.recipe_sources
    assert len(item.contributions) == 3

    print("\n✓ Test 1 passed!")
    return item


def test_remove_contributions(item):
    """Test removing contributions from an item."""
    print("\n\nTest 2: Remove contributions")
    print("-" * 50)

    # Remove Stir Fry
    item.remove_contribution("Stir Fry")
    print(f"After removing 'Stir Fry':")
    print(f"  Total: {item.quantity}")
    print(f"  Sources: {item.recipe_sources}")
    print(f"  Contributions: {len(item.contributions)}")
    assert item.quantity == "3.5 lbs"  # 2 + 1.5
    assert "Stir Fry" not in item.recipe_sources
    assert len(item.contributions) == 2

    # Remove Grilled Chicken
    item.remove_contribution("Grilled Chicken")
    print(f"\nAfter removing 'Grilled Chicken':")
    print(f"  Total: {item.quantity}")
    print(f"  Sources: {item.recipe_sources}")
    print(f"  Contributions: {len(item.contributions)}")
    assert item.quantity == "1.5 lbs"  # Just user's 1.5
    assert "Grilled Chicken" not in item.recipe_sources
    assert len(item.contributions) == 1

    print("\n✓ Test 2 passed!")
    return item


def test_serialization(item):
    """Test serialization and deserialization."""
    print("\n\nTest 3: Serialization")
    print("-" * 50)

    # Serialize
    data = item.to_dict()
    print(f"Serialized data:")
    print(f"  name: {data['name']}")
    print(f"  quantity: {data['quantity']}")
    print(f"  contributions: {len(data['contributions'])} items")

    # Deserialize
    item2 = GroceryItem.from_dict(data)
    print(f"\nDeserialized item:")
    print(f"  Total: {item2.quantity}")
    print(f"  Sources: {item2.recipe_sources}")
    print(f"  Contributions: {len(item2.contributions)}")

    assert item2.quantity == item.quantity
    assert item2.recipe_sources == item.recipe_sources
    assert len(item2.contributions) == len(item.contributions)

    print("\n✓ Test 3 passed!")


def test_backward_compat():
    """Test backward compatibility with old format."""
    print("\n\nTest 4: Backward Compatibility")
    print("-" * 50)

    # Old format (no contributions field)
    old_data = {
        "name": "Flour",
        "quantity": "2 cups",
        "category": "pantry",
        "recipe_sources": ["Pancakes", "Cookies"],
        "notes": None
    }

    item = GroceryItem.from_dict(old_data)
    print(f"Loaded old format:")
    print(f"  Total: {item.quantity}")
    print(f"  Sources: {item.recipe_sources}")
    print(f"  Contributions: {len(item.contributions)}")

    # Should create contributions from recipe_sources
    assert len(item.contributions) == 2
    assert "Pancakes" in [c.recipe_name for c in item.contributions]
    assert "Cookies" in [c.recipe_name for c in item.contributions]

    print("\n✓ Test 4 passed!")


def main():
    """Run all tests."""
    print("=" * 50)
    print("Testing Incremental Shopping List")
    print("=" * 50)

    item = test_add_contributions()
    item = test_remove_contributions(item)
    test_serialization(item)
    test_backward_compat()

    print("\n" + "=" * 50)
    print("✓ All tests passed!")
    print("=" * 50)


if __name__ == "__main__":
    main()
