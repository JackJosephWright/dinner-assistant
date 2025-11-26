"""
Integration tests for Phase 7: Snapshot-only architecture verification.

Tests that the complete snapshot architecture works end-to-end:
- Deprecation warnings on legacy methods
- Snapshot-first reads across all routes
- Complete workflow from plan creation to shopping to cooking
"""

import pytest
import sys
import os
import warnings

# Add project root to path
project_root = os.path.join(os.path.dirname(__file__), '..', '..')
sys.path.insert(0, project_root)
sys.path.insert(0, os.path.join(project_root, 'src'))

from data.database import DatabaseInterface
from data.models import MealPlan, PlannedMeal, Recipe, GroceryList, GroceryItem


def test_legacy_save_meal_plan_shows_deprecation_warning(db):
    """Test that save_meal_plan() shows deprecation warning."""
    meal_plan = MealPlan(
        week_of='2025-11-24',
        meals=[],
    )

    with warnings.catch_warnings(record=True) as w:
        warnings.simplefilter("always")
        db.save_meal_plan(meal_plan)

        # Verify deprecation warning was raised
        assert len(w) == 1
        assert issubclass(w[0].category, DeprecationWarning)
        assert "legacy meal_plans table" in str(w[0].message)
        assert "save_snapshot()" in str(w[0].message)


def test_legacy_save_grocery_list_shows_deprecation_warning(db):
    """Test that save_grocery_list() shows deprecation warning."""
    grocery_list = GroceryList(
        week_of='2025-11-24',
        items=[],
        extra_items=[],
    )

    with warnings.catch_warnings(record=True) as w:
        warnings.simplefilter("always")
        db.save_grocery_list(grocery_list)

        # Verify deprecation warning was raised
        assert len(w) == 1
        assert issubclass(w[0].category, DeprecationWarning)
        assert "legacy grocery_lists table" in str(w[0].message)
        assert "snapshot['grocery_list']" in str(w[0].message)


def test_legacy_swap_meal_shows_deprecation_warning(db):
    """Test that swap_meal_in_plan() shows deprecation warning.

    Note: This test verifies the warning is issued. The actual swap may fail
    due to missing recipes table in test environment, which is expected.
    """
    # First create a meal plan (suppress its warning)
    recipe = Recipe(
        id='test_recipe',
        name='Test Recipe',
        description='A test',
        ingredients=['eggs'],
        ingredients_raw=['2 eggs'],
        steps=['Cook eggs'],
        servings=2,
        serving_size='1 serving',
        tags=['easy'],
    )

    meal_plan = MealPlan(
        id='mp_swap_warning_test',
        week_of='2025-11-24',
        meals=[
            PlannedMeal(
                date='2025-11-24',
                meal_type='dinner',
                recipe=recipe,
                servings=2,
            )
        ],
    )

    with warnings.catch_warnings(record=True):
        warnings.simplefilter("always")
        db.save_meal_plan(meal_plan)

    # Now test swap (it should show deprecation warning)
    # We expect this to fail due to missing recipes table, but we catch the warning first
    with warnings.catch_warnings(record=True) as w:
        warnings.simplefilter("always")
        try:
            db.swap_meal_in_plan('mp_swap_warning_test', '2025-11-24', 'test_recipe')
        except Exception:
            # Expected to fail due to missing recipes table, that's ok
            pass

        # Verify deprecation warning was raised (even if swap failed)
        assert len(w) >= 1  # May include warnings from nested calls
        deprecation_warnings = [x for x in w if issubclass(x.category, DeprecationWarning)]
        assert len(deprecation_warnings) >= 1
        assert any("legacy meal_plans table" in str(x.message) for x in deprecation_warnings)


def test_end_to_end_snapshot_workflow():
    """
    Test complete snapshot workflow:
    1. Create snapshot (simulating /api/plan)
    2. Load from /plan route
    3. Load from /shop route
    4. Load from /cook route
    5. Swap meal (simulating /api/swap-meal)
    6. Verify all tabs still work
    """
    from src.web.app import assistant

    # Step 1: Create initial snapshot (simulating /api/plan)
    recipe1 = Recipe(
        id='recipe_e2e_1',
        name='Day 1 Meal',
        description='First meal',
        ingredients=['chicken'],
        ingredients_raw=['2 lbs chicken'],
        steps=['Cook chicken'],
        servings=4,
        serving_size='1 serving',
        tags=['dinner'],
        estimated_time=30,
        cuisine='American',
        difficulty='easy',
    )

    recipe2 = Recipe(
        id='recipe_e2e_2',
        name='Day 2 Meal',
        description='Second meal',
        ingredients=['fish'],
        ingredients_raw=['1 lb fish'],
        steps=['Cook fish'],
        servings=4,
        serving_size='1 serving',
        tags=['dinner'],
        estimated_time=25,
        cuisine='American',
        difficulty='easy',
    )

    snapshot = {
        'user_id': 1,
        'week_of': '2025-11-24',
        'version': 1,
        'planned_meals': [
            PlannedMeal(
                date='2025-11-24',
                meal_type='dinner',
                recipe=recipe1,
                servings=4,
            ).to_dict(),
            PlannedMeal(
                date='2025-11-25',
                meal_type='dinner',
                recipe=recipe2,
                servings=4,
            ).to_dict(),
        ],
        'grocery_list': None,
    }

    snapshot_id = assistant.db.save_snapshot(snapshot)

    # Step 2: Verify snapshot can be loaded (simulating /plan route)
    loaded_snapshot = assistant.db.get_snapshot(snapshot_id)
    assert loaded_snapshot is not None
    assert len(loaded_snapshot['planned_meals']) == 2
    assert loaded_snapshot['planned_meals'][0]['recipe']['name'] == 'Day 1 Meal'
    assert loaded_snapshot['planned_meals'][1]['recipe']['name'] == 'Day 2 Meal'

    # Step 3: Add grocery list (simulating background shopping generation)
    grocery_list = GroceryList(
        id='gl_e2e',
        week_of='2025-11-24',
        items=[
            GroceryItem(
                name='chicken',
                quantity='2 lbs',
                category='meat',
                recipe_sources=['Day 1 Meal'],
            ),
            GroceryItem(
                name='fish',
                quantity='1 lb',
                category='fish',
                recipe_sources=['Day 2 Meal'],
            ),
        ],
        extra_items=[],
    )

    snapshot = assistant.db.get_snapshot(snapshot_id)
    snapshot['grocery_list'] = grocery_list.to_dict()
    assistant.db.save_snapshot(snapshot)

    # Step 4: Verify grocery list loaded (simulating /shop route)
    updated_snapshot = assistant.db.get_snapshot(snapshot_id)
    assert updated_snapshot['grocery_list'] is not None
    assert len(updated_snapshot['grocery_list']['items']) == 2

    # Step 5: Swap a meal (simulating /api/swap-meal)
    recipe3 = Recipe(
        id='recipe_e2e_3',
        name='Swapped Meal',
        description='Replacement meal',
        ingredients=['pasta'],
        ingredients_raw=['1 lb pasta'],
        steps=['Cook pasta'],
        servings=4,
        serving_size='1 serving',
        tags=['dinner'],
        estimated_time=20,
        cuisine='Italian',
        difficulty='easy',
    )

    snapshot = assistant.db.get_snapshot(snapshot_id)
    snapshot['planned_meals'][0] = PlannedMeal(
        date='2025-11-24',
        meal_type='dinner',
        recipe=recipe3,
        servings=4,
    ).to_dict()
    assistant.db.save_snapshot(snapshot)

    # Step 6: Verify swap persisted
    final_snapshot = assistant.db.get_snapshot(snapshot_id)
    assert final_snapshot['planned_meals'][0]['recipe']['name'] == 'Swapped Meal'
    assert final_snapshot['planned_meals'][1]['recipe']['name'] == 'Day 2 Meal'

    # Step 7: Regenerate shopping list after swap
    new_grocery_list = GroceryList(
        id='gl_e2e_swapped',
        week_of='2025-11-24',
        items=[
            GroceryItem(
                name='pasta',
                quantity='1 lb',
                category='pasta',
                recipe_sources=['Swapped Meal'],
            ),
            GroceryItem(
                name='fish',
                quantity='1 lb',
                category='fish',
                recipe_sources=['Day 2 Meal'],
            ),
        ],
        extra_items=[],
    )

    snapshot = assistant.db.get_snapshot(snapshot_id)
    snapshot['grocery_list'] = new_grocery_list.to_dict()
    assistant.db.save_snapshot(snapshot)

    # Step 8: Verify final state
    final_state = assistant.db.get_snapshot(snapshot_id)
    assert final_state['planned_meals'][0]['recipe']['name'] == 'Swapped Meal'
    assert final_state['grocery_list']['items'][0]['name'] == 'pasta'
    assert final_state['grocery_list']['items'][1]['name'] == 'fish'


def test_snapshot_preserves_all_recipe_fields():
    """Verify snapshot preserves complete Recipe structure for offline use."""
    from src.web.app import assistant

    recipe = Recipe(
        id='complete_recipe',
        name='Complete Recipe',
        description='A fully detailed recipe',
        ingredients=['eggs', 'milk', 'butter'],
        ingredients_raw=['2 eggs', '1 cup milk', '2 tbsp butter'],
        steps=[
            'Beat eggs',
            'Add milk',
            'Cook in butter',
        ],
        servings=2,
        serving_size='1 portion',
        tags=['breakfast', 'easy', '15-minutes-or-less'],
        estimated_time=15,
        cuisine='French',
        difficulty='easy',
    )

    snapshot = {
        'user_id': 1,
        'week_of': '2025-11-24',
        'version': 1,
        'planned_meals': [
            PlannedMeal(
                date='2025-11-24',
                meal_type='breakfast',
                recipe=recipe,
                servings=2,
                notes='For special occasion',
            ).to_dict()
        ],
        'grocery_list': None,
    }

    snapshot_id = assistant.db.save_snapshot(snapshot)
    loaded = assistant.db.get_snapshot(snapshot_id)

    # Verify ALL recipe fields preserved
    loaded_recipe = loaded['planned_meals'][0]['recipe']
    assert loaded_recipe['id'] == 'complete_recipe'
    assert loaded_recipe['name'] == 'Complete Recipe'
    assert loaded_recipe['description'] == 'A fully detailed recipe'
    assert loaded_recipe['ingredients'] == ['eggs', 'milk', 'butter']
    assert loaded_recipe['ingredients_raw'] == ['2 eggs', '1 cup milk', '2 tbsp butter']
    assert len(loaded_recipe['steps']) == 3
    assert loaded_recipe['servings'] == 2
    assert loaded_recipe['serving_size'] == '1 portion'
    assert 'breakfast' in loaded_recipe['tags']
    assert loaded_recipe['estimated_time'] == 15
    assert loaded_recipe['cuisine'] == 'French'
    assert loaded_recipe['difficulty'] == 'easy'

    # Verify PlannedMeal fields
    loaded_meal = loaded['planned_meals'][0]
    assert loaded_meal['date'] == '2025-11-24'
    assert loaded_meal['meal_type'] == 'breakfast'
    assert loaded_meal['servings'] == 2
    assert loaded_meal['notes'] == 'For special occasion'


def test_multiple_users_snapshots_isolated():
    """Test that snapshots are properly isolated by user_id."""
    from src.web.app import assistant

    # Create snapshot for user 1 (with explicit ID)
    snapshot_user1 = {
        'id': 'mp_user1_isolation_test',
        'user_id': 1,
        'week_of': '2025-11-24',
        'version': 1,
        'planned_meals': [
            {
                'date': '2025-11-24',
                'meal_type': 'dinner',
                'recipe': {'id': 'user1_recipe', 'name': 'User 1 Meal'},
                'servings': 2,
            }
        ],
        'grocery_list': None,
    }

    # Create snapshot for user 2 (with explicit ID)
    snapshot_user2 = {
        'id': 'mp_user2_isolation_test',
        'user_id': 2,
        'week_of': '2025-11-24',
        'version': 1,
        'planned_meals': [
            {
                'date': '2025-11-24',
                'meal_type': 'dinner',
                'recipe': {'id': 'user2_recipe', 'name': 'User 2 Meal'},
                'servings': 4,
            }
        ],
        'grocery_list': None,
    }

    id1 = assistant.db.save_snapshot(snapshot_user1)
    id2 = assistant.db.save_snapshot(snapshot_user2)

    # Verify snapshots are different
    assert id1 == 'mp_user1_isolation_test'
    assert id2 == 'mp_user2_isolation_test'
    assert id1 != id2

    # Verify user 1 can't see user 2's snapshot via query
    user1_snapshots = assistant.db.get_user_snapshots(user_id=1, limit=10)
    user1_ids = [s['id'] for s in user1_snapshots]
    assert id1 in user1_ids
    assert id2 not in user1_ids

    # Verify user 2 can't see user 1's snapshot via query
    user2_snapshots = assistant.db.get_user_snapshots(user_id=2, limit=10)
    user2_ids = [s['id'] for s in user2_snapshots]
    assert id2 in user2_ids
    assert id1 not in user2_ids


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
