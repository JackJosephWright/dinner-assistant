#!/usr/bin/env python3
"""
Fast integration test for preload timing (without LLM calls).

This test verifies preload mechanics and timing without slow LLM operations.
"""

import sys
import time
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "src"))

import pytest
import logging
from datetime import datetime, timedelta

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


def test_preload_timing_with_existing_plan(client):
    """
    Test preload timing when a meal plan already exists.
    This avoids slow LLM calls by using an existing plan.
    """
    logger.info("\n" + "="*70)
    logger.info("INTEGRATION TEST: Preload Timing (Fast)")
    logger.info("="*70)

    # Step 1: Get or create a recent meal plan
    logger.info("\n1. Finding existing meal plan...")
    recent_plans = assistant.db.get_recent_meal_plans(limit=1)

    if not recent_plans:
        pytest.skip("No existing meal plans found. Run the full integration test first.")

    meal_plan = recent_plans[0]
    meal_plan_id = meal_plan.id
    logger.info(f"   ✓ Using meal plan: {meal_plan_id}")
    logger.info(f"   ✓ Week of: {meal_plan.week_of}")
    logger.info(f"   ✓ Meals: {len(meal_plan.meals)}")

    # Set the meal plan in session
    with client.session_transaction() as sess:
        sess['meal_plan_id'] = meal_plan_id

    # Step 2: Time the preload endpoint
    logger.info("\n2. Testing preload endpoint...")
    start_time = time.time()

    response = client.post('/api/plan/preload')
    preload_time = time.time() - start_time

    assert response.status_code == 200
    result = response.get_json()
    assert result['success'] is True

    logger.info(f"   ✓ Preload completed in {preload_time:.2f}s")
    logger.info(f"   ✓ Shopping list: {result.get('shopping_list_id')}")
    logger.info(f"   ✓ Recipes preloaded: {result.get('recipes_preloaded', 0)}")

    # Step 3: Time shop page load
    logger.info("\n3. Testing shop page load...")
    start_time = time.time()

    response = client.get('/shop')
    shop_load_time = time.time() - start_time

    assert response.status_code == 200
    logger.info(f"   ✓ Shop page loaded in {shop_load_time:.2f}s")

    # Step 4: Time cook page load
    logger.info("\n4. Testing cook page load...")
    start_time = time.time()

    response = client.get('/cook')
    cook_load_time = time.time() - start_time

    assert response.status_code == 200
    logger.info(f"   ✓ Cook page loaded in {cook_load_time:.2f}s")

    # Step 5: Time recipe guide load
    logger.info("\n5. Testing recipe guide load...")
    first_recipe_id = meal_plan.meals[0].recipe_id

    start_time = time.time()
    response = client.get(f'/api/cook/{first_recipe_id}')
    guide_load_time = time.time() - start_time

    assert response.status_code == 200
    result = response.get_json()
    assert result['success'] is True

    logger.info(f"   ✓ Guide loaded in {guide_load_time:.2f}s")
    # Handle both agentic (nested) and algorithmic (flat) response structures
    recipe_name = result.get('guide', {}).get('recipe_name') or result.get('recipe_name', 'Unknown')
    logger.info(f"   ✓ Recipe: {recipe_name}")

    # Summary
    logger.info("\n" + "="*70)
    logger.info("TIMING SUMMARY")
    logger.info("="*70)
    logger.info(f"Preload:      {preload_time:.2f}s")
    logger.info(f"Shop load:    {shop_load_time:.2f}s")
    logger.info(f"Cook load:    {cook_load_time:.2f}s")
    logger.info(f"Guide load:   {guide_load_time:.2f}s")
    logger.info("="*70)

    # Performance assertions
    assert shop_load_time < 2.0, f"Shop page should load in <2s, took {shop_load_time:.2f}s"
    assert cook_load_time < 2.0, f"Cook page should load in <2s, took {cook_load_time:.2f}s"

    logger.info("\n✅ Timing test passed!")


def test_api_plan_current_performance(client):
    """Test that /api/plan/current loads quickly with cached recipes."""
    logger.info("\n" + "="*70)
    logger.info("TEST: /api/plan/current Performance")
    logger.info("="*70)

    # Get existing plan
    recent_plans = assistant.db.get_recent_meal_plans(limit=1)
    if not recent_plans:
        pytest.skip("No existing meal plans found")

    meal_plan = recent_plans[0]

    # Set in session
    with client.session_transaction() as sess:
        sess['meal_plan_id'] = meal_plan.id

    # Time the API call
    logger.info("\nTiming /api/plan/current...")
    start_time = time.time()

    response = client.get('/api/plan/current')
    api_time = time.time() - start_time

    assert response.status_code == 200
    result = response.get_json()
    assert result['success'] is True
    assert 'plan' in result

    logger.info(f"✓ API call completed in {api_time:.2f}s")
    logger.info(f"✓ Returned {len(result['plan']['meals'])} meals")

    # Should be fast with parallel recipe fetching
    assert api_time < 1.0, f"API should respond in <1s, took {api_time:.2f}s"

    logger.info("\n✅ API performance test passed!")


if __name__ == "__main__":
    # Run with pytest
    pytest.main([__file__, "-v", "-s"])
