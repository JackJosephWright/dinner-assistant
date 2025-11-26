"""
Integration tests for Phase 5: Plan & Cook tabs read from snapshot.

Tests that /plan and /cook routes load from snapshot when available,
with fallback to legacy meal_plans table.
"""

import pytest
import sys
import os

# Add project root to path
project_root = os.path.join(os.path.dirname(__file__), '..', '..')
sys.path.insert(0, project_root)
sys.path.insert(0, os.path.join(project_root, 'src'))

from data.database import DatabaseInterface


def test_plan_loads_from_snapshot_when_available(client):
    """Test that /plan loads meal plan from snapshot when it exists."""
    # Login
    client.post('/login', data={'username': 'admin', 'password': 'password'})

    # Use the app's actual database interface
    from src.web.app import assistant

    # Create a snapshot with planned meals
    snapshot = {
        'user_id': 1,
        'week_of': '2025-11-24',
        'version': 1,
        'planned_meals': [
            {
                'date': '2025-11-24',
                'meal_type': 'dinner',
                'recipe': {
                    'id': '123',
                    'name': 'Snapshot Test Recipe',
                    'description': 'A test recipe from snapshot',
                    'estimated_time': 30,
                    'cuisine': 'American',
                    'difficulty': 'easy',
                },
                'servings': 4,
            }
        ],
        'grocery_list': None,
    }

    snapshot_id = assistant.db.save_snapshot(snapshot)

    # Set snapshot_id in session
    with client.session_transaction() as sess:
        sess['snapshot_id'] = snapshot_id
        sess['user_id'] = 1

    # Load /plan page
    response = client.get('/plan')

    assert response.status_code == 200
    # Check that the page contains the recipe from snapshot
    assert b'Snapshot Test Recipe' in response.data


def test_cook_loads_from_snapshot_when_available(client):
    """Test that /cook loads meal plan from snapshot when it exists."""
    # Login
    client.post('/login', data={'username': 'admin', 'password': 'password'})

    # Use the app's actual database interface
    from src.web.app import assistant

    # Create a snapshot with planned meals
    snapshot = {
        'user_id': 1,
        'week_of': '2025-11-24',
        'version': 1,
        'planned_meals': [
            {
                'date': '2025-11-24',
                'meal_type': 'dinner',
                'recipe': {
                    'id': '456',
                    'name': 'Snapshot Cook Recipe',
                    'description': 'A test recipe for cooking from snapshot',
                    'estimated_time': 45,
                    'cuisine': 'Italian',
                    'difficulty': 'medium',
                },
                'servings': 2,
            }
        ],
        'grocery_list': None,
    }

    snapshot_id = assistant.db.save_snapshot(snapshot)

    # Set snapshot_id in session
    with client.session_transaction() as sess:
        sess['snapshot_id'] = snapshot_id
        sess['user_id'] = 1

    # Load /cook page
    response = client.get('/cook')

    assert response.status_code == 200
    # Check that the page contains the recipe from snapshot
    assert b'Snapshot Cook Recipe' in response.data


def test_plan_falls_back_to_legacy_when_no_snapshot_id(client):
    """Test that /plan uses legacy path when snapshot_id not in session."""
    # Login
    client.post('/login', data={'username': 'admin', 'password': 'password'})

    # No snapshot_id in session - should use legacy path
    with client.session_transaction() as sess:
        sess['meal_plan_id'] = 'some_plan_id'
        # No snapshot_id set

    # Load /plan page
    response = client.get('/plan')

    # Should not crash, use legacy fallback
    assert response.status_code == 200


def test_cook_falls_back_to_legacy_when_no_snapshot_id(client):
    """Test that /cook uses legacy path when snapshot_id not in session."""
    # Login
    client.post('/login', data={'username': 'admin', 'password': 'password'})

    # No snapshot_id in session - should use legacy path
    with client.session_transaction() as sess:
        sess['meal_plan_id'] = 'some_plan_id'
        # No snapshot_id set

    # Load /cook page
    response = client.get('/cook')

    # Should not crash, use legacy fallback
    assert response.status_code == 200


def test_plan_falls_back_when_snapshot_planned_meals_none(client, db):
    """Test that /plan uses legacy path when snapshot.planned_meals is None."""
    # Login
    client.post('/login', data={'username': 'admin', 'password': 'password'})

    # Create a snapshot WITHOUT planned_meals (edge case)
    snapshot = {
        'id': 'mp_test_empty',
        'user_id': 1,
        'week_of': '2025-11-24',
        'version': 1,
        'planned_meals': None,  # No meals yet
        'grocery_list': None,
    }

    snapshot_id = db.save_snapshot(snapshot)

    # Set snapshot_id in session
    with client.session_transaction() as sess:
        sess['snapshot_id'] = snapshot_id
        sess['meal_plan_id'] = 'mp_test_empty'
        sess['user_id'] = 1

    # Load /plan page (should fallback to legacy)
    response = client.get('/plan')

    # Should not crash, fallback gracefully
    assert response.status_code == 200


def test_cook_falls_back_when_snapshot_planned_meals_none(client, db):
    """Test that /cook uses legacy path when snapshot.planned_meals is None."""
    # Login
    client.post('/login', data={'username': 'admin', 'password': 'password'})

    # Create a snapshot WITHOUT planned_meals (edge case)
    snapshot = {
        'id': 'mp_test_cook_empty',
        'user_id': 1,
        'week_of': '2025-11-24',
        'version': 1,
        'planned_meals': None,  # No meals yet
        'grocery_list': None,
    }

    snapshot_id = db.save_snapshot(snapshot)

    # Set snapshot_id in session
    with client.session_transaction() as sess:
        sess['snapshot_id'] = snapshot_id
        sess['meal_plan_id'] = 'mp_test_cook_empty'
        sess['user_id'] = 1

    # Load /cook page (should fallback to legacy)
    response = client.get('/cook')

    # Should not crash, fallback gracefully
    assert response.status_code == 200


def test_plan_snapshot_data_structure_matches_frontend(db):
    """Verify that snapshot planned_meals structure works with frontend."""
    from data.models import MealPlan, PlannedMeal, Recipe

    # Create a MealPlan using the models
    recipe = Recipe(
        id='test_recipe_123',
        name='Test Recipe',
        description='A test recipe',
        ingredients=['eggs', 'milk'],
        ingredients_raw=['2 eggs', '1 cup milk'],
        steps=['Mix ingredients', 'Cook'],
        servings=2,
        serving_size='1 serving',
        tags=['breakfast', 'easy'],
        estimated_time=15,
        cuisine='American',
        difficulty='easy',
    )

    planned_meal = PlannedMeal(
        date='2025-11-24',
        meal_type='breakfast',
        recipe=recipe,
        servings=2,
    )

    meal_plan = MealPlan(
        id='mp_structure_test',
        week_of='2025-11-24',
        meals=[planned_meal],
    )

    # Create snapshot from meal plan (user_id added at snapshot level)
    snapshot = {
        'id': meal_plan.id,
        'user_id': 1,  # Added at snapshot level, not in MealPlan model
        'week_of': meal_plan.week_of,
        'version': 1,
        'planned_meals': [m.to_dict() for m in meal_plan.meals],
        'grocery_list': None,
    }

    snapshot_id = db.save_snapshot(snapshot)
    loaded = db.get_snapshot(snapshot_id)

    # Verify structure is preserved
    assert len(loaded['planned_meals']) == 1
    meal = loaded['planned_meals'][0]
    assert meal['date'] == '2025-11-24'
    assert meal['meal_type'] == 'breakfast'
    assert meal['recipe']['name'] == 'Test Recipe'
    assert meal['recipe']['id'] == 'test_recipe_123'
    assert meal['recipe']['description'] == 'A test recipe'
    assert meal['recipe']['estimated_time'] == 15
    assert meal['recipe']['cuisine'] == 'American'
    assert meal['recipe']['difficulty'] == 'easy'


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
