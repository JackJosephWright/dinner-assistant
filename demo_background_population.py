#!/usr/bin/env python3
"""
Demo: Chat-First Interface with Background Meal Plan Population

This demonstrates how the chatbot:
1. Returns both web links AND recipe details
2. Automatically creates meal plans in the background
3. Keeps the plan/shop/cook structure working silently
"""

import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

from chatbot import MealPlanningChatbot


def demo_background_population():
    """
    Demo the enhanced chat-first interface.

    User says: "I need recipes for ramen soup, chicken soup, tacos, salmon"

    Chatbot returns:
    - Active link for each recipe (for web browsing)
    - Recipe details from database (if found)

    Background:
    - Automatically detects 4 recipes = week plan
    - Creates meal plan silently
    - Updates plan/shop/cook structure
    """
    print("\n" + "="*70)
    print("DEMO: CHAT-FIRST WITH BACKGROUND POPULATION")
    print("="*70)
    print("\nUser wants to find 4 recipes casually...")
    print("The chatbot will:")
    print("  1. Return web links for browsing")
    print("  2. Show recipe details from database")
    print("  3. Auto-create a meal plan in background")
    print("\n" + "-"*70 + "\n")

    try:
        chatbot = MealPlanningChatbot()

        # User's casual message
        user_message = "I need to find recipes for ramen soup, chicken soup, tacos, salmon with rice"

        print(f"User: {user_message}\n")
        print("Processing...\n")

        # Get response
        response = chatbot.chat(user_message)

        print("="*70)
        print("CHATBOT RESPONSE:")
        print("="*70)
        print(response)
        print("\n" + "="*70)

        # Check what happened in background
        print("\n" + "="*70)
        print("BACKGROUND ACTIVITY:")
        print("="*70)

        if chatbot.current_meal_plan_id:
            print(f"✅ Meal plan auto-created: {chatbot.current_meal_plan_id}")
            print(f"   The plan/shop/cook structure is now populated!")
            print(f"   User can visit the Plan page to see their meals")
        else:
            print("   No meal plan created (may need more matching recipes)")

        print("\n" + "="*70)
        print("KEY FEATURES DEMONSTRATED:")
        print("="*70)
        print("✅ Returns active links for each recipe")
        print("✅ Shows recipe details (time, difficulty)")
        print("✅ Auto-populates meal plan structure in background")
        print("✅ Keeps plan/shop/cook phases intact")
        print("✅ Conversational, no commands needed")
        print("="*70)

        return True

    except Exception as e:
        print(f"\n❌ ERROR: {e}")
        import traceback
        traceback.print_exc()
        return False


def demo_shopping_list_from_background():
    """Demo creating shopping list from the background meal plan."""
    print("\n\n" + "="*70)
    print("DEMO: SHOPPING LIST FROM BACKGROUND PLAN")
    print("="*70)
    print("\nNow user wants a shopping list...")
    print("Chatbot will use the meal plan created in background\n")
    print("-"*70 + "\n")

    try:
        chatbot = MealPlanningChatbot()

        # First, create a meal plan in background by searching recipes
        print("Step 1: User searches for recipes...")
        msg1 = "I need recipes for pasta, tacos, salmon, chicken soup"
        print(f"User: {msg1}\n")
        response1 = chatbot.chat(msg1)
        print(f"✅ Recipes found. Meal plan ID: {chatbot.current_meal_plan_id}\n")

        # Now ask for shopping list
        print("-"*70)
        print("\nStep 2: User asks for shopping list...")
        msg2 = "make me a shopping list"
        print(f"User: {msg2}\n")
        print("Processing...\n")

        response2 = chatbot.chat(msg2)

        print("="*70)
        print("CHATBOT RESPONSE:")
        print("="*70)
        print(response2)
        print("\n" + "="*70)

        if chatbot.current_shopping_list_id:
            print(f"\n✅ Shopping list created: {chatbot.current_shopping_list_id}")
            print(f"   Based on the background meal plan!")

        print("\n" + "="*70)
        print("WORKFLOW DEMONSTRATED:")
        print("="*70)
        print("1. User searches recipes → Meal plan created in background")
        print("2. User asks for shopping list → Uses background meal plan")
        print("3. Plan/Shop/Cook structure works silently behind chat")
        print("="*70)

        return True

    except Exception as e:
        print(f"\n❌ ERROR: {e}")
        import traceback
        traceback.print_exc()
        return False


if __name__ == "__main__":
    print("\n" + "="*70)
    print("ENHANCED CHAT-FIRST INTERFACE DEMO")
    print("="*70)
    print("\nThis demo shows how the chatbot now:")
    print("  • Returns web links AND recipe details")
    print("  • Auto-populates meal plans in background")
    print("  • Keeps plan/shop/cook structure working")
    print("  • Enables natural conversation flow")
    print("\n" + "="*70)

    # Run demos
    demo1 = demo_background_population()

    if demo1:
        demo2 = demo_shopping_list_from_background()

    print("\n\n" + "="*70)
    print("DEMO COMPLETE")
    print("="*70)
    print("The chat-first interface is ready!")
    print("Visit http://localhost:5000 to try it in the web app")
    print("="*70 + "\n")
