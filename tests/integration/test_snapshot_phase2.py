"""
Integration tests for Phase 2: Dual-write snapshots on plan creation.

Tests that /api/plan creates both legacy MealPlan AND snapshot entries.
UI still reads from legacy tables in Phase 2.

IMPORTANT: These tests require:
- ANTHROPIC_API_KEY environment variable
- recipes.db or recipes_dev.db database
- Real LLM calls (no mocking)
"""

import pytest
import sys
import os
from datetime import datetime, timedelta

# Add project root to path
project_root = os.path.join(os.path.dirname(__file__), '..', '..')
sys.path.insert(0, project_root)
sys.path.insert(0, os.path.join(project_root, 'src'))

# Check for required environment variables
API_KEY_AVAILABLE = bool(os.environ.get("ANTHROPIC_API_KEY"))
RECIPES_DB_EXISTS = os.path.exists(os.path.join(project_root, "data", "recipes.db")) or \
                    os.path.exists(os.path.join(project_root, "data", "recipes_dev.db"))


@pytest.mark.skipif(
    not (API_KEY_AVAILABLE and RECIPES_DB_EXISTS),
    reason="Requires ANTHROPIC_API_KEY and recipes database"
)
def test_plan_creates_snapshot_when_enabled(client):
    """
    Test that /api/plan creates a snapshot when SNAPSHOTS_ENABLED=true.

    This is a real integration test - no mocking, actual LLM calls.
    """
    # Login to set user_id in session
    response = client.post('/login', data={
        'username': 'admin',
        'password': 'password'
    }, follow_redirects=False)
    assert response.status_code == 302  # Redirect after login

    # Get next Monday
    today = datetime.now()
    days_until_monday = (7 - today.weekday()) % 7
    if days_until_monday == 0:
        days_until_monday = 7
    next_monday = today + timedelta(days=days_until_monday)
    week_of = next_monday.strftime("%Y-%m-%d")

    # Call /api/plan to create a meal plan
    response = client.post('/api/plan', json={
        'week_of': week_of,
        'num_days': 3,  # Use 3 days for faster test
        'include_explanation': False
    })

    # Verify plan was created successfully
    assert response.status_code == 200
    data = response.get_json()
    assert data.get('success') is True
    assert 'meal_plan_id' in data

    meal_plan_id = data['meal_plan_id']

    # Verify snapshot was created
    from src.data.database import DatabaseInterface
    db = DatabaseInterface(db_dir="src/web/data")

    # Get snapshot by ID (should match meal_plan_id)
    snapshot = db.get_snapshot(meal_plan_id)
    assert snapshot is not None, "Snapshot should be created"

    # Verify snapshot structure
    assert snapshot['id'] == meal_plan_id
    assert snapshot['user_id'] == 1  # admin user
    assert snapshot['week_of'] == week_of
    assert snapshot['version'] == 1
    assert 'planned_meals' in snapshot
    assert len(snapshot['planned_meals']) == 3  # 3 days requested
    assert snapshot['grocery_list'] is None  # Not yet filled in Phase 2

    # Verify each planned meal has embedded recipe
    for meal in snapshot['planned_meals']:
        assert 'date' in meal
        assert 'meal_type' in meal
        assert 'recipe' in meal
        assert 'servings' in meal

        # Verify recipe structure
        recipe = meal['recipe']
        assert 'id' in recipe
        assert 'name' in recipe
        assert 'ingredients' in recipe
        assert 'steps' in recipe

    # Verify user can query their snapshots
    user_snapshots = db.get_user_snapshots(user_id=1, limit=10)
    assert len(user_snapshots) >= 1
    assert any(s['id'] == meal_plan_id for s in user_snapshots)


def test_login_sets_user_id_in_session(client):
    """Test that login sets both username and user_id in session."""
    # Login as admin
    response = client.post('/login', data={
        'username': 'admin',
        'password': 'password'
    }, follow_redirects=False)

    assert response.status_code == 302  # Redirect

    # Check session (note: Flask test client maintains session across requests)
    with client.session_transaction() as sess:
        assert sess.get('username') == 'admin'
        assert sess.get('user_id') == 1  # admin maps to user_id 1

    # Test agusta user
    client.get('/logout')  # Clear session

    response = client.post('/login', data={
        'username': 'agusta',
        'password': 'password'
    }, follow_redirects=False)

    with client.session_transaction() as sess:
        assert sess.get('username') == 'agusta'
        assert sess.get('user_id') == 2  # agusta maps to user_id 2


@pytest.mark.skipif(not API_KEY_AVAILABLE, reason="Requires ANTHROPIC_API_KEY")
def test_snapshot_enabled_flag_controls_behavior():
    """Test that SNAPSHOTS_ENABLED flag controls dual-write behavior."""
    from src.web.app import SNAPSHOTS_ENABLED

    # Verify default is True
    assert SNAPSHOTS_ENABLED is True

    # Note: Testing with SNAPSHOTS_ENABLED=false would require reloading the module
    # For now, just verify the flag is accessible and set correctly


if __name__ == '__main__':
    pytest.main([__file__, '-v', '-s'])
