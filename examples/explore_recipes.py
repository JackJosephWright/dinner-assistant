#!/usr/bin/env python3
"""
Interactive recipe explorer.

Demonstrates the recipe search capabilities with real queries.
"""

import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from data.database import DatabaseInterface


def print_recipe_summary(recipe):
    """Print a nice summary of a recipe."""
    print(f"\n{'='*60}")
    print(f"📗 {recipe.name}")
    print(f"{'='*60}")
    print(f"⏱️  Time: {recipe.estimated_time or 'Unknown'} minutes")
    print(f"🍽️  Servings: {recipe.servings}")
    print(f"🌟 Difficulty: {recipe.difficulty.title()}")
    if recipe.cuisine:
        print(f"🌍 Cuisine: {recipe.cuisine}")

    print(f"\n📋 Ingredients ({len(recipe.ingredients_raw)} items):")
    for i, ingredient in enumerate(recipe.ingredients_raw[:10], 1):
        print(f"  {i}. {ingredient}")
    if len(recipe.ingredients_raw) > 10:
        print(f"  ... and {len(recipe.ingredients_raw) - 10} more")

    print(f"\n👨‍🍳 Steps ({len(recipe.steps)}):")
    for i, step in enumerate(recipe.steps[:3], 1):
        step_preview = step[:80] + "..." if len(step) > 80 else step
        print(f"  {i}. {step_preview}")
    if len(recipe.steps) > 3:
        print(f"  ... and {len(recipe.steps) - 3} more steps")

    print(f"\n🏷️  Tags: {', '.join(recipe.tags[:8])}")
    if len(recipe.tags) > 8:
        print(f"       ... and {len(recipe.tags) - 8} more tags")


def explore_by_time():
    """Find quick recipes."""
    db = DatabaseInterface(db_dir="data")

    print("\n" + "="*60)
    print("🚀 QUICK RECIPES (Under 30 minutes)")
    print("="*60)

    recipes = db.search_recipes(max_time=30, limit=5)

    print(f"\nFound {len(recipes)} quick recipes:\n")
    for i, recipe in enumerate(recipes, 1):
        print(f"{i}. {recipe.name} ({recipe.estimated_time} min) - {recipe.difficulty}")


def explore_by_ingredient():
    """Search by ingredient."""
    db = DatabaseInterface(db_dir="data")

    print("\n" + "="*60)
    print("🐔 CHICKEN RECIPES")
    print("="*60)

    recipes = db.search_recipes(query="chicken", max_time=45, limit=5)

    print(f"\nFound {len(recipes)} chicken recipes under 45 minutes:\n")
    for i, recipe in enumerate(recipes, 1):
        print(f"{i}. {recipe.name}")

    if recipes:
        print("\n" + "-"*60)
        print("Full details for first recipe:")
        print_recipe_summary(recipes[0])


def explore_vegetarian():
    """Find vegetarian options."""
    db = DatabaseInterface(db_dir="data")

    print("\n" + "="*60)
    print("🥗 VEGETARIAN RECIPES")
    print("="*60)

    recipes = db.search_recipes(tags=["vegetarian"], limit=5)

    print(f"\nFound {len(recipes)} vegetarian recipes:\n")
    for i, recipe in enumerate(recipes, 1):
        print(f"{i}. {recipe.name} ({recipe.estimated_time or '?'} min)")


def explore_easy_recipes():
    """Find beginner-friendly recipes."""
    db = DatabaseInterface(db_dir="data")

    print("\n" + "="*60)
    print("✨ EASY RECIPES")
    print("="*60)

    recipes = db.search_recipes(tags=["easy"], limit=5)

    print(f"\nFound {len(recipes)} easy recipes:\n")
    for i, recipe in enumerate(recipes, 1):
        print(f"{i}. {recipe.name}")
        if recipe.estimated_time:
            print(f"   Time: {recipe.estimated_time} min")


def view_meal_history():
    """Show recent meal history."""
    db = DatabaseInterface(db_dir="data")

    print("\n" + "="*60)
    print("📅 YOUR MEAL HISTORY (Last 4 Weeks)")
    print("="*60)

    history = db.get_meal_history(weeks_back=4)

    print(f"\nYou've logged {len(history)} meals:\n")

    # Group by week
    from collections import defaultdict
    by_week = defaultdict(list)

    for meal in history:
        # Extract week from date
        from datetime import datetime
        date = datetime.fromisoformat(meal.date)
        week_num = date.isocalendar()[1]
        by_week[week_num].append(meal)

    for week_num in sorted(by_week.keys(), reverse=True)[:4]:
        meals = by_week[week_num]
        print(f"\nWeek {week_num}:")
        for meal in meals[:7]:  # Show up to 7 days
            print(f"  • {meal.recipe_name}")


def search_by_your_favorites():
    """Search for recipes similar to your favorites."""
    db = DatabaseInterface(db_dir="data")

    print("\n" + "="*60)
    print("❤️  RECIPES SIMILAR TO YOUR FAVORITES")
    print("="*60)

    # Based on your history, you like:
    # - Salmon dishes
    # - Tacos
    # - Pasta/spaghetti
    # - Tofu dishes

    print("\nSearching for salmon recipes...")
    salmon = db.search_recipes(query="salmon", max_time=45, limit=3)

    print("\nSearching for taco recipes...")
    tacos = db.search_recipes(query="taco", limit=3)

    print("\nSearching for pasta recipes...")
    pasta = db.search_recipes(query="pasta", max_time=45, limit=3)

    print("\n🐟 Salmon Options:")
    for recipe in salmon:
        print(f"  • {recipe.name} ({recipe.estimated_time or '?'} min)")

    print("\n🌮 Taco Options:")
    for recipe in tacos:
        print(f"  • {recipe.name}")

    print("\n🍝 Pasta Options:")
    for recipe in pasta:
        print(f"  • {recipe.name} ({recipe.estimated_time or '?'} min)")


def main():
    """Run all explorations."""
    print("\n" + "🍽️ "*20)
    print("MEAL PLANNING ASSISTANT - RECIPE EXPLORER")
    print("🍽️ "*20)

    try:
        # Run different explorations
        view_meal_history()
        explore_by_time()
        explore_by_ingredient()
        explore_vegetarian()
        explore_easy_recipes()
        search_by_your_favorites()

        print("\n" + "="*60)
        print("✅ Exploration complete!")
        print("="*60)
        print("\nYour recipe database has 492,630 recipes ready to explore.")
        print("Try modifying this script to search for your favorite ingredients!")

    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()
