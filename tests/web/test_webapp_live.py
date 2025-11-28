"""
Live test of the Dinner Assistant web application using Playwright.
"""

import pytest


@pytest.mark.web
def test_web_app(authenticated_page, flask_app):
    """Test the web application UI and functionality."""
    page = authenticated_page  # Already logged in and on /plan

    print("\n" + "=" * 70)
    print("WEB APPLICATION UI TEST")
    print("=" * 70)

    # Wait for Plan page to load
    page.wait_for_timeout(2000)

    # Take initial screenshot
    page.screenshot(path='/tmp/webapp_home.png', full_page=True)
    print("Screenshot saved to /tmp/webapp_home.png")

    # Get page title
    title = page.title()
    print(f"Page title: {title}")

    # Check for main navigation tabs
    print("\nChecking for navigation tabs...")
    tabs = page.locator('[role="tab"], .tab, .nav-link, a[href*="/plan"], a[href*="/shop"], a[href*="/cook"]').all()
    print(f"   Found {len(tabs)} navigation elements")
    for i, tab in enumerate(tabs):
        tab_text = tab.text_content()
        if tab_text and tab_text.strip():
            print(f"   Tab {i+1}: {tab_text.strip()}")

    # Check for Plan tab elements
    print("\nChecking Plan tab elements...")
    plan_elements = page.locator('button, input, textarea').all()
    print(f"   Found {len(plan_elements)} interactive elements")

    # Look for chat interface
    print("\nLooking for chat interface...")
    chat_inputs = page.locator('input[type="text"], textarea, #messageInput').all()
    if chat_inputs:
        print(f"   Found {len(chat_inputs)} input field(s)")
        for i, input_field in enumerate(chat_inputs):
            placeholder = input_field.get_attribute('placeholder')
            if placeholder:
                print(f"   Input {i+1} placeholder: {placeholder}")

    # Check for meal plan display
    print("\nChecking for meal plan display...")
    meal_cards = page.locator('.meal-card, .recipe-card, [class*="meal"], .plan-column').all()
    print(f"   Found {len(meal_cards)} meal-related elements")

    # Take screenshot of Plan tab
    page.screenshot(path='/tmp/webapp_plan.png', full_page=True)
    print("Screenshot saved to /tmp/webapp_plan.png")

    # Click through the tabs to show navigation
    print("\nClicking through tabs...")

    # Click Shop tab
    print("   Clicking Shop tab...")
    shop_tab = page.locator('a:has-text("Shop")').first
    if shop_tab.is_visible():
        shop_tab.click()
        page.wait_for_timeout(2000)
        page.screenshot(path='/tmp/webapp_shop.png', full_page=True)
        print("   Shop tab screenshot saved")
    else:
        print("   Shop tab not found")

    # Click Cook tab
    print("   Clicking Cook tab...")
    cook_tab = page.locator('a:has-text("Cook")').first
    if cook_tab.is_visible():
        cook_tab.click()
        page.wait_for_timeout(2000)
        page.screenshot(path='/tmp/webapp_cook.png', full_page=True)
        print("   Cook tab screenshot saved")
    else:
        print("   Cook tab not found")

    # Click back to Plan tab
    print("   Clicking back to Plan tab...")
    plan_tab = page.locator('a:has-text("Plan")').first
    if plan_tab.is_visible():
        plan_tab.click()
        page.wait_for_timeout(2000)
    else:
        print("   Plan tab not found")

    # Try interacting with the chat
    print("\nTesting chat interface...")
    chat_input = page.locator('#messageInput').first
    if chat_input.is_visible():
        print("   Typing a test message...")
        chat_input.fill("Show me what's on the plan")
        page.wait_for_timeout(1000)

        # Check send button exists
        send_button = page.locator('#sendButton').first
        if send_button.is_visible():
            print("   (Not clicking send to avoid triggering LLM)")
    else:
        print("   Chat input not visible")

    print("\nWeb app test complete!")
    print(f"   Screenshots saved to /tmp/webapp_*.png")

    # Assertions
    assert len(tabs) >= 1, "Should have navigation tabs"
    assert len(plan_elements) >= 1, "Should have interactive elements"
