"""
Unit tests for validate_plan() in chatbot.py

Tests the validation logic for meal plan correctness.
"""

import pytest
import sys
from pathlib import Path
from dataclasses import dataclass
from typing import List, Optional

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "src"))

from requirements_parser import DayRequirement


# Mock Recipe class for testing
@dataclass
class MockRecipe:
    """Minimal recipe mock for validation testing."""
    id: int
    name: str
    tags: List[str]


# Import after path setup
from chatbot import MealPlanningChatbot, ValidationFailure


class TestValidatePlanCuisine:
    """Test cuisine validation."""

    @pytest.fixture
    def chatbot(self, mocker):
        """Create chatbot with mocked dependencies."""
        # Mock the Anthropic client and database
        mocker.patch('chatbot.Anthropic')
        mocker.patch('chatbot.MealPlanningAssistant')
        mocker.patch.dict('os.environ', {'ANTHROPIC_API_KEY': 'test-key'})

        bot = MealPlanningChatbot(verbose=False)
        return bot

    def test_cuisine_match_passes(self, chatbot):
        """Recipe with correct cuisine tag passes validation."""
        recipes = [MockRecipe(1, "Spaghetti Carbonara", ["italian", "main-dish", "dinner"])]
        requirements = [DayRequirement(date="2025-01-06", cuisine="italian")]

        hard_failures, soft_warnings = chatbot.validate_plan(recipes, requirements)

        assert len(hard_failures) == 0

    def test_cuisine_mismatch_fails(self, chatbot):
        """Recipe without required cuisine fails validation."""
        recipes = [MockRecipe(1, "Beef Tacos", ["mexican", "main-dish"])]
        requirements = [DayRequirement(date="2025-01-06", cuisine="italian")]

        hard_failures, soft_warnings = chatbot.validate_plan(recipes, requirements)

        assert len(hard_failures) == 1
        assert hard_failures[0].requirement == "cuisine=italian"

    def test_multiple_days_mixed_validation(self, chatbot):
        """Test multiple days with mixed pass/fail."""
        recipes = [
            MockRecipe(1, "Pasta Primavera", ["italian", "main-dish"]),
            MockRecipe(2, "Beef Stew", ["american", "main-dish"]),  # Wrong - should be irish
        ]
        requirements = [
            DayRequirement(date="2025-01-06", cuisine="italian"),
            DayRequirement(date="2025-01-07", cuisine="irish"),
        ]

        hard_failures, soft_warnings = chatbot.validate_plan(recipes, requirements)

        assert len(hard_failures) == 1
        assert hard_failures[0].date == "2025-01-07"
        assert "irish" in hard_failures[0].reason


class TestValidatePlanDietary:
    """Test dietary constraint validation."""

    @pytest.fixture
    def chatbot(self, mocker):
        """Create chatbot with mocked dependencies."""
        mocker.patch('chatbot.Anthropic')
        mocker.patch('chatbot.MealPlanningAssistant')
        mocker.patch.dict('os.environ', {'ANTHROPIC_API_KEY': 'test-key'})

        bot = MealPlanningChatbot(verbose=False)
        return bot

    def test_vegetarian_hard_constraint_passes(self, chatbot):
        """Vegetarian recipe passes vegetarian requirement."""
        recipes = [MockRecipe(1, "Veggie Stir Fry", ["vegetarian", "main-dish", "healthy"])]
        requirements = [DayRequirement(date="2025-01-06", dietary_hard=["vegetarian"])]

        hard_failures, soft_warnings = chatbot.validate_plan(recipes, requirements)

        assert len(hard_failures) == 0

    def test_vegetarian_hard_constraint_fails(self, chatbot):
        """Non-vegetarian recipe fails vegetarian requirement."""
        recipes = [MockRecipe(1, "Chicken Parmesan", ["italian", "main-dish", "poultry"])]
        requirements = [DayRequirement(date="2025-01-06", dietary_hard=["vegetarian"])]

        hard_failures, soft_warnings = chatbot.validate_plan(recipes, requirements)

        assert len(hard_failures) == 1
        assert "vegetarian" in hard_failures[0].reason

    def test_kid_friendly_soft_constraint(self, chatbot):
        """Kid-friendly is soft - missing doesn't cause hard failure."""
        recipes = [MockRecipe(1, "Spicy Thai Curry", ["thai", "main-dish"])]
        requirements = [DayRequirement(date="2025-01-06", dietary_soft=["kid-friendly"])]

        hard_failures, soft_warnings = chatbot.validate_plan(recipes, requirements)

        # No hard failures - kid-friendly is soft
        assert len(hard_failures) == 0
        # But should have a soft warning
        assert any("kid-friendly" in w for w in soft_warnings)


class TestValidatePlanCourse:
    """Test main-dish / course validation."""

    @pytest.fixture
    def chatbot(self, mocker):
        """Create chatbot with mocked dependencies."""
        mocker.patch('chatbot.Anthropic')
        mocker.patch('chatbot.MealPlanningAssistant')
        mocker.patch.dict('os.environ', {'ANTHROPIC_API_KEY': 'test-key'})

        bot = MealPlanningChatbot(verbose=False)
        return bot

    def test_dessert_rejected_for_dinner(self, chatbot):
        """Dessert fails main-dish requirement for dinner."""
        recipes = [MockRecipe(1, "Chocolate Cake", ["desserts", "baking", "sweet"])]
        requirements = [DayRequirement(date="2025-01-06")]

        hard_failures, soft_warnings = chatbot.validate_plan(recipes, requirements)

        assert len(hard_failures) == 1
        assert "main-dish" in hard_failures[0].requirement

    def test_main_dish_passes(self, chatbot):
        """Recipe with main-dish tag passes."""
        recipes = [MockRecipe(1, "Grilled Chicken", ["main-dish", "poultry", "healthy"])]
        requirements = [DayRequirement(date="2025-01-06")]

        hard_failures, soft_warnings = chatbot.validate_plan(recipes, requirements)

        # No hard failures related to course
        course_failures = [f for f in hard_failures if "main-dish" in f.requirement]
        assert len(course_failures) == 0

    def test_beverage_rejected(self, chatbot):
        """Beverage fails validation for dinner slot."""
        recipes = [MockRecipe(1, "Strawberry Smoothie", ["beverages", "fruit", "healthy"])]
        requirements = [DayRequirement(date="2025-01-06")]

        hard_failures, soft_warnings = chatbot.validate_plan(recipes, requirements)

        assert len(hard_failures) == 1


class TestValidatePlanSurprise:
    """Test surprise day handling."""

    @pytest.fixture
    def chatbot(self, mocker):
        """Create chatbot with mocked dependencies."""
        mocker.patch('chatbot.Anthropic')
        mocker.patch('chatbot.MealPlanningAssistant')
        mocker.patch.dict('os.environ', {'ANTHROPIC_API_KEY': 'test-key'})

        bot = MealPlanningChatbot(verbose=False)
        return bot

    def test_surprise_always_passes(self, chatbot):
        """Surprise day accepts any recipe."""
        recipes = [MockRecipe(1, "Random Dish", ["experimental", "fusion"])]
        requirements = [DayRequirement(date="2025-01-06", surprise=True)]

        hard_failures, soft_warnings = chatbot.validate_plan(recipes, requirements)

        # Surprise days skip validation
        assert len(hard_failures) == 0
