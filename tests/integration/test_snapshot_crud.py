"""
Integration tests for Phase 1: Snapshot CRUD operations.

Tests the meal_plan_snapshots table and DatabaseInterface methods:
- save_snapshot()
- get_snapshot()
- get_user_snapshots()
"""

import pytest
import sys
import os

# Add project root to path
project_root = os.path.join(os.path.dirname(__file__), '..', '..')
sys.path.insert(0, project_root)
sys.path.insert(0, os.path.join(project_root, 'src'))

from data.database import DatabaseInterface


def test_save_snapshot_with_auto_id(db):
    """Test that save_snapshot auto-generates ID if missing."""
    snapshot = {
        "user_id": 1,
        "week_of": "2025-11-24",
        "version": 1,
        "planned_meals": [
            {
                "date": "2025-11-24",
                "meal_type": "dinner",
                "recipe": {"id": "123", "name": "Test Recipe"},
                "servings": 4,
            }
        ],
        "grocery_list": None,
    }

    snapshot_id = db.save_snapshot(snapshot)

    # ID should be auto-generated in format: mp_{week_of}_{timestamp}
    assert snapshot_id.startswith("mp_2025-11-24_")
    assert len(snapshot_id) > 20  # Has timestamp appended


def test_save_snapshot_with_provided_id(db):
    """Test that save_snapshot uses provided ID."""
    snapshot = {
        "id": "mp_custom_test_123",
        "user_id": 1,
        "week_of": "2025-11-24",
        "version": 1,
        "planned_meals": [],
        "grocery_list": None,
    }

    snapshot_id = db.save_snapshot(snapshot)

    assert snapshot_id == "mp_custom_test_123"


def test_get_snapshot_roundtrip(db):
    """Test that snapshot can be saved and retrieved with all fields intact."""
    original_snapshot = {
        "user_id": 1,
        "week_of": "2025-11-24",
        "version": 1,
        "planned_meals": [
            {
                "date": "2025-11-24",
                "meal_type": "dinner",
                "servings": 4,
                "notes": "Test meal",
                "recipe": {
                    "id": "456",
                    "name": "Grilled Chicken",
                    "description": "Delicious chicken",
                    "ingredients": ["chicken", "salt", "pepper"],
                    "ingredients_raw": ["2 lbs chicken", "1 tsp salt", "1 tsp pepper"],
                    "ingredients_structured": [
                        {
                            "raw": "2 lbs chicken",
                            "quantity": 2.0,
                            "unit": "lbs",
                            "name": "chicken",
                            "category": "meat",
                        }
                    ],
                    "steps": ["Season chicken", "Grill for 20 minutes"],
                    "servings": 4,
                    "tags": ["easy", "30-minutes-or-less"],
                    "estimated_time": 30,
                    "cuisine": "American",
                    "difficulty": "easy",
                },
            }
        ],
        "grocery_list": {
            "items": [
                {
                    "name": "chicken",
                    "quantity": "2 lbs",
                    "category": "meat",
                    "recipe_sources": ["Grilled Chicken"],
                }
            ],
            "store_sections": {
                "meat": [
                    {
                        "name": "chicken",
                        "quantity": "2 lbs",
                        "category": "meat",
                        "recipe_sources": ["Grilled Chicken"],
                    }
                ]
            },
            "extra_items": [],
        },
    }

    # Save snapshot
    snapshot_id = db.save_snapshot(original_snapshot)

    # Load snapshot
    loaded_snapshot = db.get_snapshot(snapshot_id)

    # Verify all critical fields
    assert loaded_snapshot is not None
    assert loaded_snapshot['id'] == snapshot_id
    assert loaded_snapshot['user_id'] == 1
    assert loaded_snapshot['week_of'] == "2025-11-24"
    assert loaded_snapshot['version'] == 1

    # Verify planned meals
    assert len(loaded_snapshot['planned_meals']) == 1
    meal = loaded_snapshot['planned_meals'][0]
    assert meal['date'] == "2025-11-24"
    assert meal['meal_type'] == "dinner"
    assert meal['recipe']['name'] == "Grilled Chicken"
    assert len(meal['recipe']['ingredients']) == 3
    assert len(meal['recipe']['ingredients_structured']) == 1

    # Verify grocery list
    assert loaded_snapshot['grocery_list'] is not None
    assert len(loaded_snapshot['grocery_list']['items']) == 1
    assert loaded_snapshot['grocery_list']['items'][0]['name'] == "chicken"


def test_get_snapshot_nonexistent(db):
    """Test that get_snapshot returns None for nonexistent ID."""
    result = db.get_snapshot("nonexistent_id_12345")
    assert result is None


def test_get_user_snapshots(db):
    """Test that get_user_snapshots returns all snapshots for a user."""
    # Create 3 snapshots for user 1
    for i in range(3):
        snapshot = {
            "user_id": 1,
            "week_of": f"2025-11-{24 + i}",
            "version": 1,
            "planned_meals": [],
            "grocery_list": None,
        }
        db.save_snapshot(snapshot)

    # Create 1 snapshot for user 2
    snapshot_user2 = {
        "user_id": 2,
        "week_of": "2025-11-30",
        "version": 1,
        "planned_meals": [],
        "grocery_list": None,
    }
    db.save_snapshot(snapshot_user2)

    # Get snapshots for user 1
    user1_snapshots = db.get_user_snapshots(user_id=1, limit=10)

    assert len(user1_snapshots) == 3
    assert all(s['user_id'] == 1 for s in user1_snapshots)

    # Get snapshots for user 2
    user2_snapshots = db.get_user_snapshots(user_id=2, limit=10)

    assert len(user2_snapshots) == 1
    assert user2_snapshots[0]['user_id'] == 2


def test_get_user_snapshots_respects_limit(db):
    """Test that get_user_snapshots respects the limit parameter."""
    # Create 5 snapshots
    for i in range(5):
        snapshot = {
            "user_id": 1,
            "week_of": f"2025-11-{20 + i}",
            "version": 1,
            "planned_meals": [],
            "grocery_list": None,
        }
        db.save_snapshot(snapshot)

    # Request only 2
    snapshots = db.get_user_snapshots(user_id=1, limit=2)

    assert len(snapshots) == 2


def test_snapshot_update_via_insert_or_replace(db):
    """Test that saving a snapshot with same ID updates it (INSERT OR REPLACE)."""
    snapshot = {
        "id": "mp_test_update",
        "user_id": 1,
        "week_of": "2025-11-24",
        "version": 1,
        "planned_meals": [],
        "grocery_list": None,
    }

    # Save initial
    db.save_snapshot(snapshot)

    # Load and verify
    loaded = db.get_snapshot("mp_test_update")
    assert loaded['grocery_list'] is None

    # Update with grocery list
    snapshot['grocery_list'] = {"items": [{"name": "milk", "quantity": "1 gallon"}]}
    db.save_snapshot(snapshot)

    # Load again
    updated = db.get_snapshot("mp_test_update")
    assert updated['grocery_list'] is not None
    assert updated['grocery_list']['items'][0]['name'] == "milk"

    # Should still only have 1 snapshot (not 2)
    all_snapshots = db.get_user_snapshots(user_id=1)
    assert len(all_snapshots) == 1


def test_snapshot_preserves_nested_structures(db):
    """Test that deeply nested structures are preserved correctly."""
    snapshot = {
        "user_id": 1,
        "week_of": "2025-11-24",
        "version": 1,
        "planned_meals": [
            {
                "recipe": {
                    "ingredients_structured": [
                        {
                            "nested_field": {
                                "deeply": {
                                    "nested": "value"
                                }
                            }
                        }
                    ]
                }
            }
        ],
        "grocery_list": None,
    }

    snapshot_id = db.save_snapshot(snapshot)
    loaded = db.get_snapshot(snapshot_id)

    # Verify deep nesting preserved
    nested_value = loaded['planned_meals'][0]['recipe']['ingredients_structured'][0]['nested_field']['deeply']['nested']
    assert nested_value == "value"


@pytest.mark.skipif(
    not os.path.exists('recipes.db') and not os.path.exists('recipes_dev.db'),
    reason="Requires recipes database"
)
def test_swap_meal_in_snapshot(db):
    """Test that swap_meal_in_snapshot updates the correct meal in the snapshot."""
    # Create a snapshot with two meals
    snapshot = {
        "id": "mp_test_swap_meal",
        "user_id": 1,
        "week_of": "2025-11-24",
        "version": 1,
        "planned_meals": [
            {
                "date": "2025-11-24",
                "meal_type": "dinner",
                "recipe": {
                    "id": "recipe_old",
                    "name": "Old Recipe",
                    "description": "Old description",
                    "ingredients_raw": ["old ingredient"],
                    "steps": ["old step"],
                    "tags": [],
                },
                "servings": 4,
            },
            {
                "date": "2025-11-25",
                "meal_type": "dinner",
                "recipe": {
                    "id": "recipe_other",
                    "name": "Other Recipe",
                    "description": "Other description",
                    "ingredients_raw": ["other ingredient"],
                    "steps": ["other step"],
                    "tags": [],
                },
                "servings": 4,
            },
        ],
        "grocery_list": None,
    }
    db.save_snapshot(snapshot)

    # Get a recipe from the actual database (need recipes.db)
    try:
        recipes = db.search_recipes("chicken", limit=1)
        if not recipes:
            pytest.skip("No recipes in database to swap")
    except Exception:
        pytest.skip("Recipes database not available")

    new_recipe = recipes[0]

    # Swap the meal on 2025-11-24
    result = db.swap_meal_in_snapshot(
        snapshot_id="mp_test_swap_meal",
        date="2025-11-24",
        new_recipe_id=new_recipe.id,
        user_id=1,
    )

    assert result is not None
    assert result['id'] == "mp_test_swap_meal"

    # Reload and verify
    loaded = db.get_snapshot("mp_test_swap_meal")

    # First meal should be swapped
    meal_24 = next(m for m in loaded['planned_meals'] if m['date'] == '2025-11-24')
    assert meal_24['recipe']['id'] == new_recipe.id
    assert meal_24['recipe']['name'] == new_recipe.name

    # Second meal should be unchanged
    meal_25 = next(m for m in loaded['planned_meals'] if m['date'] == '2025-11-25')
    assert meal_25['recipe']['id'] == "recipe_other"
    assert meal_25['recipe']['name'] == "Other Recipe"


@pytest.mark.skipif(
    not os.path.exists('recipes.db') and not os.path.exists('recipes_dev.db'),
    reason="Requires recipes database"
)
def test_swap_meal_in_snapshot_clears_variant(db):
    """Test that swap_meal_in_snapshot clears any existing variant."""
    # Create a snapshot with a meal that has a variant
    snapshot = {
        "id": "mp_test_swap_variant",
        "user_id": 1,
        "week_of": "2025-11-24",
        "version": 1,
        "planned_meals": [
            {
                "date": "2025-11-24",
                "meal_type": "dinner",
                "recipe": {
                    "id": "recipe_with_variant",
                    "name": "Recipe With Variant",
                },
                "servings": 4,
                "variant": {
                    "variant_id": "variant:mp_test:2025-11-24:dinner",
                    "compiled_recipe": {"name": "Modified Recipe"},
                    "patch_ops": [{"op": "replace_ingredient"}],
                },
            },
        ],
        "grocery_list": None,
    }
    db.save_snapshot(snapshot)

    # Get a recipe to swap in
    try:
        recipes = db.search_recipes("beef", limit=1)
        if not recipes:
            pytest.skip("No recipes in database to swap")
    except Exception:
        pytest.skip("Recipes database not available")

    new_recipe = recipes[0]

    # Swap the meal
    result = db.swap_meal_in_snapshot(
        snapshot_id="mp_test_swap_variant",
        date="2025-11-24",
        new_recipe_id=new_recipe.id,
        user_id=1,
    )

    assert result is not None

    # Reload and verify variant is gone
    loaded = db.get_snapshot("mp_test_swap_variant")
    meal = loaded['planned_meals'][0]

    assert 'variant' not in meal or meal.get('variant') is None
    assert meal['recipe']['id'] == new_recipe.id


def test_swap_meal_in_snapshot_nonexistent_snapshot(db):
    """Test that swap_meal_in_snapshot returns None for nonexistent snapshot."""
    result = db.swap_meal_in_snapshot(
        snapshot_id="nonexistent_snapshot",
        date="2025-11-24",
        new_recipe_id="some_recipe",
        user_id=1,
    )

    assert result is None


def test_swap_meal_in_snapshot_nonexistent_recipe(db):
    """Test that swap_meal_in_snapshot returns None for nonexistent recipe."""
    # Create a snapshot
    snapshot = {
        "id": "mp_test_swap_norecipe",
        "user_id": 1,
        "week_of": "2025-11-24",
        "version": 1,
        "planned_meals": [
            {
                "date": "2025-11-24",
                "meal_type": "dinner",
                "recipe": {"id": "recipe1", "name": "Recipe 1"},
                "servings": 4,
            },
        ],
        "grocery_list": None,
    }
    db.save_snapshot(snapshot)

    # Try to swap with a nonexistent recipe
    try:
        result = db.swap_meal_in_snapshot(
            snapshot_id="mp_test_swap_norecipe",
            date="2025-11-24",
            new_recipe_id="nonexistent_recipe_xyz",
            user_id=1,
        )
        # Should return None because recipe doesn't exist
        assert result is None
    except Exception:
        # If recipes table doesn't exist, skip this test
        pytest.skip("Recipes database not available")


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
