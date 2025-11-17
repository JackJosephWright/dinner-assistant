#!/usr/bin/env python3
"""
Test Cook tab with embedded recipes and SSE updates.
Verifies the 0-query architecture and dynamic updates.
"""

from playwright.sync_api import sync_playwright
import time

def test_cook_tab_final():
    """Test Cook tab uses embedded recipes and SSE updates work."""

    with sync_playwright() as p:
        # Launch browser in headed mode
        browser = p.chromium.launch(headless=False, slow_mo=400)

        # Create two pages (Plan tab and Cook tab)
        plan_tab = browser.new_page()
        cook_tab = browser.new_page()

        print("=" * 70)
        print("🧪 TESTING COOK TAB: EMBEDDED RECIPES + SSE UPDATES")
        print("=" * 70)

        # Step 1: Open Plan tab and ensure there's a meal plan
        print("\n📋 Step 1: Setting up meal plan...")
        plan_tab.goto('http://localhost:5000', wait_until='domcontentloaded')
        plan_tab.wait_for_timeout(3000)

        # Check if there's a meal plan, create one if not
        clear_button = plan_tab.locator('button:has-text("Clear Plan")').first
        if not clear_button.is_visible(timeout=2000):
            print("   📝 No plan exists, creating one...")
            chat_input = plan_tab.locator('input[placeholder*="Type your message"]').first
            chat_input.fill("Plan 3 meals for the week")
            plan_tab.wait_for_timeout(500)
            send_button = plan_tab.locator('button[type="submit"]').first
            send_button.click()
            plan_tab.wait_for_timeout(60000)  # Wait for plan creation

        print("   ✅ Meal plan ready")

        # Step 2: Open Cook tab
        print("\n👨‍🍳 Step 2: Opening Cook tab...")
        cook_tab.goto('http://localhost:5000/cook', wait_until='domcontentloaded')
        cook_tab.wait_for_timeout(2000)

        # Count meals
        meal_cards = cook_tab.locator('.cursor-pointer.p-4').count()
        print(f"   ✅ Cook tab loaded with {meal_cards} meals")

        # Step 3: Test embedded recipe loading (0-query architecture)
        print("\n📦 Step 3: Testing embedded recipe display...")

        # Set up console listener to catch the log message
        console_logs = []
        cook_tab.on('console', lambda msg: console_logs.append(msg.text))

        # Click on first meal card
        first_meal = cook_tab.locator('.cursor-pointer.p-4').first
        if first_meal.is_visible():
            meal_name = first_meal.locator('h3').text_content()
            print(f"   🎯 Clicking meal: {meal_name}")
            first_meal.click()
            cook_tab.wait_for_timeout(1000)

            # Check console for "Using embedded recipe data"
            embedded_logs = [log for log in console_logs if '0 queries' in log or 'embedded' in log.lower()]
            if embedded_logs:
                print(f"   ✅ EMBEDDED RECIPE USED: {embedded_logs[0]}")
                print("   🎉 0-query architecture working!")
            else:
                print("   ⚠️  No embedded recipe log found")
                print("   Recent console logs:", console_logs[-3:] if console_logs else "None")

            # Check that recipe details are displayed
            recipe_details = cook_tab.locator('#recipeDetails')
            if recipe_details.is_visible(timeout=3000):
                # Get recipe name from displayed recipe
                displayed_name = cook_tab.locator('#recipeDetails h2').text_content()
                print(f"   📖 Recipe displayed: {displayed_name}")
                print("   ✅ Recipe details loaded")
            else:
                print("   ⚠️  Recipe details not visible")

        cook_tab.screenshot(path='/tmp/cook_tab_recipe.png', full_page=True)

        # Step 4: Test SSE dynamic updates
        print("\n📡 Step 4: Testing SSE dynamic updates...")

        # Clear console logs
        console_logs.clear()

        # Swap a meal in Plan tab
        print("   🔄 Swapping meal in Plan tab...")
        plan_tab.bring_to_front()

        # Try chat-based swap
        chat_input = plan_tab.locator('input[placeholder*="Type your message"]').first
        chat_input.fill("Swap Monday for something different")
        plan_tab.wait_for_timeout(500)
        send_button = plan_tab.locator('button[type="submit"]').first
        send_button.click()

        print("   ⏳ Waiting for SSE event in Cook tab...")
        cook_tab.bring_to_front()

        # Wait for SSE update
        start_time = time.time()
        sse_received = False

        for i in range(15):  # Wait up to 15 seconds
            time.sleep(1)

            # Check console for SSE message
            sse_logs = [log for log in console_logs if 'Meal plan changed' in log or 'Updating meal display' in log]
            if sse_logs:
                elapsed = time.time() - start_time
                print(f"   ✅ SSE EVENT RECEIVED in {elapsed:.1f}s")
                print(f"   📝 Console: {sse_logs[-1]}")
                sse_received = True
                break

        if not sse_received:
            print("   ⚠️  No SSE event detected within 15 seconds")
            print(f"   📋 Console logs: {console_logs}")

        # Wait for update to complete
        cook_tab.wait_for_timeout(3000)

        # Check if meals updated (count might change)
        final_meal_count = cook_tab.locator('.cursor-pointer.p-4').count()
        print(f"   📊 Final meal count: {final_meal_count}")

        # Check for page reload (should NOT reload)
        update_logs = [log for log in console_logs if 'Updating meal display' in log]
        if update_logs:
            print("   ✅ DYNAMIC UPDATE (no page reload)")
        else:
            reload_logs = [log for log in console_logs if 'reload' in log.lower()]
            if reload_logs:
                print("   ⚠️  Page reloaded (should use dynamic update)")

        cook_tab.screenshot(path='/tmp/cook_tab_updated.png', full_page=True)

        # Summary
        print("\n" + "=" * 70)
        print("📊 TEST RESULTS")
        print("=" * 70)

        results = {
            "Embedded Recipes (0-query)": len(embedded_logs) > 0 if 'embedded_logs' in locals() else False,
            "Recipe Display Works": recipe_details.is_visible() if 'recipe_details' in locals() else False,
            "SSE Event Received": sse_received,
            "Dynamic Update (no reload)": len(update_logs) > 0 if 'update_logs' in locals() else False,
        }

        for test, passed in results.items():
            status = "✅ PASS" if passed else "❌ FAIL"
            print(f"   {status}: {test}")

        print("\n📸 Screenshots:")
        print("   - /tmp/cook_tab_recipe.png (recipe displayed)")
        print("   - /tmp/cook_tab_updated.png (after SSE update)")

        all_passed = all(results.values())
        print("\n" + "=" * 70)
        if all_passed:
            print("🎉 ALL TESTS PASSED!")
            print("   ✅ Cook tab uses embedded recipes (0-query architecture)")
            print("   ✅ SSE updates work without page reload")
        else:
            print("⚠️  SOME TESTS FAILED")
            print("   Check console logs and screenshots for details")
        print("=" * 70)

        print("\n   Browser will remain open for 10 seconds...")
        time.sleep(10)

        browser.close()
        print("   Browser closed.")

if __name__ == '__main__':
    test_cook_tab_final()
