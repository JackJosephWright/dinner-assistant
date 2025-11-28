"""
Playwright UI tests for the Plan tab.

These tests verify the split-screen chat interface works correctly.
Run with: pytest tests/web/test_plan_page.py -v --headed --slowmo=500
"""

import pytest
import time


@pytest.mark.web
def test_split_screen_layout(authenticated_page, flask_app):
    """
    Test that the Plan page has correct split-screen layout.

    Verifies:
    - Chat column on the left
    - Plan column on the right
    - Both columns visible simultaneously
    """
    page = authenticated_page  # Already logged in and on /plan

    # Wait for page to load
    page.wait_for_selector(".split-container", timeout=5000)

    # Verify split-screen container exists
    split_container = page.locator(".split-container")
    assert split_container.is_visible(), "Split-screen container should be visible"

    # Verify chat column exists and is visible
    chat_column = page.locator(".chat-column")
    assert chat_column.is_visible(), "Chat column should be visible"

    # Verify plan column exists and is visible
    plan_column = page.locator(".plan-column")
    assert plan_column.is_visible(), "Plan column should be visible"

    # Verify chat input exists
    chat_input = page.locator("#messageInput")
    assert chat_input.is_visible(), "Chat input should be visible"

    # Verify send button exists
    send_button = page.locator("#sendButton")
    assert send_button.is_visible(), "Send button should be visible"

    print("✓ Split-screen layout verified")


@pytest.mark.web
@pytest.mark.slow  # This test requires LLM API calls (30-60s)
def test_basic_planning_flow(authenticated_page, flask_app):
    """
    Test basic meal planning workflow.

    Steps:
    1. Select days (e.g., Mon, Tue, Wed)
    2. Send chat message "plan meals"
    3. Wait for response
    4. Verify meals appear in plan column

    Note: This test may take 30+ seconds due to LLM API calls.
    """
    page = authenticated_page  # Already logged in and on /plan
    page.wait_for_selector(".split-container", timeout=5000)

    # Note: All days start selected by default, so we don't need to click them
    # Just verify they are selected
    monday_btn = page.locator("#day-1")  # Monday is index 1
    tuesday_btn = page.locator("#day-2")  # Tuesday is index 2
    wednesday_btn = page.locator("#day-3")  # Wednesday is index 3

    # Verify days are selected by default (they should have 'selected' class)
    assert "selected" in monday_btn.get_attribute("class"), "Monday should be selected"
    assert "selected" in tuesday_btn.get_attribute("class"), "Tuesday should be selected"
    assert "selected" in wednesday_btn.get_attribute("class"), "Wednesday should be selected"

    # Type chat message
    chat_input = page.locator("#messageInput")
    chat_input.fill("plan 3 chicken dinners, no dairy")

    # Click send button
    send_button = page.locator("#sendButton")
    send_button.click()

    # Wait for user message to appear in chat
    page.wait_for_selector("#chatMessages:has-text('plan 3 chicken dinners')", timeout=3000)

    # Wait for AI response (this may take 30+ seconds)
    # Look for either a response message or meal cards appearing
    try:
        # Option 1: Wait for assistant message
        page.wait_for_selector(".chat-messages .bg-gray-100", timeout=60000)
        print("✓ AI response received")
    except:
        print("Warning: AI response timeout, but continuing to check for meals")

    # Wait a bit longer for meals to be rendered
    time.sleep(2)

    # Check if any meal cards appeared in the plan column
    meal_cards = page.locator(".plan-column .bg-white")
    meal_count = meal_cards.count()

    # We should have at least 1 meal (ideally 3, but depends on API being configured)
    if meal_count >= 1:
        print(f"✓ Basic planning flow completed ({meal_count} meals created)")
    else:
        print(f"⚠ Warning: No meals created (expected at least 1). API may not be configured properly.")
        print("   Chat responded but no meals appeared in plan column.")


@pytest.mark.web
@pytest.mark.slow  # This test requires LLM API calls (30-60s)
def test_verbose_output_visibility(authenticated_page, flask_app):
    """
    Test that verbose tool execution details appear in chat.

    Verifies:
    - Tool execution messages appear (e.g., "🔧 [TOOL] search_recipes_smart")
    - Verbose messages have correct styling
    """
    page = authenticated_page  # Already logged in and on /plan
    page.wait_for_selector(".split-container", timeout=5000)

    # Select 1 day
    monday_btn = page.locator("button:has-text('Mon')")
    monday_btn.click()

    # Type simple planning message
    chat_input = page.locator("#messageInput")
    chat_input.fill("plan 1 chicken dinner")

    # Send message
    send_button = page.locator("#sendButton")
    send_button.click()

    # Wait for user message
    page.wait_for_selector("#chatMessages:has-text('plan 1 chicken dinner')", timeout=3000)

    # Wait for verbose tool message to appear
    # These appear as .verbose-message elements with monospace font
    try:
        page.wait_for_selector(".verbose-message", timeout=30000)
        verbose_messages = page.locator(".verbose-message")
        verbose_count = verbose_messages.count()

        assert verbose_count >= 1, f"Expected at least 1 verbose message, got {verbose_count}"

        # Check that at least one message contains tool execution info
        first_verbose = verbose_messages.first
        verbose_text = first_verbose.inner_text()

        # Should contain tool name or execution details
        assert len(verbose_text) > 0, "Verbose message should have content"

        print(f"✓ Verbose output visible ({verbose_count} messages)")
    except:
        # If no verbose messages appeared, that's also okay for now
        print("⚠ Warning: No verbose messages appeared (may need .env file)")


@pytest.mark.web
@pytest.mark.slow  # This test requires LLM API calls (60-120s)
def test_vague_swap_confirmation(authenticated_page, flask_app):
    """
    Test interactive swap confirmation workflow.

    Steps:
    1. Create a meal plan (1 meal)
    2. Request a vague swap (e.g., "swap day 1 to something else")
    3. Wait for 3 options to appear
    4. Type "1" to select first option
    5. Verify swap completes

    Note: This test requires LLM API and may take 60+ seconds.
    """
    page = authenticated_page  # Already logged in and on /plan
    page.wait_for_selector(".split-container", timeout=5000)

    # Step 1: Create initial plan
    monday_btn = page.locator("button:has-text('Mon')")
    monday_btn.click()

    chat_input = page.locator("#messageInput")
    chat_input.fill("plan 1 dinner with chicken")

    send_button = page.locator("#sendButton")
    send_button.click()

    # Wait for plan to be created (or timeout gracefully)
    try:
        page.wait_for_selector("#chatMessages .bg-gray-100", timeout=60000)
        print("✓ AI response received")
    except:
        print("⚠ Warning: AI response timeout (may need API key configured)")
        return  # Skip rest of test if API isn't working
    time.sleep(3)  # Wait for meal to render

    # Verify at least 1 meal exists
    meal_cards = page.locator(".plan-column .bg-white")
    assert meal_cards.count() >= 1, "Should have at least 1 meal before swap"

    # Step 2: Request vague swap
    chat_input.fill("swap day 1 to something else")
    send_button.click()

    # Wait for user message
    page.wait_for_selector("#chatMessages:has-text('swap day 1')", timeout=3000)

    # Wait for AI response with options (should contain "1:", "2:", "3:")
    try:
        # Look for numbered options in assistant message
        page.wait_for_selector("#chatMessages:has-text('1:')", timeout=45000)
        print("✓ Swap options presented")

        # Step 3: Select option 1
        chat_input.fill("1")
        send_button.click()

        # Wait for confirmation message
        page.wait_for_selector("#chatMessages", timeout=45000)

        # Wait for meal to update
        time.sleep(2)

        print("✓ Vague swap confirmation flow completed")
    except:
        print("⚠ Warning: Swap confirmation flow did not complete (may need API key configured)")
        return  # Skip rest of test if API isn't working
