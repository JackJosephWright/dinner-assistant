#!/usr/bin/env python3
"""
Test script for the new agentic agents.

Tests the LLM-powered agents that use LangGraph for reasoning.
"""

import os
import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from data.database import DatabaseInterface


def test_agentic_planning():
    """Test the agentic planning agent."""
    print("\n" + "="*70)
    print("TEST: Agentic Planning Agent")
    print("="*70)

    # Check for API key
    if not os.environ.get("ANTHROPIC_API_KEY"):
        print("⚠️  SKIPPED: ANTHROPIC_API_KEY not set")
        return False

    try:
        from agents.agentic_planning_agent import AgenticPlanningAgent

        db = DatabaseInterface(db_dir="data")
        agent = AgenticPlanningAgent(db)

        print("\n✓ Agent initialized successfully")

        # Test meal planning
        print("\n📅 Testing meal planning...")
        result = agent.plan_week(
            week_of="2025-01-20",
            num_days=3,  # Just 3 days for faster testing
        )

        if result["success"]:
            print(f"✓ Created meal plan: {result['meal_plan_id']}")
            print(f"  - Meals planned: {len(result['meals'])}")
            for meal in result["meals"]:
                print(f"    • {meal['date']}: {meal['recipe_name']}")

            # Test explanation
            print("\n📝 Testing plan explanation...")
            explanation = agent.explain_plan(result["meal_plan_id"])
            print(f"✓ Generated explanation ({len(explanation)} chars)")
            print(f"\nExplanation preview:\n{explanation[:300]}...")

            return True
        else:
            print(f"✗ Planning failed: {result.get('error')}")
            return False

    except Exception as e:
        print(f"✗ Error: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_agentic_shopping():
    """Test the agentic shopping agent."""
    print("\n" + "="*70)
    print("TEST: Agentic Shopping Agent")
    print("="*70)

    # Check for API key
    if not os.environ.get("ANTHROPIC_API_KEY"):
        print("⚠️  SKIPPED: ANTHROPIC_API_KEY not set")
        return False

    try:
        from agents.agentic_planning_agent import AgenticPlanningAgent
        from agents.agentic_shopping_agent import AgenticShoppingAgent

        db = DatabaseInterface(db_dir="data")

        # First create a meal plan
        print("\n📅 Creating test meal plan...")
        planning_agent = AgenticPlanningAgent(db)
        plan_result = planning_agent.plan_week(
            week_of="2025-01-27",
            num_days=2,  # Just 2 days for faster testing
        )

        if not plan_result["success"]:
            print(f"✗ Planning failed: {plan_result.get('error')}")
            return False

        meal_plan_id = plan_result["meal_plan_id"]
        print(f"✓ Created meal plan: {meal_plan_id}")

        # Test shopping list generation
        print("\n🛒 Testing shopping list generation...")
        shopping_agent = AgenticShoppingAgent(db)
        result = shopping_agent.create_grocery_list(meal_plan_id)

        if result["success"]:
            print(f"✓ Created shopping list: {result['grocery_list_id']}")
            print(f"  - Total items: {result['num_items']}")
            print(f"  - Store sections: {len(result['store_sections'])}")

            # Show some items
            if result["items"]:
                print(f"\n  Sample items:")
                for item in result["items"][:5]:
                    print(f"    • {item['name']}: {item['quantity']}")

            # Test formatting
            print("\n📝 Testing list formatting...")
            formatted = shopping_agent.format_shopping_list(result["grocery_list_id"])
            print(f"✓ Generated formatted list ({len(formatted)} chars)")
            print(f"\nFormatted list preview:\n{formatted[:400]}...")

            return True
        else:
            print(f"✗ Shopping list failed: {result.get('error')}")
            return False

    except Exception as e:
        print(f"✗ Error: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_agentic_cooking():
    """Test the agentic cooking agent."""
    print("\n" + "="*70)
    print("TEST: Agentic Cooking Agent")
    print("="*70)

    # Check for API key
    if not os.environ.get("ANTHROPIC_API_KEY"):
        print("⚠️  SKIPPED: ANTHROPIC_API_KEY not set")
        return False

    try:
        from agents.agentic_cooking_agent import AgenticCookingAgent

        db = DatabaseInterface(db_dir="data")
        agent = AgenticCookingAgent(db)

        print("\n✓ Agent initialized successfully")

        # Find a recipe to test with
        print("\n🔍 Finding test recipe...")
        recipes = db.search_recipes(query="chicken", limit=1)
        if not recipes:
            print("✗ No recipes found")
            return False

        recipe = recipes[0]
        print(f"✓ Using recipe: {recipe.name} (ID: {recipe.id})")

        # Test cooking guide
        print("\n👨‍🍳 Testing cooking guide...")
        result = agent.get_cooking_guide(recipe.id)

        if result["success"]:
            print(f"✓ Generated cooking guide")
            print(f"  - Tips: {len(result['tips'])}")
            print(f"  - Ingredients: {len(result['ingredients'])}")
            print(f"  - Steps: {len(result['steps'])}")

            if result["tips"]:
                print(f"\n  Sample tips:")
                for tip in result["tips"][:2]:
                    print(f"    • {tip}")

            # Test substitutions
            print("\n🔄 Testing ingredient substitutions...")
            sub_result = agent.get_substitutions("butter", reason="dairy-free")

            if sub_result["success"]:
                print(f"✓ Got {len(sub_result['substitutions'])} substitutions for butter:")
                for sub in sub_result["substitutions"][:3]:
                    print(f"    • {sub}")

            # Test formatted instructions
            print("\n📝 Testing formatted instructions...")
            formatted = agent.format_cooking_instructions(recipe.id)
            print(f"✓ Generated formatted instructions ({len(formatted)} chars)")
            print(f"\nInstructions preview:\n{formatted[:400]}...")

            return True
        else:
            print(f"✗ Cooking guide failed: {result.get('error')}")
            return False

    except Exception as e:
        print(f"✗ Error: {e}")
        import traceback
        traceback.print_exc()
        return False


def main():
    """Run all agentic agent tests."""
    print("\n" + "="*70)
    print("AGENTIC AGENTS TEST SUITE")
    print("="*70)
    print("\nThese tests require ANTHROPIC_API_KEY to be set.")

    # Check for API key
    if not os.environ.get("ANTHROPIC_API_KEY"):
        print("\n❌ ERROR: ANTHROPIC_API_KEY not set")
        print("\nTo run these tests, set your API key:")
        print("  export ANTHROPIC_API_KEY='your-key-here'")
        print("\nThese tests will use actual API calls and may incur costs.")
        sys.exit(1)

    print("\n⚠️  NOTE: These tests will make real API calls to Anthropic.")
    print("     This may take a few minutes and will incur API costs.")
    print()

    # Run tests
    results = []

    results.append(("Planning Agent", test_agentic_planning()))
    results.append(("Shopping Agent", test_agentic_shopping()))
    results.append(("Cooking Agent", test_agentic_cooking()))

    # Summary
    print("\n" + "="*70)
    print("TEST SUMMARY")
    print("="*70)

    passed = sum(1 for _, result in results if result)
    total = len(results)

    for name, result in results:
        status = "✓ PASSED" if result else "✗ FAILED"
        print(f"{status}: {name}")

    print(f"\nTotal: {passed}/{total} tests passed")

    if passed == total:
        print("\n🎉 All agentic agent tests passed!")
        sys.exit(0)
    else:
        print(f"\n❌ {total - passed} test(s) failed")
        sys.exit(1)


if __name__ == "__main__":
    main()
