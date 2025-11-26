#!/usr/bin/env python3
"""
Test web app timing: clear plan, create new plan, measure tab load times.
"""

from playwright.sync_api import sync_playwright
import time

def test_webapp_timing():
    """Test meal planning workflow and measure tab load times."""

    with sync_playwright() as p:
        # Launch browser in headed mode (visible)
        browser = p.chromium.launch(headless=False, slow_mo=300)
        page = browser.new_page()

        print("🌐 Navigating to http://localhost:5000...")
        start = time.time()
        page.goto('http://localhost:5000', wait_until='domcontentloaded')
        page.wait_for_timeout(2000)
        load_time = time.time() - start
        print(f"   ✅ Plan tab loaded in {load_time:.2f}s")

        # Take initial screenshot
        page.screenshot(path='/tmp/test_initial.png', full_page=True)

        # Step 1: Clear the existing meal plan
        print("\n🗑️  Clearing meal plan...")
        clear_button = page.locator('button:has-text("Clear Plan")').first
        if clear_button.is_visible():
            start = time.time()
            clear_button.click()

            # Wait for confirmation and accept
            page.wait_for_timeout(1000)

            # Look for confirmation dialog (if any)
            try:
                confirm_button = page.locator('button:has-text("Confirm"), button:has-text("Yes"), button:has-text("OK")').first
                if confirm_button.is_visible(timeout=2000):
                    confirm_button.click()
                    print("   ✅ Confirmed clear action")
            except:
                print("   ℹ️  No confirmation dialog (or already cleared)")

            page.wait_for_timeout(2000)
            clear_time = time.time() - start
            print(f"   ✅ Plan cleared in {clear_time:.2f}s")
            page.screenshot(path='/tmp/test_cleared.png', full_page=True)
        else:
            print("   ⚠️  Clear button not found")

        # Step 2: Create a new meal plan
        print("\n📝 Creating new meal plan...")
        chat_input = page.locator('input[placeholder*="Type your message"]').first

        if chat_input.is_visible():
            # Type the planning request
            print("   Typing: 'Plan 5 meals for the week'")
            chat_input.fill("Plan 5 meals for the week")
            page.wait_for_timeout(500)

            # Click send button
            send_button = page.locator('button[type="submit"]').first
            if send_button.is_visible():
                print("   🚀 Sending request...")
                start = time.time()
                send_button.click()

                # Wait for response to appear
                print("   ⏳ Waiting for AI response...")

                # Wait for meal cards to appear (indicating plan is created)
                try:
                    # Look for meal cards or recipe links appearing
                    page.wait_for_selector('a[href*="/recipe/"], .meal-card, h3:has-text("Monday"), h3:has-text("Day")', timeout=60000)
                    plan_time = time.time() - start
                    print(f"   ✅ Meal plan created in {plan_time:.2f}s")
                except:
                    plan_time = time.time() - start
                    print(f"   ⏱️  Waited {plan_time:.2f}s (may still be loading)")

                # Wait a bit more for full render
                page.wait_for_timeout(3000)
                page.screenshot(path='/tmp/test_plan_created.png', full_page=True)
            else:
                print("   ⚠️  Send button not found")
        else:
            print("   ⚠️  Chat input not found")

        # Step 3: Measure Shop tab load time
        print("\n🛒 Testing Shop tab load time...")
        start = time.time()
        shop_tab = page.locator('a:has-text("Shop")').first
        shop_tab.click()

        # Wait for shopping list to load
        try:
            page.wait_for_selector('.shopping-item, li:has-text("Pantry"), h3:has-text("Pantry")', timeout=30000)
            shop_time = time.time() - start
            print(f"   ✅ Shop tab loaded in {shop_time:.2f}s")
        except:
            shop_time = time.time() - start
            print(f"   ⏱️  Shop tab response in {shop_time:.2f}s (may still be loading)")

        page.wait_for_timeout(2000)
        page.screenshot(path='/tmp/test_shop_tab.png', full_page=True)

        # Step 4: Measure Cook tab load time
        print("\n👨‍🍳 Testing Cook tab load time...")
        start = time.time()
        cook_tab = page.locator('a:has-text("Cook")').first
        cook_tab.click()

        # Wait for cook page to load
        page.wait_for_selector('button:has-text("View Recipe"), .meal-card', timeout=10000)
        cook_time = time.time() - start
        print(f"   ✅ Cook tab loaded in {cook_time:.2f}s")

        page.wait_for_timeout(2000)
        page.screenshot(path='/tmp/test_cook_tab.png', full_page=True)

        # Step 5: Return to Plan tab and measure
        print("\n📋 Testing Plan tab reload time...")
        start = time.time()
        plan_tab = page.locator('a:has-text("Plan")').first
        plan_tab.click()
        page.wait_for_timeout(1000)
        plan_reload_time = time.time() - start
        print(f"   ✅ Plan tab reloaded in {plan_reload_time:.2f}s")

        # Summary
        print("\n" + "="*60)
        print("⏱️  TIMING SUMMARY")
        print("="*60)
        print(f"Initial Plan tab load:  {load_time:.2f}s")
        print(f"Clear meal plan:        {clear_time:.2f}s" if 'clear_time' in locals() else "Clear meal plan:        N/A")
        print(f"Create new meal plan:   {plan_time:.2f}s" if 'plan_time' in locals() else "Create new meal plan:   N/A")
        print(f"Shop tab load:          {shop_time:.2f}s" if 'shop_time' in locals() else "Shop tab load:          N/A")
        print(f"Cook tab load:          {cook_time:.2f}s")
        print(f"Plan tab reload:        {plan_reload_time:.2f}s")
        print("="*60)
        print(f"\n📸 Screenshots saved to /tmp/test_*.png")

        print("\n   Browser will remain open for 5 more seconds...")
        page.wait_for_timeout(5000)

        browser.close()
        print("   Browser closed.")

if __name__ == '__main__':
    test_webapp_timing()
