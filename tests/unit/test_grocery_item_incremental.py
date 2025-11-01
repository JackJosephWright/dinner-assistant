"""
Unit tests for GroceryItem incremental updates.
"""

import pytest
from src.data.models import GroceryItem, IngredientContribution


class TestGroceryItemContributions:
    """Test GroceryItem contribution tracking."""

    def test_add_single_contribution(self):
        """Test adding a single contribution."""
        item = GroceryItem(
            name="Chicken Breast",
            quantity="0 lbs",
            category="meat",
            recipe_sources=[],
            contributions=[]
        )

        item.add_contribution("Grilled Chicken", "2 lbs", "lbs", 2.0)

        assert item.quantity == "2 lbs"
        assert len(item.contributions) == 1
        assert "Grilled Chicken" in item.recipe_sources
        assert item.contributions[0].recipe_name == "Grilled Chicken"

    def test_add_multiple_contributions(self):
        """Test adding contributions from multiple recipes."""
        item = GroceryItem(
            name="Flour",
            quantity="0 cups",
            category="pantry",
            recipe_sources=[],
            contributions=[]
        )

        item.add_contribution("Pancakes", "2 cups", "cups", 2.0)
        item.add_contribution("Cookies", "1 cups", "cups", 1.0)
        item.add_contribution("Bread", "3 cups", "cups", 3.0)

        assert item.quantity == "6 cups"
        assert len(item.contributions) == 3
        assert len(item.recipe_sources) == 3
        assert "Pancakes" in item.recipe_sources
        assert "Cookies" in item.recipe_sources
        assert "Bread" in item.recipe_sources

    def test_add_contribution_with_decimals(self):
        """Test adding fractional quantities."""
        item = GroceryItem(
            name="Milk",
            quantity="0 gallons",
            category="dairy",
            recipe_sources=[],
            contributions=[]
        )

        item.add_contribution("Smoothie", "0.5 gallons", "gallons", 0.5)
        item.add_contribution("Pancakes", "0.25 gallons", "gallons", 0.25)

        assert item.quantity == "0.8 gallons"  # Should format as decimal
        assert len(item.contributions) == 2

    def test_add_user_contribution(self):
        """Test adding extra items from user."""
        item = GroceryItem(
            name="Bananas",
            quantity="2 count",
            category="produce",
            recipe_sources=["Smoothie"],
            contributions=[
                IngredientContribution("Smoothie", "2", "count", 2.0)
            ]
        )

        # User adds 6 more
        item.add_contribution("User", "6", "count", 6.0)

        assert item.quantity == "8 count"
        assert len(item.contributions) == 2
        assert "User" in item.recipe_sources
        assert "Smoothie" in item.recipe_sources

    def test_remove_single_contribution(self):
        """Test removing a contribution."""
        item = GroceryItem(
            name="Tomatoes",
            quantity="5 count",
            category="produce",
            recipe_sources=["Pasta", "Salad"],
            contributions=[
                IngredientContribution("Pasta", "3", "count", 3.0),
                IngredientContribution("Salad", "2", "count", 2.0),
            ]
        )

        item.remove_contribution("Pasta")

        assert item.quantity == "2 count"
        assert len(item.contributions) == 1
        assert "Pasta" not in item.recipe_sources
        assert "Salad" in item.recipe_sources

    def test_remove_all_contributions(self):
        """Test removing all contributions leaves item at zero."""
        item = GroceryItem(
            name="Onions",
            quantity="2 count",
            category="produce",
            recipe_sources=["Stir Fry"],
            contributions=[
                IngredientContribution("Stir Fry", "2", "count", 2.0)
            ]
        )

        item.remove_contribution("Stir Fry")

        assert item.quantity == "0"
        assert len(item.contributions) == 0
        assert len(item.recipe_sources) == 0

    def test_remove_nonexistent_contribution(self):
        """Test removing a contribution that doesn't exist (no-op)."""
        item = GroceryItem(
            name="Garlic",
            quantity="3 cloves",
            category="produce",
            recipe_sources=["Pasta"],
            contributions=[
                IngredientContribution("Pasta", "3 cloves", "cloves", 3.0)
            ]
        )

        item.remove_contribution("Nonexistent Recipe")

        assert item.quantity == "3 cloves"
        assert len(item.contributions) == 1
        assert "Pasta" in item.recipe_sources

    def test_recipe_sources_updated_automatically(self):
        """Test recipe_sources syncs with contributions."""
        item = GroceryItem(
            name="Salt",
            quantity="0 tsp",
            category="pantry",
            recipe_sources=[],
            contributions=[]
        )

        # Add contributions
        item.add_contribution("Recipe A", "1 tsp", "tsp", 1.0)
        assert item.recipe_sources == ["Recipe A"]

        item.add_contribution("Recipe B", "2 tsp", "tsp", 2.0)
        assert set(item.recipe_sources) == {"Recipe A", "Recipe B"}

        # Remove contribution
        item.remove_contribution("Recipe A")
        assert item.recipe_sources == ["Recipe B"]

    def test_integer_quantities_format_without_decimal(self):
        """Test that whole numbers format as integers."""
        item = GroceryItem(
            name="Eggs",
            quantity="0 count",
            category="dairy",
            recipe_sources=[],
            contributions=[]
        )

        item.add_contribution("Pancakes", "6", "count", 6.0)

        # Should be "6 count", not "6.0 count"
        assert item.quantity == "6 count"
        assert ".0" not in item.quantity


class TestGroceryItemSerialization:
    """Test GroceryItem serialization with contributions."""

    def test_serialize_with_contributions(self):
        """Test serialization includes contributions."""
        item = GroceryItem(
            name="Chicken",
            quantity="3 lbs",
            category="meat",
            recipe_sources=["Recipe A", "Recipe B"],
            contributions=[
                IngredientContribution("Recipe A", "2 lbs", "lbs", 2.0),
                IngredientContribution("Recipe B", "1 lbs", "lbs", 1.0),
            ]
        )

        data = item.to_dict()

        assert data["name"] == "Chicken"
        assert data["quantity"] == "3 lbs"
        assert "contributions" in data
        assert len(data["contributions"]) == 2
        assert data["contributions"][0]["recipe_name"] == "Recipe A"

    def test_deserialize_with_contributions(self):
        """Test deserialization restores contributions."""
        data = {
            "name": "Flour",
            "quantity": "5 cups",
            "category": "pantry",
            "recipe_sources": ["Pancakes", "Cookies"],
            "notes": None,
            "contributions": [
                {"recipe_name": "Pancakes", "quantity": "2 cups", "unit": "cups", "amount": 2.0},
                {"recipe_name": "Cookies", "quantity": "3 cups", "unit": "cups", "amount": 3.0},
            ]
        }

        item = GroceryItem.from_dict(data)

        assert item.name == "Flour"
        assert item.quantity == "5 cups"
        assert len(item.contributions) == 2
        assert item.contributions[0].recipe_name == "Pancakes"
        assert item.contributions[1].recipe_name == "Cookies"

    def test_backward_compat_no_contributions(self):
        """Test loading old format without contributions field."""
        data = {
            "name": "Milk",
            "quantity": "1 gallon",
            "category": "dairy",
            "recipe_sources": ["Smoothie", "Pancakes"],
            "notes": None
        }

        item = GroceryItem.from_dict(data)

        # Should create contributions from recipe_sources
        assert len(item.contributions) == 2
        assert "Smoothie" in [c.recipe_name for c in item.contributions]
        assert "Pancakes" in [c.recipe_name for c in item.contributions]
        # Quantity should be preserved
        assert item.quantity == "1 gallon"

    def test_backward_compat_empty_recipe_sources(self):
        """Test old format with no recipe sources."""
        data = {
            "name": "Sugar",
            "quantity": "2 cups",
            "category": "pantry",
            "recipe_sources": [],
            "notes": None
        }

        item = GroceryItem.from_dict(data)

        # Should have empty contributions
        assert len(item.contributions) == 0
        assert item.quantity == "2 cups"

    def test_roundtrip_serialization(self):
        """Test serialize → deserialize preserves data."""
        original = GroceryItem(
            name="Tomatoes",
            quantity="4 count",
            category="produce",
            recipe_sources=["Pasta", "Salad"],
            contributions=[
                IngredientContribution("Pasta", "3", "count", 3.0),
                IngredientContribution("Salad", "1", "count", 1.0),
            ]
        )

        data = original.to_dict()
        restored = GroceryItem.from_dict(data)

        assert restored.name == original.name
        assert restored.quantity == original.quantity
        assert restored.category == original.category
        assert len(restored.contributions) == len(original.contributions)
        assert set(restored.recipe_sources) == set(original.recipe_sources)


class TestGroceryItemEdgeCases:
    """Test edge cases for GroceryItem."""

    def test_empty_item(self):
        """Test item with no contributions."""
        item = GroceryItem(
            name="Empty",
            quantity="0",
            category="other",
            recipe_sources=[],
            contributions=[]
        )

        assert item.quantity == "0"
        assert len(item.contributions) == 0

    def test_add_zero_amount(self):
        """Test adding zero quantity."""
        item = GroceryItem(
            name="Test",
            quantity="0",
            category="other",
            recipe_sources=[],
            contributions=[]
        )

        item.add_contribution("Recipe", "0 cups", "cups", 0.0)

        assert item.quantity == "0 cups"
        assert len(item.contributions) == 1

    def test_very_large_quantity(self):
        """Test handling very large quantities."""
        item = GroceryItem(
            name="Water",
            quantity="0 gallons",
            category="other",
            recipe_sources=[],
            contributions=[]
        )

        item.add_contribution("Recipe", "1000 gallons", "gallons", 1000.0)

        assert item.quantity == "1000 gallons"
        assert item.contributions[0].amount == 1000.0

    def test_multiple_user_contributions(self):
        """Test adding multiple user contributions (should merge)."""
        item = GroceryItem(
            name="Bananas",
            quantity="0 count",
            category="produce",
            recipe_sources=[],
            contributions=[]
        )

        item.add_contribution("User", "3", "count", 3.0)
        item.add_contribution("User", "2", "count", 2.0)

        # Both should be tracked (not merged automatically)
        assert len(item.contributions) == 2
        assert item.quantity == "5 count"

    def test_remove_then_add_same_recipe(self):
        """Test removing and re-adding from same recipe."""
        item = GroceryItem(
            name="Flour",
            quantity="2 cups",
            category="pantry",
            recipe_sources=["Pancakes"],
            contributions=[
                IngredientContribution("Pancakes", "2 cups", "cups", 2.0)
            ]
        )

        # Remove
        item.remove_contribution("Pancakes")
        assert item.quantity == "0"

        # Re-add
        item.add_contribution("Pancakes", "3 cups", "cups", 3.0)
        assert item.quantity == "3 cups"
        assert len(item.contributions) == 1
