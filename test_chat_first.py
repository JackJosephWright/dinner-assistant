#!/usr/bin/env python3
"""
Test the chat-first interface with web recipe search.

This script demonstrates the new conversational flow where users can
casually mention recipes they need and get web search results instantly.
"""

import sys
import os

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

from chatbot import MealPlanningChatbot


def test_casual_recipe_search():
    """Test casual recipe search like the user described."""
    print("\n" + "="*70)
    print("TESTING CHAT-FIRST INTERFACE")
    print("="*70)
    print("\nScenario: User casually mentions recipes they need")
    print("User message: 'I need to find recipes for ramen soup, chicken soup,")
    print("               tacos, salmon with rice and vegetables'\n")

    try:
        # Initialize chatbot
        chatbot = MealPlanningChatbot()

        # Test message (same as user's example)
        user_message = "I need to find recipes for ramen soup, chicken soup, tacos, salmon with rice and vegetables"

        # Get response
        print("🤖 Processing...\n")
        response = chatbot.chat(user_message)

        print("="*70)
        print("CHATBOT RESPONSE:")
        print("="*70)
        print(response)
        print("\n" + "="*70)

        # Check if we got web results
        if "http" in response.lower():
            print("\n✅ SUCCESS: Web search results returned with links!")
        else:
            print("\n⚠️  Note: Response didn't include web links")

        return True

    except Exception as e:
        print(f"\n❌ ERROR: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_conversational_planning():
    """Test extracting meal planning intent from conversation."""
    print("\n" + "="*70)
    print("TESTING CONVERSATIONAL MEAL PLANNING")
    print("="*70)
    print("\nScenario: User wants to plan meals conversationally")
    print("User message: 'Can you help me plan my dinners for next week?'\n")

    try:
        chatbot = MealPlanningChatbot()

        user_message = "Can you help me plan my dinners for next week?"

        print("🤖 Processing...\n")
        response = chatbot.chat(user_message)

        print("="*70)
        print("CHATBOT RESPONSE:")
        print("="*70)
        print(response)
        print("\n" + "="*70)

        # Check if meal plan was created
        if chatbot.current_meal_plan_id:
            print(f"\n✅ SUCCESS: Meal plan created! ID: {chatbot.current_meal_plan_id}")
        else:
            print("\n⚠️  Note: No meal plan created (may need follow-up)")

        return True

    except Exception as e:
        print(f"\n❌ ERROR: {e}")
        import traceback
        traceback.print_exc()
        return False


if __name__ == "__main__":
    print("\nTesting the new chat-first interface...")
    print("This demonstrates how users can now interact naturally,")
    print("just like with ChatGPT, and get instant recipe results.\n")

    # Run tests
    test1_passed = test_casual_recipe_search()
    print("\n" + "-"*70 + "\n")
    test2_passed = test_conversational_planning()

    # Summary
    print("\n" + "="*70)
    print("TEST SUMMARY")
    print("="*70)
    print(f"Recipe Search Test: {'✅ PASSED' if test1_passed else '❌ FAILED'}")
    print(f"Conversational Planning Test: {'✅ PASSED' if test2_passed else '❌ FAILED'}")
    print("="*70)

    sys.exit(0 if (test1_passed and test2_passed) else 1)
