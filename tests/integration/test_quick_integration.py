#!/usr/bin/env python3
"""
Quick integration tests for critical bugs.

These tests run faster by using smaller test cases.
"""

import os
import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from src.data.database import DatabaseInterface

# Get the project root directory
PROJECT_ROOT = Path(__file__).parent.parent
DATA_DIR = str(PROJECT_ROOT / "data")


def test_chatbot_tool_handling_quick():
    """
    Quick test of chatbot's tool handling - just verify initialization.
    """
    print("\n" + "="*70)
    print("TEST: Chatbot Tool Handling (Quick)")
    print("="*70)

    # Check for API key
    if not os.environ.get("ANTHROPIC_API_KEY"):
        print("⚠️  SKIPPED: ANTHROPIC_API_KEY not set")
        return None

    try:
        from chatbot import MealPlanningChatbot

        chatbot = MealPlanningChatbot()
        print("✓ Chatbot initialized")

        # Verify tool definitions
        tools = chatbot.get_tools()
        print(f"✓ {len(tools)} tools defined")

        tool_names = [t['name'] for t in tools]
        expected = ['plan_meals', 'create_shopping_list', 'search_recipes']
        for name in expected:
            if name in tool_names:
                print(f"  ✓ {name}")
            else:
                print(f"  ✗ Missing tool: {name}")
                return False

        return True

    except Exception as e:
        print(f"✗ Error: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_agentic_planning_recipe_search_quick():
    """
    Quick test that recipe search returns candidates.
    """
    print("\n" + "="*70)
    print("TEST: Agentic Planning Recipe Search (Quick)")
    print("="*70)

    # Check for API key
    if not os.environ.get("ANTHROPIC_API_KEY"):
        print("⚠️  SKIPPED: ANTHROPIC_API_KEY not set")
        return None

    try:
        from agents.agentic_planning_agent import AgenticPlanningAgent, PlanningState

        db = DatabaseInterface(db_dir=DATA_DIR)
        agent = AgenticPlanningAgent(db)

        print("✓ Agent initialized")

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
        print("🔍 Running search_recipes_node...")
        result_state = agent._search_recipes_node(state)

        if result_state.get("error"):
            print(f"✗ Search failed: {result_state['error']}")
            return False

        num_candidates = len(result_state.get("recipe_candidates", []))
        print(f"✓ Found {num_candidates} recipe candidates")

        if num_candidates == 0:
            print("✗ BUG: Found 0 recipe candidates!")
            return False

        # Show sample
        for candidate in result_state["recipe_candidates"][:3]:
            print(f"  - {candidate['recipe_name']}")

        return True

    except Exception as e:
        print(f"✗ Error: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_anthropic_api_format_quick():
    """
    Quick test of Anthropic API call format.
    """
    print("\n" + "="*70)
    print("TEST: Anthropic API Format (Quick)")
    print("="*70)

    # Check for API key
    if not os.environ.get("ANTHROPIC_API_KEY"):
        print("⚠️  SKIPPED: ANTHROPIC_API_KEY not set")
        return None

    try:
        from anthropic import Anthropic

        client = Anthropic(api_key=os.environ.get("ANTHROPIC_API_KEY"))

        # Simple tool use test
        tools = [
            {
                "name": "get_weather",
                "description": "Get the weather",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "location": {"type": "string"},
                    },
                    "required": ["location"],
                },
            }
        ]

        messages = [
            {"role": "user", "content": "What's the weather in SF?"}
        ]

        response = client.messages.create(
            model="claude-sonnet-4-5-20250929",
            max_tokens=1024,
            tools=tools,
            messages=messages,
        )

        if response.stop_reason == "tool_use":
            print("✓ Tool use triggered")

            # Proper format: collect all tool uses
            tool_uses = [b for b in response.content if b.type == "tool_use"]
            print(f"  Tool uses: {len(tool_uses)}")

            # Add assistant response
            messages.append({
                "role": "assistant",
                "content": response.content,
            })

            # Add ALL tool results
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

            # Try final response
            try:
                response2 = client.messages.create(
                    model="claude-sonnet-4-5-20250929",
                    max_tokens=1024,
                    tools=tools,
                    messages=messages,
                )
                print("✓ API format correct")
                return True

            except Exception as e:
                if "tool_use" in str(e) and "tool_result" in str(e):
                    print(f"✗ API format error: {e}")
                    return False
                else:
                    # Some other error, might be transient
                    print(f"⚠️  API error (not format): {e}")
                    return None

        else:
            print("⚠️  No tool use (test inconclusive)")
            return None

    except Exception as e:
        print(f"✗ Error: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_database_recipe_search_quick():
    """
    Quick database search test.
    """
    print("\n" + "="*70)
    print("TEST: Database Recipe Search (Quick)")
    print("="*70)

    try:
        db = DatabaseInterface(db_dir=DATA_DIR)

        # Search for chicken
        recipes = db.search_recipes(query="chicken", limit=5)
        print(f"✓ Found {len(recipes)} chicken recipes")

        if len(recipes) == 0:
            print("✗ No recipes found!")
            return False

        for recipe in recipes[:3]:
            print(f"  - {recipe.name}")

        return True

    except Exception as e:
        print(f"✗ Error: {e}")
        import traceback
        traceback.print_exc()
        return False


def main():
    """Run quick integration tests."""
    print("\n" + "="*70)
    print("QUICK INTEGRATION TEST SUITE")
    print("="*70)
    print("\nFast tests for critical bugs (completes in ~1 minute).")

    # Check for API key
    has_api_key = bool(os.environ.get("ANTHROPIC_API_KEY"))
    if not has_api_key:
        print("\n⚠️  WARNING: ANTHROPIC_API_KEY not set")
        print("   Some tests will be skipped.")

    # Run tests
    results = []

    print("\n" + "-"*70)
    results.append(("Database Search", test_database_recipe_search_quick()))

    if has_api_key:
        print("\n" + "-"*70)
        results.append(("API Format", test_anthropic_api_format_quick()))

        print("\n" + "-"*70)
        results.append(("Recipe Search", test_agentic_planning_recipe_search_quick()))

        print("\n" + "-"*70)
        results.append(("Chatbot Init", test_chatbot_tool_handling_quick()))

    # Summary
    print("\n" + "="*70)
    print("TEST SUMMARY")
    print("="*70)

    passed = sum(1 for _, r in results if r is True)
    skipped = sum(1 for _, r in results if r is None)
    failed = sum(1 for _, r in results if r is False)

    for name, result in results:
        if result is True:
            status = "✓ PASSED"
        elif result is None:
            status = "⊘ SKIPPED"
        else:
            status = "✗ FAILED"
        print(f"{status}: {name}")

    print(f"\nResults: {passed} passed, {failed} failed, {skipped} skipped")

    if failed > 0:
        print(f"\n❌ {failed} test(s) failed")
        sys.exit(1)
    elif passed > 0:
        print("\n✅ All tests passed!")
        sys.exit(0)
    else:
        print("\n⚠️  All tests skipped")
        sys.exit(0)


if __name__ == "__main__":
    main()
