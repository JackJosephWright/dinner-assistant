"""
Test vertical slice: search recipes through the database interface.

This tests the core flow without needing the full MCP/LangGraph setup.
"""

import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from src.data.database import DatabaseInterface
from src.data.models import Recipe


def test_database_connection():
    """Test that we can connect to the database."""
    print("Testing database connection...")

    db = DatabaseInterface(db_dir="data")

    # Test recipes database
    print("\nTesting recipe search...")
    recipes = db.search_recipes(query="chicken", max_time=30, limit=5)

    print(f"Found {len(recipes)} chicken recipes under 30 minutes:")
    for recipe in recipes:
        print(f"  - {recipe.name} ({recipe.estimated_time} min)")
        print(f"    Tags: {', '.join(recipe.tags[:5])}...")
        print(f"    Cuisine: {recipe.cuisine}, Difficulty: {recipe.difficulty}")
        print()

    assert len(recipes) > 0, "Should find at least one recipe"

    # Test meal history
    print("Testing meal history...")
    history = db.get_meal_history(weeks_back=4)

    print(f"\nFound {len(history)} meals in history:")
    for meal in history[:10]:
        print(f"  - {meal.recipe_name} on {meal.date}")

    assert len(history) > 0, "Should have meal history"

    print("\n✓ Database tests passed!")


def test_recipe_search_filters():
    """Test various recipe search filters."""
    print("\n" + "=" * 50)
    print("Testing recipe search with filters...")
    print("=" * 50)

    db = DatabaseInterface(db_dir="data")

    # Test 1: Search by time
    print("\n1. Recipes under 15 minutes:")
    quick_recipes = db.search_recipes(max_time=15, limit=5)
    for recipe in quick_recipes:
        print(f"  - {recipe.name} ({recipe.estimated_time} min)")

    # Test 2: Search by tags
    print("\n2. Easy recipes:")
    easy_recipes = db.search_recipes(tags=["easy"], limit=5)
    for recipe in easy_recipes:
        print(f"  - {recipe.name} (Difficulty: {recipe.difficulty})")

    # Test 3: Search by keyword
    print("\n3. Salmon recipes:")
    salmon_recipes = db.search_recipes(query="salmon", limit=5)
    for recipe in salmon_recipes:
        print(f"  - {recipe.name}")

    # Test 4: Get full recipe details
    if salmon_recipes:
        print("\n4. Full recipe details for first salmon recipe:")
        recipe = salmon_recipes[0]
        print(f"  Name: {recipe.name}")
        print(f"  Description: {recipe.description[:100]}...")
        print(f"  Servings: {recipe.servings}")
        print(f"  Ingredients: {len(recipe.ingredients)} items")
        print(f"    First 3: {recipe.ingredients_raw[:3]}")
        print(f"  Steps: {len(recipe.steps)} steps")

    print("\n✓ Search filter tests passed!")


def test_preferences():
    """Test user preferences."""
    print("\n" + "=" * 50)
    print("Testing preferences...")
    print("=" * 50)

    db = DatabaseInterface(db_dir="data")

    # Set some preferences
    db.set_preference("max_weeknight_time", "45")
    db.set_preference("preferred_cuisines", "italian,mexican,thai")

    # Get preferences
    prefs = db.get_all_preferences()
    print(f"\nUser preferences: {prefs}")

    assert "max_weeknight_time" in prefs
    print("\n✓ Preferences tests passed!")


def main():
    """Run all vertical slice tests."""
    print("\n" + "=" * 70)
    print("VERTICAL SLICE TEST: Database → Search → Results")
    print("=" * 70)

    try:
        test_database_connection()
        test_recipe_search_filters()
        test_preferences()

        print("\n" + "=" * 70)
        print("✓ ALL TESTS PASSED!")
        print("=" * 70)
        print("\nThe vertical slice is working! You can now:")
        print("  1. Search recipes by various criteria")
        print("  2. Access meal history")
        print("  3. Store and retrieve preferences")
        print("\nNext steps: Integrate with MCP server and Planning Agent")

    except Exception as e:
        print(f"\n✗ TEST FAILED: {e}")
        import traceback

        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
