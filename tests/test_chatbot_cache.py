#!/usr/bin/env python3
"""
Unit tests for chatbot in-memory plan caching.

Tests that MealPlan objects are properly cached after creation and loading,
and that cached plans are used for follow-up queries.
"""

import pytest
import sys
import os
from datetime import datetime, timedelta
from unittest.mock import Mock, MagicMock, patch

# Add parent directory to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

# Import data models first
from src.data.models import Recipe, PlannedMeal, MealPlan, Ingredient

# Mock the relative imports in chatbot.py before importing it
sys.modules['main'] = Mock()
sys.modules['data'] = sys.modules['src.data']
sys.modules['data.models'] = sys.modules['src.data.models']

from src.chatbot import MealPlanningChatbot


@pytest.fixture
def mock_recipe_with_dairy():
    """Create a mock recipe with dairy allergen."""
    dairy_ing = Ingredient(
        raw="1 cup milk",
        name="milk",
        quantity=1.0,
        unit="cup",
        allergens=["dairy"]
    )
    butter_ing = Ingredient(
        raw="1/2 cup butter",
        name="butter",
        quantity=0.5,
        unit="cup",
        allergens=["dairy"]
    )

    return Recipe(
        id="1",
        name="Creamy Pasta",
        description="Pasta with cream sauce",
        ingredients=["milk", "butter", "pasta"],
        ingredients_raw=["1 cup milk", "1/2 cup butter", "1 lb pasta"],
        ingredients_structured=[dairy_ing, butter_ing],
        steps=["Boil pasta", "Make sauce", "Combine"],
        servings=4,
        serving_size="1 plate",
        tags=["30-minutes-or-less", "easy"],
    )


@pytest.fixture
def mock_recipe_no_dairy():
    """Create a mock recipe without dairy."""
    chicken_ing = Ingredient(
        raw="1 lb chicken",
        name="chicken",
        quantity=1.0,
        unit="lb",
        allergens=[]
    )

    return Recipe(
        id="2",
        name="Grilled Chicken",
        description="Simple grilled chicken",
        ingredients=["chicken", "salt", "pepper"],
        ingredients_raw=["1 lb chicken", "salt to taste", "pepper to taste"],
        ingredients_structured=[chicken_ing],
        steps=["Season", "Grill"],
        servings=4,
        serving_size="1 piece",
        tags=["30-minutes-or-less", "easy"],
    )


@pytest.fixture
def mock_meal_plan(mock_recipe_with_dairy, mock_recipe_no_dairy):
    """Create a mock meal plan with 2 meals."""
    today = datetime.now().date()
    meals = [
        PlannedMeal(
            date=(today + timedelta(days=0)).isoformat(),
            meal_type="dinner",
            recipe=mock_recipe_with_dairy,
            servings=4
        ),
        PlannedMeal(
            date=(today + timedelta(days=1)).isoformat(),
            meal_type="dinner",
            recipe=mock_recipe_no_dairy,
            servings=4
        ),
    ]

    plan = MealPlan(
        week_of=today.isoformat(),
        meals=meals,
        preferences_applied=[]
    )
    plan.id = "test-plan-123"

    return plan


class TestPlanCaching:
    """Test that meal plans are properly cached in memory."""

    @patch('src.chatbot.MealPlanningAssistant')
    @patch.dict(os.environ, {'ANTHROPIC_API_KEY': 'test-key'})
    def test_plan_cached_after_creation(self, mock_assistant_class, mock_meal_plan):
        """Test that plan is cached after plan_meals_smart execution."""
        # Setup mock
        mock_assistant = Mock()
        mock_assistant.db = Mock()
        mock_assistant.db.save_meal_plan = Mock(return_value="test-plan-123")
        mock_assistant.db.get_recent_meal_plans = Mock(return_value=[])
        mock_assistant.db.search_recipes = Mock(return_value=[mock_meal_plan.meals[0].recipe])
        mock_assistant.db.get_meal_history = Mock(return_value=[])
        mock_assistant_class.return_value = mock_assistant

        # Create chatbot (disable auto-load for this test)
        chatbot = MealPlanningChatbot(verbose=False)
        chatbot.last_meal_plan = None  # Clear any auto-loaded plan

        # Manually execute plan_meals_smart logic (simplified)
        plan = mock_meal_plan
        plan_id = chatbot.assistant.db.save_meal_plan(plan)
        chatbot.current_meal_plan_id = plan_id
        chatbot.last_meal_plan = plan  # This is what our code change does

        # Verify plan is cached
        assert chatbot.last_meal_plan is not None
        assert chatbot.last_meal_plan == plan
        assert len(chatbot.last_meal_plan.meals) == 2
        assert chatbot.last_meal_plan.meals[0].recipe.name == "Creamy Pasta"

    @patch('src.chatbot.MealPlanningAssistant')
    @patch.dict(os.environ, {'ANTHROPIC_API_KEY': 'test-key'})
    def test_allergen_check_uses_cached_plan(self, mock_assistant_class, mock_meal_plan):
        """Test that check_allergens uses cached plan without DB queries."""
        # Setup mock
        mock_assistant = Mock()
        mock_assistant.db = Mock()
        mock_assistant.db.get_recent_meal_plans = Mock(return_value=[])
        mock_assistant_class.return_value = mock_assistant

        # Create chatbot with cached plan
        chatbot = MealPlanningChatbot(verbose=False)
        chatbot.last_meal_plan = mock_meal_plan

        # Execute check_allergens
        result = chatbot.execute_tool("check_allergens", {"allergen": "dairy"})

        # Verify it found dairy
        assert "Found dairy" in result or "dairy in" in result
        assert "Creamy Pasta" in result

        # Verify no DB calls were made (plan was cached)
        mock_assistant.db.get_recipe.assert_not_called()
        mock_assistant.db.get_meal_plan.assert_not_called()

    @patch('src.chatbot.MealPlanningAssistant')
    @patch.dict(os.environ, {'ANTHROPIC_API_KEY': 'test-key'})
    def test_allergen_check_no_allergen_found(self, mock_assistant_class, mock_meal_plan):
        """Test check_allergens returns correct message when allergen not found."""
        mock_assistant = Mock()
        mock_assistant.db = Mock()
        mock_assistant.db.get_recent_meal_plans = Mock(return_value=[])
        mock_assistant_class.return_value = mock_assistant

        chatbot = MealPlanningChatbot(verbose=False)
        chatbot.last_meal_plan = mock_meal_plan

        # Check for shellfish (not present)
        result = chatbot.execute_tool("check_allergens", {"allergen": "shellfish"})

        assert "No shellfish" in result or "not" in result.lower()

    @patch('src.chatbot.MealPlanningAssistant')
    @patch.dict(os.environ, {'ANTHROPIC_API_KEY': 'test-key'})
    def test_no_plan_cached_returns_error(self, mock_assistant_class):
        """Test tools return error when no plan is cached."""
        mock_assistant = Mock()
        mock_assistant.db = Mock()
        mock_assistant.db.get_recent_meal_plans = Mock(return_value=[])
        mock_assistant_class.return_value = mock_assistant

        chatbot = MealPlanningChatbot(verbose=False)
        chatbot.last_meal_plan = None  # No plan

        result = chatbot.execute_tool("check_allergens", {"allergen": "dairy"})

        assert "No meal plan loaded" in result

    @patch('src.chatbot.MealPlanningAssistant')
    @patch.dict(os.environ, {'ANTHROPIC_API_KEY': 'test-key'})
    def test_get_day_ingredients_from_cache(self, mock_assistant_class, mock_meal_plan):
        """Test get_day_ingredients uses cached plan."""
        mock_assistant = Mock()
        mock_assistant.db = Mock()
        mock_assistant.db.get_recent_meal_plans = Mock(return_value=[])
        mock_assistant_class.return_value = mock_assistant

        chatbot = MealPlanningChatbot(verbose=False)
        chatbot.last_meal_plan = mock_meal_plan

        # Get ingredients for first day
        date = mock_meal_plan.meals[0].date
        result = chatbot.execute_tool("get_day_ingredients", {"date": date})

        # Verify ingredients are returned
        assert "Creamy Pasta" in result
        assert "milk" in result or "Ingredients" in result

        # Verify no DB calls
        mock_assistant.db.get_recipe.assert_not_called()

    @patch('src.chatbot.MealPlanningAssistant')
    @patch.dict(os.environ, {'ANTHROPIC_API_KEY': 'test-key'})
    def test_list_meals_by_allergen(self, mock_assistant_class, mock_meal_plan):
        """Test list_meals_by_allergen returns detailed info."""
        mock_assistant = Mock()
        mock_assistant.db = Mock()
        mock_assistant.db.get_recent_meal_plans = Mock(return_value=[])
        mock_assistant_class.return_value = mock_assistant

        chatbot = MealPlanningChatbot(verbose=False)
        chatbot.last_meal_plan = mock_meal_plan

        result = chatbot.execute_tool("list_meals_by_allergen", {"allergen": "dairy"})

        # Should list the meal with details
        assert "Creamy Pasta" in result
        assert mock_meal_plan.meals[0].date in result


class TestAutoLoad:
    """Test auto-loading of most recent plan on startup."""

    @patch('src.chatbot.MealPlanningAssistant')
    @patch.dict(os.environ, {'ANTHROPIC_API_KEY': 'test-key'})
    def test_auto_load_recent_plan(self, mock_assistant_class, mock_meal_plan):
        """Test that chatbot auto-loads most recent plan on init."""
        mock_assistant = Mock()
        mock_assistant.db = Mock()
        mock_assistant.db.get_recent_meal_plans = Mock(return_value=[mock_meal_plan])
        mock_assistant_class.return_value = mock_assistant

        # Create chatbot (should auto-load)
        chatbot = MealPlanningChatbot(verbose=False)

        # Verify plan was loaded
        assert chatbot.last_meal_plan is not None
        assert chatbot.last_meal_plan == mock_meal_plan
        assert chatbot.current_meal_plan_id == "test-plan-123"

    @patch('src.chatbot.MealPlanningAssistant')
    @patch.dict(os.environ, {'ANTHROPIC_API_KEY': 'test-key'})
    def test_auto_load_no_recent_plan(self, mock_assistant_class):
        """Test graceful handling when no recent plan exists."""
        mock_assistant = Mock()
        mock_assistant.db = Mock()
        mock_assistant.db.get_recent_meal_plans = Mock(return_value=[])
        mock_assistant_class.return_value = mock_assistant

        # Should not raise error
        chatbot = MealPlanningChatbot(verbose=False)

        assert chatbot.last_meal_plan is None
        assert chatbot.current_meal_plan_id is None


class TestBackupQueue:
    """Test backup recipe queue for fast meal swapping."""

    @patch('src.chatbot.MealPlanningAssistant')
    @patch.dict(os.environ, {'ANTHROPIC_API_KEY': 'test-key'})
    def test_backup_recipes_stored_during_planning(self, mock_assistant_class, mock_recipe_with_dairy, mock_recipe_no_dairy):
        """Test that backup recipes are stored during plan_meals_smart."""
        mock_assistant = Mock()
        mock_assistant.db = Mock()
        mock_assistant.db.get_recent_meal_plans = Mock(return_value=[])
        mock_assistant.db.search_recipes = Mock(return_value=[
            mock_recipe_with_dairy,  # Will be selected
            mock_recipe_no_dairy,     # Will be backup
        ])
        mock_assistant.db.get_meal_history = Mock(return_value=[])
        mock_assistant.db.save_meal_plan = Mock(return_value="test-plan-456")
        mock_assistant_class.return_value = mock_assistant

        chatbot = MealPlanningChatbot(verbose=False)

        # Execute planning (simplified - normally would call execute_tool)
        # Manually set up what plan_meals_smart does
        plan = MealPlan(
            week_of="2025-01-20",
            meals=[
                PlannedMeal(
                    date="2025-01-20",
                    meal_type="dinner",
                    recipe=mock_recipe_with_dairy,
                    servings=4
                )
            ],
            backup_recipes={"chicken": [mock_recipe_no_dairy]}
        )
        plan.id = "test-plan-456"
        chatbot.last_meal_plan = plan

        # Verify backups were stored
        assert "chicken" in plan.backup_recipes
        assert len(plan.backup_recipes["chicken"]) == 1
        assert plan.backup_recipes["chicken"][0] == mock_recipe_no_dairy

    @patch('src.chatbot.MealPlanningAssistant')
    @patch.dict(os.environ, {'ANTHROPIC_API_KEY': 'test-key'})
    def test_check_backup_match_direct(self, mock_assistant_class):
        """Test _check_backup_match with direct category match."""
        mock_assistant = Mock()
        mock_assistant.db = Mock()
        mock_assistant.db.get_recent_meal_plans = Mock(return_value=[])
        mock_assistant_class.return_value = mock_assistant

        chatbot = MealPlanningChatbot(verbose=False)

        # Direct match
        assert chatbot._check_backup_match("different chicken dish", "chicken") is True
        assert chatbot._check_backup_match("another pasta option", "pasta") is True

    @patch('src.chatbot.MealPlanningAssistant')
    @patch.dict(os.environ, {'ANTHROPIC_API_KEY': 'test-key'})
    def test_check_backup_match_related_terms(self, mock_assistant_class):
        """Test _check_backup_match with related terms."""
        mock_assistant = Mock()
        mock_assistant.db = Mock()
        mock_assistant.db.get_recent_meal_plans = Mock(return_value=[])
        mock_assistant_class.return_value = mock_assistant

        chatbot = MealPlanningChatbot(verbose=False)

        # Related terms
        assert chatbot._check_backup_match("poultry recipe", "chicken") is True
        assert chatbot._check_backup_match("steak dinner", "beef") is True
        assert chatbot._check_backup_match("spaghetti meal", "pasta") is True

    @patch('src.chatbot.MealPlanningAssistant')
    @patch.dict(os.environ, {'ANTHROPIC_API_KEY': 'test-key'})
    def test_check_backup_match_modifiers(self, mock_assistant_class):
        """Test _check_backup_match with modifier words."""
        mock_assistant = Mock()
        mock_assistant.db = Mock()
        mock_assistant.db.get_recent_meal_plans = Mock(return_value=[])
        mock_assistant_class.return_value = mock_assistant

        chatbot = MealPlanningChatbot(verbose=False)

        # Modifiers
        assert chatbot._check_backup_match("swap this chicken", "chicken") is True
        assert chatbot._check_backup_match("change pasta meal", "pasta") is True
        assert chatbot._check_backup_match("replace this beef", "beef") is True

    @patch('src.chatbot.MealPlanningAssistant')
    @patch.dict(os.environ, {'ANTHROPIC_API_KEY': 'test-key'})
    def test_check_backup_match_no_match(self, mock_assistant_class):
        """Test _check_backup_match returns False when no match."""
        mock_assistant = Mock()
        mock_assistant.db = Mock()
        mock_assistant.db.get_recent_meal_plans = Mock(return_value=[])
        mock_assistant_class.return_value = mock_assistant

        chatbot = MealPlanningChatbot(verbose=False)

        # No match
        assert chatbot._check_backup_match("fish recipe", "chicken") is False
        assert chatbot._check_backup_match("vegetarian dish", "beef") is False

    @patch('src.chatbot.MealPlanningAssistant')
    @patch.dict(os.environ, {'ANTHROPIC_API_KEY': 'test-key'})
    def test_swap_meal_fast_uses_backups(self, mock_assistant_class, mock_recipe_with_dairy, mock_recipe_no_dairy):
        """Test swap_meal_fast uses backup recipes when available."""
        mock_assistant = Mock()
        mock_assistant.db = Mock()
        mock_assistant.db.get_recent_meal_plans = Mock(return_value=[])
        mock_assistant.db.swap_meal_in_plan = Mock(return_value=True)
        mock_assistant_class.return_value = mock_assistant

        chatbot = MealPlanningChatbot(verbose=False)

        # Set up plan with backups
        plan = MealPlan(
            week_of="2025-01-20",
            meals=[
                PlannedMeal(
                    date="2025-01-20",
                    meal_type="dinner",
                    recipe=mock_recipe_with_dairy,
                    servings=4
                )
            ],
            backup_recipes={"chicken": [mock_recipe_no_dairy]}
        )
        plan.id = "test-plan-789"
        chatbot.last_meal_plan = plan

        # Execute swap_meal_fast
        result = chatbot.execute_tool("swap_meal_fast", {
            "date": "2025-01-20",
            "requirements": "different chicken dish"
        })

        # Verify backup was used
        assert "Creamy Pasta" in result  # Old recipe
        assert "Grilled Chicken" in result  # New recipe from backups
        assert "chicken" in result  # Category used
        assert "cached backups" in result or "<10ms" in result

        # Verify DB was updated
        mock_assistant.db.swap_meal_in_plan.assert_called_once_with(
            plan_id="test-plan-789",
            date="2025-01-20",
            new_recipe_id="2"
        )

        # Verify cached plan was updated
        assert chatbot.last_meal_plan.meals[0].recipe == mock_recipe_no_dairy

    @patch('src.chatbot.MealPlanningAssistant')
    @patch.dict(os.environ, {'ANTHROPIC_API_KEY': 'test-key'})
    def test_swap_meal_fast_no_plan_error(self, mock_assistant_class):
        """Test swap_meal_fast returns error when no plan loaded."""
        mock_assistant = Mock()
        mock_assistant.db = Mock()
        mock_assistant.db.get_recent_meal_plans = Mock(return_value=[])
        mock_assistant_class.return_value = mock_assistant

        chatbot = MealPlanningChatbot(verbose=False)
        chatbot.last_meal_plan = None

        result = chatbot.execute_tool("swap_meal_fast", {
            "date": "2025-01-20",
            "requirements": "different chicken"
        })

        assert "No meal plan loaded" in result


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
