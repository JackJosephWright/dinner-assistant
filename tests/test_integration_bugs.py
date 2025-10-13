#!/usr/bin/env python3
"""
Integration tests to identify and verify bug fixes.

These tests are designed to catch real-world integration issues
between components, especially around API usage and tool handling.
"""

import os
import sys
from pathlib import Path
from datetime import datetime, timedelta
import json

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from data.database import DatabaseInterface

# Get the project root directory
PROJECT_ROOT = Path(__file__).parent.parent
DATA_DIR = str(PROJECT_ROOT / "data")


def test_chatbot_tool_handling():
    """
    Test chatbot's tool use and tool result handling.

    This catches the bug where multiple tool_use blocks aren't properly
    matched with their tool_result blocks.
    """
    print("\n" + "="*70)
    print("TEST: Chatbot Tool Handling")
    print("="*70)

    # Check for API key
    if not os.environ.get("ANTHROPIC_API_KEY"):
        print("⚠️  SKIPPED: ANTHROPIC_API_KEY not set")
        return None

    try:
        from chatbot import MealPlanningChatbot

        chatbot = MealPlanningChatbot()
        print("\n✓ Chatbot initialized")

        # Test 1: Simple tool use (plan_meals)
        print("\n📋 Test 1: Planning meals with chatbot...")
        try:
            response = chatbot.chat("Plan meals for next week")
            print(f"✓ Chat response received ({len(response)} chars)")

            # Check if a meal plan was created
            if chatbot.current_meal_plan_id:
                print(f"✓ Meal plan created: {chatbot.current_meal_plan_id}")
            else:
                print("⚠️  No meal plan ID set - may indicate issue")

        except Exception as e:
            print(f"✗ Chat failed: {e}")
            import traceback
            traceback.print_exc()
            return False

        # Test 2: Multiple sequential tool uses
        print("\n🛒 Test 2: Creating shopping list (sequential tool use)...")
        try:
            response = chatbot.chat("Create a shopping list from this meal plan")
            print(f"✓ Chat response received ({len(response)} chars)")

            if chatbot.current_shopping_list_id:
                print(f"✓ Shopping list created: {chatbot.current_shopping_list_id}")
            else:
                print("⚠️  No shopping list ID set")

        except Exception as e:
            print(f"✗ Chat failed: {e}")
            import traceback
            traceback.print_exc()
            return False

        # Test 3: Recipe search (verify no errors)
        print("\n🔍 Test 3: Searching recipes...")
        try:
            response = chatbot.chat("Find me some quick chicken recipes under 30 minutes")
            print(f"✓ Chat response received ({len(response)} chars)")

        except Exception as e:
            print(f"✗ Chat failed: {e}")
            import traceback
            traceback.print_exc()
            return False

        print("\n✓ All chatbot tool handling tests passed")
        return True

    except Exception as e:
        print(f"✗ Error: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_agentic_planning_recipe_search():
    """
    Test that agentic planning agent can find recipe candidates.

    Catches the "Found 0 recipe candidates" bug.
    """
    print("\n" + "="*70)
    print("TEST: Agentic Planning Recipe Search")
    print("="*70)

    # Check for API key
    if not os.environ.get("ANTHROPIC_API_KEY"):
        print("⚠️  SKIPPED: ANTHROPIC_API_KEY not set")
        return None

    try:
        from agents.agentic_planning_agent import AgenticPlanningAgent

        db = DatabaseInterface(db_dir=DATA_DIR)
        agent = AgenticPlanningAgent(db)

        print("\n✓ Agent initialized")

        # Test the search_recipes_node directly
        print("\n🔍 Testing recipe search via planning state...")

        from agents.agentic_planning_agent import PlanningState

        # Create a test state
        state = PlanningState(
            week_of="2025-01-20",
            num_days=3,
            preferences={
                "max_weeknight_time": 45,
                "max_weekend_time": 90,
                "preferred_cuisines": ["italian", "mexican", "asian"],
                "min_vegetarian_meals": 1,
            },
            history_summary="User enjoys variety",
            recent_meals=["Salmon Pasta", "Chicken Stir Fry"],
            favorite_patterns="Likes quick weeknight meals",
            recipe_candidates=[],
            selected_meals=[],
            reasoning="",
            error=None,
        )

        # Execute search node
        print("   Running search_recipes_node...")
        result_state = agent._search_recipes_node(state)

        if result_state.get("error"):
            print(f"✗ Search failed with error: {result_state['error']}")
            return False

        num_candidates = len(result_state.get("recipe_candidates", []))
        print(f"   Found {num_candidates} recipe candidates")

        if num_candidates == 0:
            print("✗ BUG: Found 0 recipe candidates!")
            print("   This indicates the search logic is broken")
            return False

        print(f"✓ Recipe search working ({num_candidates} candidates found)")

        # Show sample candidates
        print("\n   Sample candidates:")
        for candidate in result_state["recipe_candidates"][:5]:
            print(f"   - {candidate['recipe_name']} ({candidate['search_keyword']})")

        return True

    except Exception as e:
        print(f"✗ Error: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_full_planning_workflow():
    """
    Integration test for complete planning workflow.

    Tests analyze_history -> search_recipes -> select_meals pipeline.
    """
    print("\n" + "="*70)
    print("TEST: Full Planning Workflow")
    print("="*70)

    # Check for API key
    if not os.environ.get("ANTHROPIC_API_KEY"):
        print("⚠️  SKIPPED: ANTHROPIC_API_KEY not set")
        return None

    try:
        from agents.agentic_planning_agent import AgenticPlanningAgent

        db = DatabaseInterface(db_dir=DATA_DIR)
        agent = AgenticPlanningAgent(db)

        print("\n✓ Agent initialized")

        # Test complete workflow
        print("\n📅 Running complete planning workflow...")
        result = agent.plan_week(
            week_of="2025-01-20",
            num_days=3,
        )

        if not result["success"]:
            print(f"✗ Planning failed: {result.get('error')}")
            return False

        print(f"✓ Plan created: {result['meal_plan_id']}")
        print(f"   Meals planned: {len(result['meals'])}")

        for meal in result["meals"]:
            print(f"   - {meal['date']}: {meal['recipe_name']}")

        # Verify reasoning is present
        if result.get("reasoning"):
            print(f"\n✓ Reasoning provided ({len(result['reasoning'])} chars)")
        else:
            print("⚠️  No reasoning in result")

        return True

    except Exception as e:
        print(f"✗ Error: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_database_recipe_search():
    """
    Test basic database recipe search functionality.

    Verifies that the database layer is working correctly.
    """
    print("\n" + "="*70)
    print("TEST: Database Recipe Search")
    print("="*70)

    try:
        db = DatabaseInterface(db_dir=DATA_DIR)

        # Test 1: Simple keyword search
        print("\n🔍 Test 1: Search for 'chicken'...")
        recipes = db.search_recipes(query="chicken", limit=10)
        print(f"   Found {len(recipes)} recipes")

        if len(recipes) == 0:
            print("✗ No chicken recipes found - database may be empty")
            return False

        print(f"✓ Database search working ({len(recipes)} recipes)")
        for recipe in recipes[:3]:
            print(f"   - {recipe.name}")

        # Test 2: Search with time constraint
        print("\n⏱️  Test 2: Search for quick meals (< 30 min)...")
        recipes = db.search_recipes(query="pasta", max_time=30, limit=10)
        print(f"   Found {len(recipes)} quick pasta recipes")

        if len(recipes) > 0:
            print(f"✓ Time-constrained search working")
            for recipe in recipes[:3]:
                time_str = f"{recipe.estimated_time} min" if recipe.estimated_time else "?"
                print(f"   - {recipe.name} ({time_str})")
        else:
            print("⚠️  No quick pasta recipes found")

        # Test 3: Multiple searches (simulating agent behavior)
        print("\n🔄 Test 3: Multiple diverse searches...")
        search_queries = [
            ("chicken", 45),
            ("salmon", 45),
            ("vegetarian", 45),
            ("pasta", 30),
        ]

        total_found = 0
        for query, max_time in search_queries:
            recipes = db.search_recipes(query=query, max_time=max_time, limit=5)
            total_found += len(recipes)
            print(f"   '{query}' (< {max_time}min): {len(recipes)} recipes")

        if total_found == 0:
            print("✗ No recipes found across all searches!")
            return False

        print(f"✓ Multiple searches found {total_found} total recipes")

        return True

    except Exception as e:
        print(f"✗ Error: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_anthropic_api_call_format():
    """
    Test that API calls to Anthropic are formatted correctly.

    This specifically checks for the tool_use/tool_result matching bug.
    """
    print("\n" + "="*70)
    print("TEST: Anthropic API Call Format")
    print("="*70)

    # Check for API key
    if not os.environ.get("ANTHROPIC_API_KEY"):
        print("⚠️  SKIPPED: ANTHROPIC_API_KEY not set")
        return None

    try:
        from anthropic import Anthropic

        client = Anthropic(api_key=os.environ.get("ANTHROPIC_API_KEY"))

        # Test 1: Simple tool use
        print("\n🔧 Test 1: Single tool use...")

        tools = [
            {
                "name": "get_weather",
                "description": "Get the weather for a location",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "location": {"type": "string", "description": "City name"},
                    },
                    "required": ["location"],
                },
            }
        ]

        messages = [
            {"role": "user", "content": "What's the weather in San Francisco?"}
        ]

        response = client.messages.create(
            model="claude-sonnet-4-5-20250929",
            max_tokens=1024,
            tools=tools,
            messages=messages,
        )

        if response.stop_reason == "tool_use":
            print("✓ Tool use triggered")

            # Get tool use blocks
            tool_uses = [block for block in response.content if block.type == "tool_use"]
            print(f"   Tool uses: {len(tool_uses)}")

            # Now construct tool results properly
            messages.append({
                "role": "assistant",
                "content": response.content,  # This should be the ENTIRE response.content
            })

            # Add tool results
            tool_results = []
            for tool_use in tool_uses:
                tool_results.append({
                    "type": "tool_result",
                    "tool_use_id": tool_use.id,
                    "content": "Sunny, 72°F",
                })

            messages.append({
                "role": "user",
                "content": tool_results,
            })

            # Try to get final response
            try:
                response2 = client.messages.create(
                    model="claude-sonnet-4-5-20250929",
                    max_tokens=1024,
                    tools=tools,
                    messages=messages,
                )
                print("✓ API call succeeded with proper tool_result format")
                return True

            except Exception as e:
                print(f"✗ API call failed: {e}")
                return False
        else:
            print("⚠️  No tool use triggered")
            return None

    except Exception as e:
        print(f"✗ Error: {e}")
        import traceback
        traceback.print_exc()
        return False


def main():
    """Run all integration tests."""
    print("\n" + "="*70)
    print("INTEGRATION TEST SUITE - Bug Detection")
    print("="*70)
    print("\nThese tests identify real integration bugs and verify fixes.")

    # Check for API key
    has_api_key = bool(os.environ.get("ANTHROPIC_API_KEY"))
    if not has_api_key:
        print("\n⚠️  WARNING: ANTHROPIC_API_KEY not set")
        print("   Some tests will be skipped.")

    # Run tests
    results = []

    print("\n" + "-"*70)
    results.append(("Database Recipe Search", test_database_recipe_search()))

    if has_api_key:
        print("\n" + "-"*70)
        results.append(("Anthropic API Format", test_anthropic_api_call_format()))

        print("\n" + "-"*70)
        results.append(("Agentic Planning Recipe Search", test_agentic_planning_recipe_search()))

        print("\n" + "-"*70)
        results.append(("Full Planning Workflow", test_full_planning_workflow()))

        print("\n" + "-"*70)
        results.append(("Chatbot Tool Handling", test_chatbot_tool_handling()))

    # Summary
    print("\n" + "="*70)
    print("TEST SUMMARY")
    print("="*70)

    passed = sum(1 for _, result in results if result is True)
    skipped = sum(1 for _, result in results if result is None)
    failed = sum(1 for _, result in results if result is False)
    total = len(results)

    for name, result in results:
        if result is True:
            status = "✓ PASSED"
        elif result is None:
            status = "⊘ SKIPPED"
        else:
            status = "✗ FAILED"
        print(f"{status}: {name}")

    print(f"\nResults: {passed} passed, {failed} failed, {skipped} skipped (total: {total})")

    if failed > 0:
        print(f"\n❌ {failed} test(s) failed - bugs detected!")
        print("\nFailed tests indicate bugs that need fixing.")
        sys.exit(1)
    elif passed > 0:
        print("\n✅ All tests passed!")
        sys.exit(0)
    else:
        print("\n⚠️  All tests skipped")
        sys.exit(0)


if __name__ == "__main__":
    main()
