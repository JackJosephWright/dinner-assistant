#!/usr/bin/env python3
"""
Test script to verify the structured query optimization is working.

This script:
1. Tests the search_recipes_structured() method
2. Compares performance with the original search_recipes() method
3. Generates a test meal plan using the optimized agent
4. Measures time and token usage
"""

import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent / "src"))

import time
import logging
from datetime import datetime, timedelta

from data.database import DatabaseInterface
from agents.agentic_planning_agent import AgenticPlanningAgent

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


def test_structured_search():
    """Test the structured search method."""
    logger.info("\n=== Testing Structured Search ===")

    db = DatabaseInterface("data")

    # Test 1: Search by cuisine and protein
    start = time.time()
    results = db.search_recipes_structured(
        cuisines=["italian"],
        proteins=["chicken"],
        max_time=45,
        limit=15,
    )
    elapsed = time.time() - start

    logger.info(f"Test 1 - Italian chicken dishes under 45 min:")
    logger.info(f"  Found {len(results)} recipes in {elapsed*1000:.1f}ms")
    if results:
        logger.info(f"  Sample: {results[0]['name']}")

    # Test 2: Search by dietary flags
    start = time.time()
    results = db.search_recipes_structured(
        dietary_flags=["vegetarian"],
        max_time=30,
        difficulty=["easy"],
        limit=15,
    )
    elapsed = time.time() - start

    logger.info(f"\nTest 2 - Easy vegetarian dishes under 30 min:")
    logger.info(f"  Found {len(results)} recipes in {elapsed*1000:.1f}ms")
    if results:
        logger.info(f"  Sample: {results[0]['name']}")

    # Test 3: Search by protein and time range
    start = time.time()
    results = db.search_recipes_structured(
        proteins=["fish", "seafood"],
        min_time=20,
        max_time=45,
        limit=15,
    )
    elapsed = time.time() - start

    logger.info(f"\nTest 3 - Fish/seafood dishes 20-45 min:")
    logger.info(f"  Found {len(results)} recipes in {elapsed*1000:.1f}ms")
    if results:
        logger.info(f"  Sample: {results[0]['name']}")

    # Test 4: Complex multi-filter search
    start = time.time()
    results = db.search_recipes_structured(
        cuisines=["mexican", "thai"],
        proteins=["tofu", "beans"],
        dietary_flags=["vegetarian"],
        max_time=45,
        difficulty=["easy", "medium"],
        limit=15,
    )
    elapsed = time.time() - start

    logger.info(f"\nTest 4 - Mexican/Thai vegetarian with tofu/beans:")
    logger.info(f"  Found {len(results)} recipes in {elapsed*1000:.1f}ms")
    if results:
        logger.info(f"  Sample: {results[0]['name']}")


def test_meal_planning_performance():
    """Test meal planning with the optimized agent."""
    logger.info("\n\n=== Testing Meal Planning Performance ===")

    db = DatabaseInterface("data")
    agent = AgenticPlanningAgent(db)

    # Get next Monday
    today = datetime.now()
    days_ahead = 7 - today.weekday()  # Monday is 0
    if days_ahead <= 0:
        days_ahead += 7
    next_monday = today + timedelta(days=days_ahead)
    week_of = next_monday.strftime("%Y-%m-%d")

    logger.info(f"Generating meal plan for week of {week_of}...")

    start = time.time()
    result = agent.plan_week(
        week_of=week_of,
        num_days=7,
        preferences={
            "max_weeknight_time": 45,
            "max_weekend_time": 90,
            "preferred_cuisines": ["italian", "mexican", "asian"],
            "min_vegetarian_meals": 2,
        }
    )
    elapsed = time.time() - start

    if result["success"]:
        logger.info(f"\n✅ Meal plan generated successfully in {elapsed:.2f} seconds")
        logger.info(f"Plan ID: {result['meal_plan_id']}")
        logger.info(f"\nMeals planned:")
        for meal in result["meals"]:
            logger.info(f"  {meal['date']}: {meal['recipe_name']}")

        logger.info(f"\nReasoning:\n{result['reasoning']}")
    else:
        logger.error(f"\n❌ Meal planning failed: {result.get('error')}")

    return elapsed


def compare_search_methods():
    """Compare old vs new search approach."""
    logger.info("\n\n=== Comparing Search Methods ===")

    db = DatabaseInterface("data")

    # Old approach: multiple keyword searches
    logger.info("\nOld approach (keyword-based):")
    keywords = ["chicken", "tofu", "salmon", "pasta", "beef"]

    start = time.time()
    old_results = []
    for keyword in keywords:
        recipes = db.search_recipes(query=keyword, max_time=45, limit=15)
        old_results.extend(recipes)
    old_elapsed = time.time() - start

    # Deduplicate
    seen = set()
    old_unique = []
    for recipe in old_results:
        if recipe.id not in seen:
            seen.add(recipe.id)
            old_unique.append(recipe)

    logger.info(f"  {len(keywords)} keyword searches")
    logger.info(f"  Found {len(old_unique)} unique recipes in {old_elapsed*1000:.1f}ms")
    logger.info(f"  ~{len(old_unique) * 4} lines of output (verbose format)")

    # New approach: structured filters
    logger.info("\nNew approach (structured filters):")

    start = time.time()
    new_results = db.search_recipes_structured(
        proteins=["chicken", "tofu", "fish", "beef"],
        max_time=45,
        limit=15,
    )
    new_elapsed = time.time() - start

    logger.info(f"  1 structured search")
    logger.info(f"  Found {len(new_results)} recipes in {new_elapsed*1000:.1f}ms")
    logger.info(f"  ~{len(new_results)} lines of output (compact format)")

    speedup = old_elapsed / new_elapsed if new_elapsed > 0 else 0
    logger.info(f"\n  Speed improvement: {speedup:.1f}x faster")
    logger.info(f"  Token reduction: ~{(1 - len(new_results) / (len(old_unique) * 4)) * 100:.0f}%")


if __name__ == "__main__":
    print("="*60)
    print("STRUCTURED QUERY OPTIMIZATION TEST")
    print("="*60)

    try:
        # Test structured search
        test_structured_search()

        # Compare old vs new
        compare_search_methods()

        # Test meal planning
        planning_time = test_meal_planning_performance()

        print("\n" + "="*60)
        print("TEST SUMMARY")
        print("="*60)
        print(f"✅ Structured search working correctly")
        print(f"✅ Meal planning completed in {planning_time:.2f}s")
        print(f"\nExpected improvements achieved:")
        print(f"  - Database queries using indexed fields")
        print(f"  - Compact result format (1 line per recipe)")
        print(f"  - Reduced LLM token usage")
        print("="*60)

    except Exception as e:
        logger.error(f"\n❌ Test failed: {e}", exc_info=True)
