#!/usr/bin/env python3
"""
Integration tests for the complete meal planning workflow.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from main import MealPlanningAssistant


def test_complete_workflow():
    """Test the complete plan → shop → cook workflow."""
    print("\n" + "="*70)
    print("INTEGRATION TEST: Complete Workflow")
    print("="*70)

    assistant = MealPlanningAssistant(db_dir="data")

    # Run complete workflow
    result = assistant.complete_workflow()

    # Verify results
    assert result["success"], f"Workflow failed: {result.get('error')}"

    assert "meal_plan_id" in result
    assert "shopping_list_id" in result

    # Check meal plan
    plan = result["plan_result"]
    assert len(plan["meals"]) > 0, "No meals in plan"
    print(f"\n✓ Meal plan has {len(plan['meals'])} meals")

    # Check shopping list
    shop = result["shop_result"]
    assert shop["num_items"] > 0, "No items in shopping list"
    print(f"✓ Shopping list has {shop['num_items']} items")

    # Check cooking guide
    cook = result["cook_result"]
    assert cook["success"], "Cooking guide failed"
    print(f"✓ Cooking guide generated for {cook['recipe_name']}")

    print("\n" + "="*70)
    print("✅ INTEGRATION TEST PASSED!")
    print("="*70)

    return result


def main():
    """Run integration tests."""
    print("\n" + "🧪 "*30)
    print("MEAL PLANNING ASSISTANT - INTEGRATION TESTS")
    print("🧪 "*30)

    try:
        result = test_complete_workflow()

        print("\n" + "="*70)
        print("✅ ALL INTEGRATION TESTS PASSED!")
        print("="*70)

        print("\nThe complete system is working:")
        print("  ✓ Planning Agent - generates meal plans")
        print("  ✓ Shopping Agent - creates grocery lists")
        print("  ✓ Cooking Agent - provides cooking guidance")
        print("  ✓ Orchestrator - coordinates all agents")

        return result

    except Exception as e:
        print(f"\n❌ TEST FAILED: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
