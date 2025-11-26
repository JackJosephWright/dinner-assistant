#!/usr/bin/env python3
"""
Playwright integration tests for the Dinner Assistant web UI.

Tests that all three tabs (Plan, Shop, Cook) work correctly after agent cleanup.
Uses with_server.py to manage the Flask server lifecycle.

Run with:
    python /home/jack_wright/.claude/plugins/marketplaces/anthropic-agent-skills/webapp-testing/scripts/with_server.py \
        --server "source .env && python3 src/web/app.py" --port 5000 \
        -- python tests/integration/test_webapp_integration.py
"""

import sys
import time
from playwright.sync_api import sync_playwright

# Test configuration
BASE_URL = "http://localhost:5000"
SCREENSHOT_DIR = "/tmp"


def test_plan_tab():
    """Test the Plan tab loads and can display meal planning interface."""
    print("\n" + "="*60)
    print("TEST: Plan Tab")
    print("="*60)

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()

        # Capture console logs for debugging
        console_logs = []
        page.on("console", lambda msg: console_logs.append(f"[{msg.type}] {msg.text}"))

        try:
            # Navigate to Plan tab
            print("Navigating to /plan...")
            page.goto(f"{BASE_URL}/plan")
            page.wait_for_load_state('networkidle')
            page.wait_for_timeout(2000)

            # Take screenshot
            screenshot_path = f"{SCREENSHOT_DIR}/test_plan_tab.png"
            page.screenshot(path=screenshot_path, full_page=True)
            print(f"Screenshot: {screenshot_path}")

            # Check page loaded
            title = page.title()
            print(f"Page title: {title}")

            # Check for key elements
            checks = []

            # Check navigation
            nav = page.locator("nav, .nav, #navbar")
            if nav.count() > 0:
                checks.append("✅ Navigation found")
            else:
                checks.append("⚠️ Navigation not found (may be styled differently)")

            # Check for chat input or meal plan area
            chat_input = page.locator("#chatInput, input[type='text'], textarea")
            if chat_input.count() > 0:
                checks.append("✅ Chat/input area found")
            else:
                checks.append("❌ Chat input not found")

            # Check for meal plan grid or cards
            meal_area = page.locator("#mealPlanGrid, #mealCardsGrid, .meal-card, .meal-grid")
            if meal_area.count() > 0:
                checks.append("✅ Meal plan area found")
            else:
                checks.append("⚠️ Meal plan area empty (expected before planning)")

            for check in checks:
                print(f"  {check}")

            # Check for errors in console
            errors = [log for log in console_logs if 'error' in log.lower()]
            if errors:
                print(f"\n  Console errors: {len(errors)}")
                for err in errors[:3]:
                    print(f"    {err[:100]}")

            success = "❌" not in "".join(checks)
            print(f"\n{'✅ PASSED' if success else '❌ FAILED'}: Plan tab test")
            return success

        finally:
            browser.close()


def test_shop_tab():
    """Test the Shop tab loads and displays shopping list interface."""
    print("\n" + "="*60)
    print("TEST: Shop Tab")
    print("="*60)

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()

        console_logs = []
        page.on("console", lambda msg: console_logs.append(f"[{msg.type}] {msg.text}"))

        try:
            # Navigate to Shop tab
            print("Navigating to /shop...")
            page.goto(f"{BASE_URL}/shop")
            page.wait_for_load_state('networkidle')
            page.wait_for_timeout(2000)

            # Take screenshot
            screenshot_path = f"{SCREENSHOT_DIR}/test_shop_tab.png"
            page.screenshot(path=screenshot_path, full_page=True)
            print(f"Screenshot: {screenshot_path}")

            # Check page loaded
            title = page.title()
            print(f"Page title: {title}")

            checks = []

            # Check for shopping list container
            shop_container = page.locator("#shoppingListContainer, .shopping-list, #groceryList")
            if shop_container.count() > 0:
                checks.append("✅ Shopping list container found")
            else:
                checks.append("❌ Shopping list container not found")

            # Check for category sections or empty state
            categories = page.locator(".category-section, .store-section, #emptyState, .empty-state")
            if categories.count() > 0:
                checks.append("✅ Category sections or empty state found")
            else:
                checks.append("⚠️ No categories (may need meal plan first)")

            # Check for generate button
            generate_btn = page.locator("button:has-text('Generate'), button:has-text('Regenerate')")
            if generate_btn.count() > 0:
                checks.append("✅ Generate button found")
            else:
                checks.append("⚠️ Generate button not found")

            for check in checks:
                print(f"  {check}")

            errors = [log for log in console_logs if 'error' in log.lower()]
            if errors:
                print(f"\n  Console errors: {len(errors)}")

            success = "❌" not in "".join(checks)
            print(f"\n{'✅ PASSED' if success else '❌ FAILED'}: Shop tab test")
            return success

        finally:
            browser.close()


def test_cook_tab():
    """Test the Cook tab loads and displays cooking guide interface."""
    print("\n" + "="*60)
    print("TEST: Cook Tab")
    print("="*60)

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()

        console_logs = []
        page.on("console", lambda msg: console_logs.append(f"[{msg.type}] {msg.text}"))

        try:
            # Navigate to Cook tab
            print("Navigating to /cook...")
            page.goto(f"{BASE_URL}/cook")
            page.wait_for_load_state('networkidle')
            page.wait_for_timeout(2000)

            # Take screenshot
            screenshot_path = f"{SCREENSHOT_DIR}/test_cook_tab.png"
            page.screenshot(path=screenshot_path, full_page=True)
            print(f"Screenshot: {screenshot_path}")

            title = page.title()
            print(f"Page title: {title}")

            checks = []

            # Check for meal cards grid
            meal_grid = page.locator("#mealCardsGrid, .meal-grid, .recipe-grid")
            if meal_grid.count() > 0:
                checks.append("✅ Meal cards grid found")
            else:
                checks.append("⚠️ Meal cards grid empty (needs meal plan)")

            # Check for recipe search
            search_input = page.locator("#searchRecipes, input[placeholder*='Search'], input[type='search']")
            if search_input.count() > 0:
                checks.append("✅ Recipe search input found")
            else:
                checks.append("⚠️ Recipe search not found")

            # Check for recipe viewer section
            recipe_viewer = page.locator("#recipeViewer, .recipe-detail, .recipe-content")
            if recipe_viewer.count() > 0:
                checks.append("✅ Recipe viewer area found")
            else:
                checks.append("⚠️ Recipe viewer area not visible (select recipe first)")

            for check in checks:
                print(f"  {check}")

            errors = [log for log in console_logs if 'error' in log.lower()]
            if errors:
                print(f"\n  Console errors: {len(errors)}")

            # Cook tab passes if grid is found (even if empty)
            success = meal_grid.count() > 0 or recipe_viewer.count() > 0
            print(f"\n{'✅ PASSED' if success else '❌ FAILED'}: Cook tab test")
            return success

        finally:
            browser.close()


def test_navigation():
    """Test navigation between tabs works correctly."""
    print("\n" + "="*60)
    print("TEST: Tab Navigation")
    print("="*60)

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()

        try:
            # Start at Plan tab
            print("Starting at /plan...")
            page.goto(f"{BASE_URL}/plan")
            page.wait_for_load_state('networkidle')

            checks = []

            # Try navigating to Shop
            print("Clicking Shop tab...")
            shop_link = page.locator("a[href='/shop'], a:has-text('Shop'), [data-tab='shop']")
            if shop_link.count() > 0:
                shop_link.first.click()
                page.wait_for_load_state('networkidle')
                if "/shop" in page.url:
                    checks.append("✅ Navigation to Shop works")
                else:
                    checks.append("❌ Navigation to Shop failed")
            else:
                checks.append("⚠️ Shop link not found")

            # Try navigating to Cook
            print("Clicking Cook tab...")
            cook_link = page.locator("a[href='/cook'], a:has-text('Cook'), [data-tab='cook']")
            if cook_link.count() > 0:
                cook_link.first.click()
                page.wait_for_load_state('networkidle')
                if "/cook" in page.url:
                    checks.append("✅ Navigation to Cook works")
                else:
                    checks.append("❌ Navigation to Cook failed")
            else:
                checks.append("⚠️ Cook link not found")

            # Try navigating back to Plan
            print("Clicking Plan tab...")
            plan_link = page.locator("a[href='/plan'], a:has-text('Plan'), [data-tab='plan']")
            if plan_link.count() > 0:
                plan_link.first.click()
                page.wait_for_load_state('networkidle')
                if "/plan" in page.url:
                    checks.append("✅ Navigation to Plan works")
                else:
                    checks.append("❌ Navigation to Plan failed")
            else:
                checks.append("⚠️ Plan link not found")

            for check in checks:
                print(f"  {check}")

            success = "❌" not in "".join(checks)
            print(f"\n{'✅ PASSED' if success else '❌ FAILED'}: Navigation test")
            return success

        finally:
            browser.close()


def test_api_health():
    """Test that the API health endpoint responds."""
    print("\n" + "="*60)
    print("TEST: API Health Check")
    print("="*60)

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()

        try:
            # Check health endpoint
            response = page.request.get(f"{BASE_URL}/health")
            status = response.status

            if status == 200:
                print(f"  ✅ Health endpoint returned 200")
                return True
            else:
                print(f"  ❌ Health endpoint returned {status}")
                return False

        finally:
            browser.close()


def main():
    """Run all integration tests."""
    print("\n" + "="*60)
    print("DINNER ASSISTANT WEB UI INTEGRATION TESTS")
    print("="*60)
    print("\nTesting after agent cleanup to verify nothing broke.")
    print(f"Base URL: {BASE_URL}")
    print(f"Screenshots: {SCREENSHOT_DIR}")

    results = []

    # Run tests
    results.append(("API Health", test_api_health()))
    results.append(("Plan Tab", test_plan_tab()))
    results.append(("Shop Tab", test_shop_tab()))
    results.append(("Cook Tab", test_cook_tab()))
    results.append(("Navigation", test_navigation()))

    # Summary
    print("\n" + "="*60)
    print("TEST SUMMARY")
    print("="*60)

    passed = sum(1 for _, result in results if result)
    total = len(results)

    for name, result in results:
        status = "✅ PASSED" if result else "❌ FAILED"
        print(f"  {status}: {name}")

    print(f"\nTotal: {passed}/{total} tests passed")

    if passed == total:
        print("\n🎉 All integration tests passed!")
        sys.exit(0)
    else:
        print(f"\n❌ {total - passed} test(s) failed")
        sys.exit(1)


if __name__ == "__main__":
    main()
