"""
Unit tests for IngredientContribution model.
"""

import pytest
from src.data.models import IngredientContribution


class TestIngredientContribution:
    """Test IngredientContribution dataclass."""

    def test_create_contribution(self):
        """Test creating a contribution."""
        contrib = IngredientContribution(
            recipe_name="Grilled Chicken",
            quantity="2 lbs",
            unit="lbs",
            amount=2.0
        )

        assert contrib.recipe_name == "Grilled Chicken"
        assert contrib.quantity == "2 lbs"
        assert contrib.unit == "lbs"
        assert contrib.amount == 2.0

    def test_contribution_serialization(self):
        """Test to_dict and from_dict."""
        contrib = IngredientContribution(
            recipe_name="Stir Fry",
            quantity="1 cup",
            unit="cup",
            amount=1.0
        )

        # Serialize
        data = contrib.to_dict()
        assert data["recipe_name"] == "Stir Fry"
        assert data["quantity"] == "1 cup"
        assert data["unit"] == "cup"
        assert data["amount"] == 1.0

        # Deserialize
        contrib2 = IngredientContribution.from_dict(data)
        assert contrib2.recipe_name == contrib.recipe_name
        assert contrib2.quantity == contrib.quantity
        assert contrib2.unit == contrib.unit
        assert contrib2.amount == contrib.amount

    def test_user_contribution(self):
        """Test contribution from user (not recipe)."""
        contrib = IngredientContribution(
            recipe_name="User",
            quantity="6",
            unit="count",
            amount=6.0
        )

        assert contrib.recipe_name == "User"
        assert contrib.quantity == "6"
        assert contrib.unit == "count"

    def test_fractional_amount(self):
        """Test contributions with fractional amounts."""
        contrib = IngredientContribution(
            recipe_name="Smoothie",
            quantity="1.5 cups",
            unit="cups",
            amount=1.5
        )

        assert contrib.amount == 1.5
        assert contrib.quantity == "1.5 cups"
