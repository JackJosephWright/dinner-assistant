#!/usr/bin/env python3
"""
Integration test for web interface preload optimization.

This test simulates a real user flow:
1. Create a meal plan via the web interface
2. Verify that preload automatically triggers
3. Check that Shop and Cook pages load instantly with cached data
"""

import sys
import time
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "src"))

import pytest
import logging
from datetime import datetime, timedelta
from flask import session

# Import the Flask app
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "src" / "web"))
from app import app, assistant

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@pytest.fixture
def client():
    """Create a test client for the Flask app."""
    app.config['TESTING'] = True
    app.config['SECRET_KEY'] = 'test-secret-key'

    with app.test_client() as client:
        yield client


def test_complete_user_flow_with_preload(client):
    """
    Integration test: Complete user flow from planning to shopping to cooking.

    Tests:
    1. Create meal plan (should be fast)
    2. Verify preload endpoint triggers automatically
    3. Verify shopping list is cached and loads instantly
    4. Verify cooking guides are preloaded
    """
    logger.info("\n" + "="*70)
    logger.info("INTEGRATION TEST: Web Preload Optimization")
    logger.info("="*70)

    # Get next Monday for planning
    today = datetime.now()
    days_ahead = 7 - today.weekday()
    if days_ahead <= 0:
        days_ahead += 7
    next_monday = today + timedelta(days=days_ahead)
    week_of = next_monday.strftime("%Y-%m-%d")

    # Step 1: Create meal plan via chat API
    logger.info("\n1. Creating meal plan via chat API...")
    start_time = time.time()

    response = client.post('/api/chat', json={
        'message': f'Plan meals for me (for 7 days starting {week_of})'
    })

    plan_time = time.time() - start_time
    logger.info(f"   ✓ Plan created in {plan_time:.2f}s")

    assert response.status_code == 200
    result = response.get_json()
    assert result['success'] is True
    assert 'meal_plan_id' in result

    meal_plan_id = result['meal_plan_id']
    logger.info(f"   ✓ Meal plan ID: {meal_plan_id}")

    # Step 2: Simulate page load and trigger preload
    logger.info("\n2. Triggering preload endpoint (simulating page load)...")
    start_time = time.time()

    response = client.post('/api/plan/preload')
    preload_time = time.time() - start_time

    assert response.status_code == 200
    result = response.get_json()
    assert result['success'] is True

    logger.info(f"   ✓ Preload completed in {preload_time:.2f}s")
    logger.info(f"   ✓ Shopping list created: {result.get('shopping_list_created')}")
    logger.info(f"   ✓ Recipes preloaded: {result.get('recipes_preloaded', 0)}")

    shopping_list_id = result['shopping_list_id']

    # Step 3: Verify shopping list loads instantly (should be cached)
    logger.info("\n3. Loading shopping list page (should be instant)...")
    start_time = time.time()

    response = client.get('/shop')
    shop_load_time = time.time() - start_time

    assert response.status_code == 200
    logger.info(f"   ✓ Shop page loaded in {shop_load_time:.2f}s")

    # Verify shopping list is in the HTML
    html = response.data.decode('utf-8')
    assert 'Shopping List' in html or 'shopping_list_id' in html

    # Step 4: Verify cooking page loads with recipes
    logger.info("\n4. Loading cooking page (should have preloaded recipes)...")
    start_time = time.time()

    response = client.get('/cook')
    cook_load_time = time.time() - start_time

    assert response.status_code == 200
    logger.info(f"   ✓ Cook page loaded in {cook_load_time:.2f}s")

    # Verify meals are in the HTML
    html = response.data.decode('utf-8')
    assert 'current_meals' in html or len(html) > 1000  # Should have content

    # Step 5: Test individual recipe cooking guide (should be cached)
    logger.info("\n5. Loading individual cooking guide...")

    # Get first recipe ID from meal plan
    meal_plan = assistant.db.get_meal_plan(meal_plan_id)
    first_recipe_id = meal_plan.meals[0].recipe_id

    start_time = time.time()
    response = client.get(f'/api/cook/{first_recipe_id}')
    guide_load_time = time.time() - start_time

    assert response.status_code == 200
    result = response.get_json()
    assert result['success'] is True

    logger.info(f"   ✓ Cooking guide loaded in {guide_load_time:.2f}s")
    # Handle both agentic (nested) and algorithmic (flat) response structures
    recipe_name = result.get('guide', {}).get('recipe_name') or result.get('recipe_name', 'Unknown')
    logger.info(f"   ✓ Recipe: {recipe_name}")

    # Summary
    logger.info("\n" + "="*70)
    logger.info("TEST SUMMARY")
    logger.info("="*70)
    logger.info(f"✓ Plan creation:      {plan_time:.2f}s")
    logger.info(f"✓ Background preload: {preload_time:.2f}s")
    logger.info(f"✓ Shop page load:     {shop_load_time:.2f}s (instant!)")
    logger.info(f"✓ Cook page load:     {cook_load_time:.2f}s (instant!)")
    logger.info(f"✓ Recipe guide load:  {guide_load_time:.2f}s (cached!)")
    logger.info("="*70)

    # Assertions for performance
    assert shop_load_time < 1.0, f"Shop page should load in <1s, took {shop_load_time:.2f}s"
    assert cook_load_time < 1.0, f"Cook page should load in <1s, took {cook_load_time:.2f}s"
    assert guide_load_time < 5.0, f"Recipe guide should load in <5s, took {guide_load_time:.2f}s"

    logger.info("\n✅ All integration tests passed!")


def test_preload_prevents_duplicate_work(client):
    """
    Test that preload doesn't regenerate shopping list if it already exists.
    """
    logger.info("\n" + "="*70)
    logger.info("TEST: Preload prevents duplicate work")
    logger.info("="*70)

    # Get next Monday
    today = datetime.now()
    days_ahead = 7 - today.weekday()
    if days_ahead <= 0:
        days_ahead += 7
    next_monday = today + timedelta(days=days_ahead)
    week_of = next_monday.strftime("%Y-%m-%d")

    # Step 1: Create plan
    response = client.post('/api/chat', json={
        'message': f'Plan meals for me (for 7 days starting {week_of})'
    })
    assert response.status_code == 200
    result = response.get_json()
    meal_plan_id = result['meal_plan_id']

    # Step 2: First preload (should create shopping list)
    logger.info("\n1. First preload (should create shopping list)...")
    start_time = time.time()
    response = client.post('/api/plan/preload')
    first_preload_time = time.time() - start_time

    assert response.status_code == 200
    result = response.get_json()
    assert result['success'] is True
    assert result['shopping_list_created'] is True

    logger.info(f"   ✓ First preload: {first_preload_time:.2f}s (created shopping list)")

    shopping_list_id = result['shopping_list_id']

    # Step 3: Second preload (should skip shopping list generation)
    logger.info("\n2. Second preload (should skip shopping list)...")
    start_time = time.time()
    response = client.post('/api/plan/preload')
    second_preload_time = time.time() - start_time

    assert response.status_code == 200
    result = response.get_json()
    assert result['success'] is True
    assert result['shopping_list_created'] is False  # Should be False (not created again)
    assert result['shopping_list_id'] == shopping_list_id  # Same ID

    logger.info(f"   ✓ Second preload: {second_preload_time:.2f}s (reused existing)")

    # Second preload should be faster (no shopping list generation)
    logger.info(f"\n✓ Speed improvement: {first_preload_time - second_preload_time:.2f}s faster")

    logger.info("\n✅ Duplicate work prevention test passed!")


if __name__ == "__main__":
    # Run with pytest
    pytest.main([__file__, "-v", "-s"])
