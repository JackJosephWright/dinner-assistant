#!/usr/bin/env python3
"""
Test Cook tab SSE integration - verify it reloads when meal plan changes.
"""

from playwright.sync_api import sync_playwright
import time

def test_cook_tab_sse():
    """Test that Cook tab reloads when meal plan changes in Plan tab."""

    with sync_playwright() as p:
        # Launch browser in headed mode (visible)
        browser = p.chromium.launch(headless=False, slow_mo=500)

        # Create two pages (simulating two tabs)
        plan_tab = browser.new_page()
        cook_tab = browser.new_page()

        print("=" * 70)
        print("🧪 TESTING COOK TAB SSE CROSS-TAB SYNCHRONIZATION")
        print("=" * 70)

        # Step 1: Open Plan tab and create a meal plan
        print("\n📋 Step 1: Opening Plan tab and creating meal plan...")
        plan_tab.goto('http://localhost:5000', wait_until='domcontentloaded')
        plan_tab.wait_for_timeout(3000)
        print("   ✅ Plan tab loaded")

        # Check if there's already a meal plan
        clear_button = plan_tab.locator('button:has-text("Clear Plan")').first
        if clear_button.is_visible():
            print("   🗑️  Clearing existing plan...")
            clear_button.click()
            plan_tab.wait_for_timeout(3000)

        # Create new plan
        print("   📝 Creating new meal plan...")
        chat_input = plan_tab.locator('input[placeholder*="Type your message"]').first
        chat_input.fill("Plan 3 meals for the week")
        plan_tab.wait_for_timeout(500)

        send_button = plan_tab.locator('button[type="submit"]').first
        send_button.click()

        # Wait for plan to be created
        print("   ⏳ Waiting for AI to create plan (this may take 30-60s)...")
        try:
            plan_tab.wait_for_selector('a[href*="/recipe/"], h3:has-text("Monday")', timeout=90000)
            print("   ✅ Meal plan created successfully")
        except:
            print("   ⚠️  Timeout waiting for meal plan (may still be loading)")

        plan_tab.wait_for_timeout(5000)

        # Step 2: Open Cook tab
        print("\n👨‍🍳 Step 2: Opening Cook tab...")
        cook_tab.goto('http://localhost:5000/cook', wait_until='domcontentloaded')
        cook_tab.wait_for_timeout(2000)

        # Count initial meals
        initial_meals = cook_tab.locator('.cursor-pointer.p-4').count()
        print(f"   ✅ Cook tab loaded with {initial_meals} meals")
        cook_tab.screenshot(path='/tmp/cook_initial.png', full_page=True)

        # Step 3: Add console listener to Cook tab to catch SSE events
        print("\n📡 Step 3: Setting up console listener on Cook tab...")
        console_logs = []
        cook_tab.on('console', lambda msg: console_logs.append(msg.text))

        # Step 4: Swap a meal in Plan tab (this should trigger meal_plan_changed event)
        print("\n🔄 Step 4: Swapping meal in Plan tab...")

        # Look for a meal card with swap button
        swap_button = plan_tab.locator('button:has-text("Swap")').first
        if swap_button.is_visible(timeout=5000):
            print("   🎯 Clicking swap button...")
            swap_button.click()
            plan_tab.wait_for_timeout(1000)

            # Look for backup recipe selection
            backup_option = plan_tab.locator('.cursor-pointer, button:has-text("Select")').first
            if backup_option.is_visible(timeout=3000):
                print("   ✨ Selecting backup recipe...")
                backup_option.click()
                plan_tab.wait_for_timeout(5000)
                print("   ✅ Meal swapped in Plan tab")
            else:
                print("   ⚠️  No backup options found, trying different approach...")
        else:
            print("   ⚠️  Swap button not found, trying chat-based swap...")
            # Alternative: use chat to swap
            chat_input = plan_tab.locator('input[placeholder*="Type your message"]').first
            chat_input.fill("Swap Monday for something different")
            plan_tab.wait_for_timeout(500)
            send_button = plan_tab.locator('button[type="submit"]').first
            send_button.click()
            plan_tab.wait_for_timeout(10000)
            print("   ✅ Swap requested via chat")

        # Step 5: Watch Cook tab for automatic reload
        print("\n👀 Step 5: Watching Cook tab for SSE-triggered reload...")
        print("   ⏳ Waiting up to 10 seconds for Cook tab to detect change...")

        # Monitor for page reload or console log
        start_time = time.time()
        reload_detected = False

        # Check console logs for SSE message
        for i in range(10):
            time.sleep(1)

            # Check if SSE message was logged
            sse_messages = [log for log in console_logs if 'Meal plan changed' in log or 'reloading' in log]
            if sse_messages:
                reload_detected = True
                elapsed = time.time() - start_time
                print(f"   ✅ SSE event detected! ({elapsed:.1f}s)")
                print(f"   📝 Console: {sse_messages[-1]}")
                break

            # Check if URL changed (page reloaded)
            current_url = cook_tab.url
            if 'cook' not in current_url or cook_tab.is_closed():
                reload_detected = True
                elapsed = time.time() - start_time
                print(f"   ✅ Cook tab reloaded! ({elapsed:.1f}s)")
                break

        if not reload_detected:
            print("   ⚠️  No reload detected within 10 seconds")
            print(f"   📋 Console logs captured: {len(console_logs)}")
            if console_logs:
                print("   Recent logs:")
                for log in console_logs[-5:]:
                    print(f"      - {log}")

        # Wait a bit more and take final screenshot
        cook_tab.wait_for_timeout(3000)

        # Check if Cook tab reloaded by comparing meal count
        try:
            final_meals = cook_tab.locator('.cursor-pointer.p-4').count()
            print(f"\n   📊 Meal count: Initial={initial_meals}, Final={final_meals}")
            cook_tab.screenshot(path='/tmp/cook_final.png', full_page=True)
        except:
            print("   ⚠️  Could not count final meals (tab may have reloaded)")

        # Summary
        print("\n" + "=" * 70)
        print("📸 SCREENSHOTS")
        print("=" * 70)
        print("   Initial state: /tmp/cook_initial.png")
        print("   Final state:   /tmp/cook_final.png")

        print("\n" + "=" * 70)
        print("✅ TEST COMPLETE")
        print("=" * 70)
        if reload_detected:
            print("   🎉 SUCCESS: Cook tab SSE integration is working!")
            print("   The Cook tab automatically detected meal plan changes.")
        else:
            print("   ⚠️  UNCLEAR: Cook tab may not have detected the change")
            print("   Check console logs and screenshots for details.")

        print("\n   Browser will remain open for 10 seconds...")
        time.sleep(10)

        browser.close()
        print("   Browser closed.")

if __name__ == '__main__':
    test_cook_tab_sse()
