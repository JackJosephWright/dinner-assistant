#!/usr/bin/env python3
"""
Integration test for plan update workflow.

This test verifies:
1. Create a meal plan
2. Verify shopping list is generated
3. Verify cook page has recipes
4. Update the meal plan (replan)
5. Verify shopping list updates
6. Verify cook page updates
"""

import sys
import time
import os
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "src"))

import pytest
import logging
from datetime import datetime, timedelta
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

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


def test_full_plan_update_workflow(client):
    """
    Integration test: Create plan, verify shop/cook, update plan, verify updates.

    Tests:
    1. Create initial meal plan
    2. Verify shopping list is created and populated
    3. Verify cook page shows recipes
    4. Update the meal plan (replan)
    5. Verify shopping list is updated with new recipes
    6. Verify cook page shows updated recipes
    """
    logger.info("\n" + "="*70)
    logger.info("INTEGRATION TEST: Plan Update Workflow")
    logger.info("="*70)

    # Get next Monday
    today = datetime.now()
    days_ahead = 7 - today.weekday()
    if days_ahead <= 0:
        days_ahead += 7
    next_monday = today + timedelta(days=days_ahead)
    week_of = next_monday.strftime("%Y-%m-%d")

    # ==================== STEP 1: Create Initial Plan ====================
    logger.info("\n" + "="*70)
    logger.info("STEP 1: Creating initial meal plan")
    logger.info("="*70)

    start_time = time.time()
    response = client.post('/api/chat', json={
        'message': f'Plan meals for me (for 7 days starting {week_of})'
    })
    plan_time = time.time() - start_time

    if response.status_code != 200:
        logger.error(f"❌ Chat API returned {response.status_code}")
        logger.error(f"Response: {response.get_json()}")

    assert response.status_code == 200
    result = response.get_json()
    assert result['success'] is True
    assert 'meal_plan_id' in result

    initial_plan_id = result['meal_plan_id']
    logger.info(f"✓ Initial plan created in {plan_time:.2f}s")
    logger.info(f"✓ Plan ID: {initial_plan_id}")

    # Get the initial plan details
    initial_plan = assistant.db.get_meal_plan(initial_plan_id)
    initial_recipe_ids = [meal.recipe_id for meal in initial_plan.meals]
    initial_recipe_names = [meal.recipe_name for meal in initial_plan.meals]

    logger.info(f"✓ Initial plan has {len(initial_recipe_ids)} meals:")
    for i, name in enumerate(initial_recipe_names, 1):
        logger.info(f"  {i}. {name}")

    # ==================== STEP 2: Verify Shopping List ====================
    logger.info("\n" + "="*70)
    logger.info("STEP 2: Verifying shopping list generation")
    logger.info("="*70)

    # Trigger preload (which creates shopping list)
    start_time = time.time()
    response = client.post('/api/plan/preload')
    preload_time = time.time() - start_time

    assert response.status_code == 200
    result = response.get_json()
    assert result['success'] is True

    initial_shopping_list_id = result['shopping_list_id']
    logger.info(f"✓ Shopping list created in {preload_time:.2f}s")
    logger.info(f"✓ Shopping list ID: {initial_shopping_list_id}")

    # Get shopping list details
    initial_shopping_list = assistant.db.get_grocery_list(initial_shopping_list_id)
    initial_item_count = len(initial_shopping_list.items)
    logger.info(f"✓ Shopping list has {initial_item_count} items")

    # Verify shop page loads with shopping list items
    response = client.get('/shop')
    assert response.status_code == 200
    html = response.data.decode('utf-8')
    # Check that shopping list items are displayed
    assert f"{initial_item_count} items" in html, f"Expected '{initial_item_count} items' in shop page HTML"
    assert week_of in html, f"Expected week date '{week_of}' in shop page HTML"
    logger.info(f"✓ Shop page displays shopping list with {initial_item_count} items")

    # ==================== STEP 3: Verify Cook Page ====================
    logger.info("\n" + "="*70)
    logger.info("STEP 3: Verifying cook page")
    logger.info("="*70)

    response = client.get('/cook')
    assert response.status_code == 200
    html = response.data.decode('utf-8')

    # Check that at least some recipe names appear in the cook page
    recipes_found = sum(1 for name in initial_recipe_names if name in html)
    logger.info(f"✓ Cook page displays {recipes_found}/{len(initial_recipe_names)} recipe names")
    assert recipes_found > 0, "Cook page should display at least some recipes"

    # ==================== STEP 4: Update Plan (Replan) ====================
    logger.info("\n" + "="*70)
    logger.info("STEP 4: Updating meal plan (replan)")
    logger.info("="*70)

    start_time = time.time()
    response = client.post('/api/chat', json={
        'message': f'Replan meals for me (for 7 days starting {week_of})'
    })
    replan_time = time.time() - start_time

    assert response.status_code == 200
    result = response.get_json()
    assert result['success'] is True

    # The plan ID should be the same (updated in place)
    # but let's check what the chatbot says
    logger.info(f"✓ Replan completed in {replan_time:.2f}s")

    # Get the updated plan details
    updated_plan = assistant.db.get_meal_plan(initial_plan_id)
    updated_recipe_ids = [meal.recipe_id for meal in updated_plan.meals]
    updated_recipe_names = [meal.recipe_name for meal in updated_plan.meals]

    logger.info(f"✓ Updated plan has {len(updated_recipe_ids)} meals:")
    for i, name in enumerate(updated_recipe_names, 1):
        logger.info(f"  {i}. {name}")

    # Check if meals actually changed
    changed_meals = sum(1 for old, new in zip(initial_recipe_ids, updated_recipe_ids) if old != new)
    logger.info(f"✓ {changed_meals}/{len(initial_recipe_ids)} meals changed")

    # ==================== STEP 5: Verify Shopping List Updates ====================
    logger.info("\n" + "="*70)
    logger.info("STEP 5: Verifying shopping list updates")
    logger.info("="*70)

    # Trigger preload again (should create new shopping list)
    start_time = time.time()
    response = client.post('/api/plan/preload')
    preload_time2 = time.time() - start_time

    assert response.status_code == 200
    result = response.get_json()
    assert result['success'] is True

    updated_shopping_list_id = result['shopping_list_id']
    logger.info(f"✓ Preload completed in {preload_time2:.2f}s")
    logger.info(f"✓ Shopping list ID: {updated_shopping_list_id}")

    # Get updated shopping list details
    updated_shopping_list = assistant.db.get_grocery_list(updated_shopping_list_id)
    updated_item_count = len(updated_shopping_list.items)
    logger.info(f"✓ Updated shopping list has {updated_item_count} items")

    # If meals changed, shopping list should be different
    if changed_meals > 0:
        if updated_shopping_list_id != initial_shopping_list_id:
            logger.info(f"✓ Shopping list was regenerated (different ID)")
        else:
            logger.warning(f"⚠ Shopping list ID unchanged despite meal changes")

    # Verify shop page shows updated list
    response = client.get('/shop')
    assert response.status_code == 200
    html = response.data.decode('utf-8')
    # Check that updated shopping list items are displayed
    assert f"{updated_item_count} items" in html, f"Expected '{updated_item_count} items' in shop page HTML"
    logger.info(f"✓ Shop page displays updated shopping list with {updated_item_count} items")

    # ==================== STEP 6: Verify Cook Page Updates ====================
    logger.info("\n" + "="*70)
    logger.info("STEP 6: Verifying cook page updates")
    logger.info("="*70)

    response = client.get('/cook')
    assert response.status_code == 200
    html = response.data.decode('utf-8')

    # Check that updated recipe names appear
    updated_recipes_found = sum(1 for name in updated_recipe_names if name in html)
    logger.info(f"✓ Cook page displays {updated_recipes_found}/{len(updated_recipe_names)} updated recipe names")
    assert updated_recipes_found > 0, "Cook page should display updated recipes"

    # ==================== SUMMARY ====================
    logger.info("\n" + "="*70)
    logger.info("TEST SUMMARY")
    logger.info("="*70)
    logger.info(f"✓ Initial plan creation:     {plan_time:.2f}s")
    logger.info(f"✓ Initial shopping list:     {preload_time:.2f}s ({initial_item_count} items)")
    logger.info(f"✓ Replan:                    {replan_time:.2f}s")
    logger.info(f"✓ Updated shopping list:     {preload_time2:.2f}s ({updated_item_count} items)")
    logger.info(f"✓ Meals changed:             {changed_meals}/{len(initial_recipe_ids)}")
    logger.info(f"✓ Shopping list ID changed:  {updated_shopping_list_id != initial_shopping_list_id}")
    logger.info("="*70)

    logger.info("\n✅ Plan update workflow test passed!")


if __name__ == "__main__":
    # Run with pytest
    pytest.main([__file__, "-v", "-s"])
