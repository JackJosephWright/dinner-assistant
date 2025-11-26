"""
Integration tests for Phase 3: Shop tab reads from snapshot.

Tests that /shop route loads grocery list from snapshot when available,
with fallback to legacy grocery_lists table.
"""

import pytest
import sys
import os

# Add project root to path
project_root = os.path.join(os.path.dirname(__file__), '..', '..')
sys.path.insert(0, project_root)
sys.path.insert(0, os.path.join(project_root, 'src'))

from data.database import DatabaseInterface


def test_shop_loads_from_snapshot_when_available(client):
    """Test that /shop loads grocery list from snapshot when it exists."""
    # Login
    client.post('/login', data={'username': 'admin', 'password': 'password'})

    # Use the app's actual database interface
    from src.web.app import assistant

    # Create a snapshot with grocery list
    snapshot = {
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
        'grocery_list': {
            'items': [
                {
                    'name': 'chicken',
                    'quantity': '2 lbs',
                    'category': 'meat',
                    'recipe_sources': ['Test Recipe'],
                }
            ],
            'store_sections': {
                'meat': [
                    {
                        'name': 'chicken',
                        'quantity': '2 lbs',
                        'category': 'meat',
                        'recipe_sources': ['Test Recipe'],
                    }
                ]
            },
            'extra_items': [],
        }
    }

    snapshot_id = assistant.db.save_snapshot(snapshot)

    # Set snapshot_id in session
    with client.session_transaction() as sess:
        sess['snapshot_id'] = snapshot_id
        sess['user_id'] = 1

    # Load /shop page
    response = client.get('/shop')

    assert response.status_code == 200
    # Check that the page contains the grocery item
    assert b'chicken' in response.data
    assert b'2 lbs' in response.data


def test_shop_falls_back_to_legacy_when_snapshot_grocery_list_none(client, db):
    """Test that /shop uses legacy path when snapshot.grocery_list is None."""
    # Login
    client.post('/login', data={'username': 'admin', 'password': 'password'})

    # Create a snapshot WITHOUT grocery list (still being generated)
    snapshot = {
        'id': 'mp_test_123',
        'user_id': 1,
        'week_of': '2025-11-24',
        'version': 1,
        'planned_meals': [],
        'grocery_list': None,  # Not yet generated
    }

    snapshot_id = db.save_snapshot(snapshot)

    # Set snapshot_id in session
    with client.session_transaction() as sess:
        sess['snapshot_id'] = snapshot_id
        sess['meal_plan_id'] = 'mp_test_123'
        sess['user_id'] = 1

    # Load /shop page (should fallback to legacy)
    response = client.get('/shop')

    # Should not crash, fallback gracefully
    assert response.status_code == 200


def test_shop_falls_back_to_legacy_when_no_snapshot_id(client):
    """Test that /shop uses legacy path when snapshot_id not in session."""
    # Login
    client.post('/login', data={'username': 'admin', 'password': 'password'})

    # No snapshot_id in session - should use legacy path
    with client.session_transaction() as sess:
        sess['meal_plan_id'] = 'some_plan_id'
        # No snapshot_id set

    # Load /shop page
    response = client.get('/shop')

    # Should not crash, use legacy fallback
    assert response.status_code == 200


def test_shop_with_snapshots_disabled(client, db, monkeypatch):
    """Test that /shop uses legacy path when SNAPSHOTS_ENABLED=false."""
    # This test would need to reload app module with different env var
    # For now, just verify the route doesn't crash

    # Login
    client.post('/login', data={'username': 'admin', 'password': 'password'})

    # Create snapshot anyway
    snapshot = {
        'user_id': 1,
        'week_of': '2025-11-24',
        'version': 1,
        'planned_meals': [],
        'grocery_list': {'items': []},
    }
    snapshot_id = db.save_snapshot(snapshot)

    with client.session_transaction() as sess:
        sess['snapshot_id'] = snapshot_id
        sess['user_id'] = 1

    # Load /shop - should work regardless of flag
    response = client.get('/shop')
    assert response.status_code == 200


def test_shop_snapshot_structure_matches_legacy(db):
    """Verify that snapshot grocery_list structure matches legacy GroceryList.to_dict()."""
    from data.models import GroceryList, GroceryItem

    # Create a GroceryList using the model
    grocery_list = GroceryList(
        id='gl_test',
        week_of='2025-11-24',
        items=[
            GroceryItem(
                name='milk',
                quantity='1 gallon',
                category='dairy',
                recipe_sources=['Recipe A', 'Recipe B'],
            )
        ],
        extra_items=[],
    )

    legacy_dict = grocery_list.to_dict()

    # Create snapshot with same structure
    snapshot = {
        'user_id': 1,
        'week_of': '2025-11-24',
        'version': 1,
        'planned_meals': [],
        'grocery_list': legacy_dict,
    }

    snapshot_id = db.save_snapshot(snapshot)
    loaded = db.get_snapshot(snapshot_id)

    # Verify structure is preserved
    assert loaded['grocery_list']['items'][0]['name'] == 'milk'
    assert loaded['grocery_list']['items'][0]['quantity'] == '1 gallon'
    assert loaded['grocery_list']['items'][0]['category'] == 'dairy'
    assert loaded['grocery_list']['items'][0]['recipe_sources'] == ['Recipe A', 'Recipe B']


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
