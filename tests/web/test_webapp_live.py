#!/usr/bin/env python3
"""
Live test of the Dinner Assistant web application using Playwright.
"""

from playwright.sync_api import sync_playwright
import time

def test_web_app():
    """Test the web application UI and functionality."""

    with sync_playwright() as p:
        # Launch browser in headed mode (visible)
        browser = p.chromium.launch(headless=False, slow_mo=500)
        page = browser.new_page()

        print("🌐 Navigating to http://localhost:5000...")
        page.goto('http://localhost:5000', wait_until='domcontentloaded')

        # Wait a bit for initial render
        page.wait_for_timeout(2000)

        # Take initial screenshot
        page.screenshot(path='/tmp/webapp_home.png', full_page=True)
        print("📸 Screenshot saved to /tmp/webapp_home.png")

        # Get page title
        title = page.title()
        print(f"📄 Page title: {title}")

        # Check for main navigation tabs
        print("\n🔍 Checking for navigation tabs...")
        tabs = page.locator('[role="tab"], .tab, .nav-link').all()
        print(f"   Found {len(tabs)} tabs")
        for i, tab in enumerate(tabs):
            tab_text = tab.text_content()
            print(f"   Tab {i+1}: {tab_text}")

        # Check for Plan tab elements
        print("\n🔍 Checking Plan tab elements...")
        plan_elements = page.locator('button, input, textarea').all()
        print(f"   Found {len(plan_elements)} interactive elements")

        # Look for chat interface
        print("\n🔍 Looking for chat interface...")
        chat_inputs = page.locator('input[type="text"], textarea').all()
        if chat_inputs:
            print(f"   Found {len(chat_inputs)} input field(s)")
            for i, input_field in enumerate(chat_inputs):
                placeholder = input_field.get_attribute('placeholder')
                if placeholder:
                    print(f"   Input {i+1} placeholder: {placeholder}")

        # Check for meal plan display
        print("\n🔍 Checking for meal plan display...")
        meal_cards = page.locator('.meal-card, .recipe-card, [class*="meal"]').all()
        print(f"   Found {len(meal_cards)} meal-related elements")

        # Take screenshot of Plan tab
        page.screenshot(path='/tmp/webapp_plan.png', full_page=True)
        print("📸 Screenshot saved to /tmp/webapp_plan.png")

        # Click through the tabs to show navigation
        print("\n🔍 Clicking through tabs...")

        # Click Shop tab
        print("   Clicking Shop tab...")
        shop_tab = page.locator('a:has-text("Shop")').first
        shop_tab.click()
        page.wait_for_timeout(2000)
        page.screenshot(path='/tmp/webapp_shop.png', full_page=True)
        print("   📸 Shop tab screenshot saved")

        # Click Cook tab
        print("   Clicking Cook tab...")
        cook_tab = page.locator('a:has-text("Cook")').first
        cook_tab.click()
        page.wait_for_timeout(2000)
        page.screenshot(path='/tmp/webapp_cook.png', full_page=True)
        print("   📸 Cook tab screenshot saved")

        # Click back to Plan tab
        print("   Clicking back to Plan tab...")
        plan_tab = page.locator('a:has-text("Plan")').first
        plan_tab.click()
        page.wait_for_timeout(2000)

        # Try interacting with the chat
        print("\n💬 Testing chat interface...")
        chat_input = page.locator('input[placeholder*="Type your message"]').first
        if chat_input.is_visible():
            print("   Typing a test message...")
            chat_input.fill("Show me what's on the plan")
            page.wait_for_timeout(1000)

            # Click send button
            send_button = page.locator('button[type="submit"]').first
            if send_button.is_visible():
                print("   (Not clicking send to avoid triggering LLM)")
                # send_button.click()  # Commented out to avoid LLM call

        print("\n✨ Demonstration complete!")

        # Get console logs
        print("\n📋 Console logs:")
        console_messages = []
        page.on('console', lambda msg: console_messages.append(f"   [{msg.type}] {msg.text}"))

        # Reload to capture console logs
        page.reload(wait_until='domcontentloaded')
        page.wait_for_timeout(1000)

        if console_messages:
            for msg in console_messages[-10:]:  # Last 10 messages
                print(msg)
        else:
            print("   No console messages captured")

        # Summary
        print("\n✅ Web app test complete!")
        print(f"   Screenshots saved to /tmp/webapp_*.png")
        print("\n   Browser will remain open for 5 more seconds...")
        page.wait_for_timeout(5000)

        browser.close()
        print("   Browser closed.")

if __name__ == '__main__':
    test_web_app()
