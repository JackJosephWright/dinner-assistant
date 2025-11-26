"""
Integration tests for Phase 4: Background shopping regeneration updates snapshot.

Tests that regenerate_shopping_list_async updates snapshot['grocery_list']
after generating the shopping list.
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


def test_snapshot_updated_after_grocery_list_generation(db):
    """
    Test that snapshot is updated when grocery list is generated.

    This simulates what happens in the background thread.
    """
    # Create initial snapshot without grocery list
    snapshot = {
        'id': 'mp_test_phase4',
        'user_id': 1,
        'week_of': '2025-11-24',
        'version': 1,
        'planned_meals': [
            {
                'date': '2025-11-24',
                'meal_type': 'dinner',
                'recipe': {'id': '123', 'name': 'Test Recipe'},
                'servings': 4,
            }
        ],
        'grocery_list': None,  # Initially empty
    }

    snapshot_id = db.save_snapshot(snapshot)

    # Verify initial state
    loaded = db.get_snapshot(snapshot_id)
    assert loaded['grocery_list'] is None

    # Simulate grocery list generation
    grocery_list = GroceryList(
        id='gl_test',
        week_of='2025-11-24',
        items=[
            GroceryItem(
                name='chicken',
                quantity='2 lbs',
                category='meat',
                recipe_sources=['Test Recipe'],
            )
        ],
        extra_items=[],
    )

    # Simulate what the background thread does
    snapshot['grocery_list'] = grocery_list.to_dict()
    db.save_snapshot(snapshot)

    # Verify snapshot was updated
    updated = db.get_snapshot(snapshot_id)
    assert updated['grocery_list'] is not None
    assert len(updated['grocery_list']['items']) == 1
    assert updated['grocery_list']['items'][0]['name'] == 'chicken'
    assert updated['grocery_list']['items'][0]['quantity'] == '2 lbs'


def test_snapshot_preserves_grocery_list_on_update():
    """Test that snapshot UPDATE preserves grocery_list when re-saved."""
    from src.web.app import assistant

    # Create snapshot with grocery list
    snapshot = {
        'user_id': 1,
        'week_of': '2025-11-24',
        'version': 1,
        'planned_meals': [],
        'grocery_list': {
            'items': [{'name': 'milk', 'quantity': '1 gallon'}],
            'store_sections': {},
            'extra_items': [],
        }
    }

    snapshot_id = assistant.db.save_snapshot(snapshot)

    # Load and verify
    loaded = assistant.db.get_snapshot(snapshot_id)
    assert loaded['grocery_list'] is not None
    assert loaded['grocery_list']['items'][0]['name'] == 'milk'

    # Update snapshot (simulate adding a meal)
    loaded['planned_meals'].append({
        'date': '2025-11-25',
        'meal_type': 'dinner',
        'recipe': {'id': '456', 'name': 'New Recipe'},
    })
    assistant.db.save_snapshot(loaded)

    # Verify grocery_list still exists
    reloaded = assistant.db.get_snapshot(snapshot_id)
    assert reloaded['grocery_list'] is not None
    assert reloaded['grocery_list']['items'][0]['name'] == 'milk'
    assert len(reloaded['planned_meals']) == 1


def test_snapshot_grocery_list_structure_matches_legacy(db):
    """Verify snapshot grocery_list has same structure as GroceryList.to_dict()."""
    # Create a GroceryList
    grocery_list = GroceryList(
        id='gl_structure_test',
        week_of='2025-11-24',
        items=[
            GroceryItem(
                name='eggs',
                quantity='1 dozen',
                category='dairy',
                recipe_sources=['Recipe A'],
                notes='Free range',
            )
        ],
        extra_items=[
            GroceryItem(
                name='coffee',
                quantity='1 lb',
                category='beverages',
                recipe_sources=['User request'],
            )
        ],
        estimated_total=15.50,
    )

    legacy_dict = grocery_list.to_dict()

    # Create snapshot with same grocery list
    snapshot = {
        'user_id': 1,
        'week_of': '2025-11-24',
        'version': 1,
        'planned_meals': [],
        'grocery_list': legacy_dict,
    }

    snapshot_id = db.save_snapshot(snapshot)
    loaded = db.get_snapshot(snapshot_id)

    # Verify structure matches
    assert 'items' in loaded['grocery_list']
    assert 'store_sections' in loaded['grocery_list']
    assert 'extra_items' in loaded['grocery_list']

    # Verify items
    assert len(loaded['grocery_list']['items']) == 1
    item = loaded['grocery_list']['items'][0]
    assert item['name'] == 'eggs'
    assert item['quantity'] == '1 dozen'
    assert item['category'] == 'dairy'
    assert item['recipe_sources'] == ['Recipe A']
    assert item['notes'] == 'Free range'

    # Verify extra_items
    assert len(loaded['grocery_list']['extra_items']) == 1
    extra = loaded['grocery_list']['extra_items'][0]
    assert extra['name'] == 'coffee'


def test_background_shopping_logic_simulation():
    """
    Simulate the Phase 4 background thread logic without actual LLM calls.

    This tests the pattern used in regenerate_shopping_list_async.
    """
    from src.web.app import assistant

    # Step 1: Create snapshot (as done in Phase 2)
    snapshot = {
        'id': 'mp_sim_test',
        'user_id': 1,
        'week_of': '2025-11-24',
        'version': 1,
        'planned_meals': [
            {
                'date': '2025-11-24',
                'meal_type': 'dinner',
                'recipe': {
                    'id': '789',
                    'name': 'Pasta',
                    'ingredients': ['pasta', 'tomato sauce'],
                },
                'servings': 4,
            }
        ],
        'grocery_list': None,
    }

    snapshot_id = assistant.db.save_snapshot(snapshot)

    # Step 2: Simulate shopping list generation
    # (In real code, this would be assistant.create_shopping_list(meal_plan_id))
    grocery_list = GroceryList(
        id='gl_sim_test',
        week_of='2025-11-24',
        items=[
            GroceryItem(
                name='pasta',
                quantity='1 lb',
                category='pasta',
                recipe_sources=['Pasta'],
            ),
            GroceryItem(
                name='tomato sauce',
                quantity='1 jar',
                category='canned goods',
                recipe_sources=['Pasta'],
            ),
        ],
        extra_items=[],
    )

    # Step 3: Update snapshot with grocery list (Phase 4 logic)
    snapshot = assistant.db.get_snapshot(snapshot_id)
    snapshot['grocery_list'] = grocery_list.to_dict()
    assistant.db.save_snapshot(snapshot)

    # Step 4: Verify snapshot was updated
    final_snapshot = assistant.db.get_snapshot(snapshot_id)
    assert final_snapshot['grocery_list'] is not None
    assert len(final_snapshot['grocery_list']['items']) == 2
    assert final_snapshot['grocery_list']['items'][0]['name'] == 'pasta'
    assert final_snapshot['grocery_list']['items'][1]['name'] == 'tomato sauce'

    # Verify both planned_meals and grocery_list coexist
    assert len(final_snapshot['planned_meals']) == 1
    assert final_snapshot['planned_meals'][0]['recipe']['name'] == 'Pasta'


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
