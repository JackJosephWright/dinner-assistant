"""
Integration tests for Phase 6: Swap-meal edits snapshot.

Tests that /api/swap-meal updates snapshot's planned_meals and
background shopping regeneration updates snapshot's grocery_list.
"""

import pytest
import sys
import os

# Add project root to path
project_root = os.path.join(os.path.dirname(__file__), '..', '..')
sys.path.insert(0, project_root)
sys.path.insert(0, os.path.join(project_root, 'src'))

from data.database import DatabaseInterface
from data.models import GroceryList, GroceryItem


def test_snapshot_updated_after_meal_swap(db):
    """
    Test that snapshot is updated when a meal is swapped.

    Simulates the swap_meal pattern without actual LLM calls.
    """
    # Create initial snapshot with 2 meals
    snapshot = {
        'id': 'mp_swap_test',
        'user_id': 1,
        'week_of': '2025-11-24',
        'version': 1,
        'planned_meals': [
            {
                'date': '2025-11-24',
                'meal_type': 'dinner',
                'recipe': {'id': 'old_recipe_123', 'name': 'Old Recipe'},
                'servings': 4,
            },
            {
                'date': '2025-11-25',
                'meal_type': 'dinner',
                'recipe': {'id': '456', 'name': 'Keep This'},
                'servings': 4,
            },
        ],
        'grocery_list': None,
    }

    snapshot_id = db.save_snapshot(snapshot)

    # Verify initial state
    loaded = db.get_snapshot(snapshot_id)
    assert loaded['planned_meals'][0]['recipe']['id'] == 'old_recipe_123'

    # Simulate swap: Replace meal on 2025-11-24
    snapshot['planned_meals'][0] = {
        'date': '2025-11-24',
        'meal_type': 'dinner',
        'recipe': {'id': 'new_recipe_789', 'name': 'New Swapped Recipe'},
        'servings': 4,
    }
    db.save_snapshot(snapshot)

    # Verify snapshot was updated
    updated = db.get_snapshot(snapshot_id)
    assert updated['planned_meals'][0]['recipe']['id'] == 'new_recipe_789'
    assert updated['planned_meals'][0]['recipe']['name'] == 'New Swapped Recipe'
    # Second meal should be unchanged
    assert updated['planned_meals'][1]['recipe']['id'] == '456'
    assert updated['planned_meals'][1]['recipe']['name'] == 'Keep This'


def test_swap_preserves_other_meals():
    """Test that swapping one meal doesn't affect other meals in the snapshot."""
    from src.web.app import assistant

    # Create snapshot with 3 meals
    snapshot = {
        'user_id': 1,
        'week_of': '2025-11-24',
        'version': 1,
        'planned_meals': [
            {
                'date': '2025-11-24',
                'meal_type': 'dinner',
                'recipe': {'id': 'meal_1', 'name': 'Meal 1'},
                'servings': 2,
            },
            {
                'date': '2025-11-25',
                'meal_type': 'dinner',
                'recipe': {'id': 'meal_2', 'name': 'Meal 2'},
                'servings': 2,
            },
            {
                'date': '2025-11-26',
                'meal_type': 'dinner',
                'recipe': {'id': 'meal_3', 'name': 'Meal 3'},
                'servings': 2,
            },
        ],
        'grocery_list': None,
    }

    snapshot_id = assistant.db.save_snapshot(snapshot)

    # Swap only the middle meal
    snapshot = assistant.db.get_snapshot(snapshot_id)
    snapshot['planned_meals'][1] = {
        'date': '2025-11-25',
        'meal_type': 'dinner',
        'recipe': {'id': 'swapped_meal', 'name': 'Swapped Meal'},
        'servings': 2,
    }
    assistant.db.save_snapshot(snapshot)

    # Verify only middle meal changed
    updated = assistant.db.get_snapshot(snapshot_id)
    assert updated['planned_meals'][0]['recipe']['id'] == 'meal_1'
    assert updated['planned_meals'][1]['recipe']['id'] == 'swapped_meal'
    assert updated['planned_meals'][2]['recipe']['id'] == 'meal_3'


def test_swap_and_shopping_regeneration_updates_snapshot():
    """
    Test the full swap workflow: swap meal then regenerate shopping.

    Simulates what happens in /api/swap-meal endpoint.
    """
    from src.web.app import assistant

    # Step 1: Create snapshot (as done in Phase 2)
    snapshot = {
        'id': 'mp_full_workflow',
        'user_id': 1,
        'week_of': '2025-11-24',
        'version': 1,
        'planned_meals': [
            {
                'date': '2025-11-24',
                'meal_type': 'dinner',
                'recipe': {
                    'id': 'original_recipe',
                    'name': 'Original Chicken',
                    'ingredients': ['chicken', 'salt'],
                },
                'servings': 4,
            }
        ],
        'grocery_list': None,
    }

    snapshot_id = assistant.db.save_snapshot(snapshot)

    # Step 2: Simulate swap (replace chicken with fish)
    snapshot = assistant.db.get_snapshot(snapshot_id)
    snapshot['planned_meals'][0] = {
        'date': '2025-11-24',
        'meal_type': 'dinner',
        'recipe': {
            'id': 'swapped_recipe',
            'name': 'Grilled Salmon',
            'ingredients': ['salmon', 'lemon'],
        },
        'servings': 4,
    }
    assistant.db.save_snapshot(snapshot)

    # Verify meal was swapped in snapshot
    updated_snapshot = assistant.db.get_snapshot(snapshot_id)
    assert updated_snapshot['planned_meals'][0]['recipe']['name'] == 'Grilled Salmon'
    assert updated_snapshot['grocery_list'] is None  # Not yet regenerated

    # Step 3: Simulate background shopping regeneration
    grocery_list = GroceryList(
        id='gl_after_swap',
        week_of='2025-11-24',
        items=[
            GroceryItem(
                name='salmon',
                quantity='1 lb',
                category='fish',
                recipe_sources=['Grilled Salmon'],
            ),
            GroceryItem(
                name='lemon',
                quantity='2',
                category='produce',
                recipe_sources=['Grilled Salmon'],
            ),
        ],
        extra_items=[],
    )

    # Update snapshot with new grocery list
    snapshot = assistant.db.get_snapshot(snapshot_id)
    snapshot['grocery_list'] = grocery_list.to_dict()
    assistant.db.save_snapshot(snapshot)

    # Step 4: Verify both meal and shopping list are updated
    final_snapshot = assistant.db.get_snapshot(snapshot_id)
    assert final_snapshot['planned_meals'][0]['recipe']['name'] == 'Grilled Salmon'
    assert final_snapshot['grocery_list'] is not None
    assert len(final_snapshot['grocery_list']['items']) == 2
    assert final_snapshot['grocery_list']['items'][0]['name'] == 'salmon'
    assert final_snapshot['grocery_list']['items'][1]['name'] == 'lemon'


def test_swap_updates_snapshot_timestamp():
    """Test that swapping a meal updates the snapshot's updated_at timestamp."""
    from src.web.app import assistant
    from datetime import datetime
    import time

    snapshot = {
        'user_id': 1,
        'week_of': '2025-11-24',
        'version': 1,
        'planned_meals': [
            {
                'date': '2025-11-24',
                'meal_type': 'dinner',
                'recipe': {'id': 'original', 'name': 'Original'},
                'servings': 2,
            }
        ],
        'grocery_list': None,
    }

    snapshot_id = assistant.db.save_snapshot(snapshot)
    first_snapshot = assistant.db.get_snapshot(snapshot_id)
    first_timestamp = first_snapshot['updated_at']

    # Wait a bit to ensure timestamp changes
    time.sleep(0.1)

    # Swap meal
    snapshot = assistant.db.get_snapshot(snapshot_id)
    snapshot['planned_meals'][0]['recipe'] = {'id': 'swapped', 'name': 'Swapped'}
    snapshot['updated_at'] = datetime.now().isoformat()
    assistant.db.save_snapshot(snapshot)

    # Verify timestamp was updated
    updated_snapshot = assistant.db.get_snapshot(snapshot_id)
    assert updated_snapshot['updated_at'] > first_timestamp


def test_swap_preserves_grocery_list_if_already_exists():
    """Test that swapping a meal doesn't delete existing grocery list."""
    from src.web.app import assistant

    # Create snapshot with both meals and grocery list
    snapshot = {
        'user_id': 1,
        'week_of': '2025-11-24',
        'version': 1,
        'planned_meals': [
            {
                'date': '2025-11-24',
                'meal_type': 'dinner',
                'recipe': {'id': 'original', 'name': 'Original'},
                'servings': 2,
            }
        ],
        'grocery_list': {
            'items': [{'name': 'eggs', 'quantity': '12'}],
            'store_sections': {},
            'extra_items': [],
        },
    }

    snapshot_id = assistant.db.save_snapshot(snapshot)

    # Swap meal
    snapshot = assistant.db.get_snapshot(snapshot_id)
    snapshot['planned_meals'][0]['recipe'] = {'id': 'swapped', 'name': 'Swapped'}
    assistant.db.save_snapshot(snapshot)

    # Verify grocery list still exists (will be regenerated in background)
    updated = assistant.db.get_snapshot(snapshot_id)
    assert updated['grocery_list'] is not None
    assert updated['grocery_list']['items'][0]['name'] == 'eggs'


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
