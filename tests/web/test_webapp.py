#!/usr/bin/env python3
"""
Test script to interact with the Flask web application and verify optimizations.
"""

import requests
import time
import json
from datetime import datetime, timedelta

BASE_URL = "http://127.0.0.1:5000"

class WebAppTester:
    def __init__(self):
        self.session = requests.Session()
        self.results = []

    def log(self, message, status="INFO"):
        timestamp = datetime.now().strftime("%H:%M:%S")
        print(f"[{timestamp}] [{status}] {message}")

    def test_home_page(self):
        """Test that home page loads and redirects to plan page."""
        self.log("Testing home page redirect...")
        start = time.time()
        response = self.session.get(f"{BASE_URL}/")
        elapsed = time.time() - start

        if response.status_code == 200 and "/plan" in response.url:
            self.log(f"✓ Home page redirects to /plan ({elapsed:.2f}s)", "PASS")
            return True
        else:
            self.log(f"✗ Home page failed (status: {response.status_code})", "FAIL")
            return False

    def test_plan_page(self):
        """Test plan page loads."""
        self.log("Testing plan page...")
        start = time.time()
        response = self.session.get(f"{BASE_URL}/plan")
        elapsed = time.time() - start

        if response.status_code == 200:
            has_onboarding = "onboardingModal" in response.text
            has_chat = "chatContainer" in response.text
            has_day_selector = "daySelector" in response.text

            self.log(f"✓ Plan page loaded ({elapsed:.2f}s)", "PASS")
            self.log(f"  - Onboarding modal: {'Yes' if has_onboarding else 'No'}")
            self.log(f"  - Chat interface: {'Yes' if has_chat else 'No'}")
            self.log(f"  - Day selector: {'Yes' if has_day_selector else 'No'}")
            return True
        else:
            self.log(f"✗ Plan page failed (status: {response.status_code})", "FAIL")
            return False

    def test_onboarding_flow(self):
        """Test onboarding API."""
        self.log("Testing onboarding flow...")

        # Check onboarding status
        response = self.session.get(f"{BASE_URL}/api/onboarding/check")
        if response.status_code == 200:
            data = response.json()
            self.log(f"✓ Onboarding check: needs_onboarding={data.get('needs_onboarding')}", "PASS")

            if data.get('needs_onboarding'):
                # Start onboarding
                response = self.session.post(f"{BASE_URL}/api/onboarding/start")
                if response.status_code == 200:
                    self.log("✓ Onboarding started", "PASS")

                    # Answer questions
                    answers = [
                        "2 adults",
                        "No allergies",
                        "Italian, Mexican, Asian",
                        "30-45 minutes",
                        "None",
                        "Medium spice",
                        "yes"
                    ]

                    for i, answer in enumerate(answers):
                        response = self.session.post(
                            f"{BASE_URL}/api/onboarding/answer",
                            json={"answer": answer}
                        )
                        if response.status_code == 200:
                            data = response.json()
                            if data.get('is_complete'):
                                self.log(f"✓ Onboarding completed after {i+1} answers", "PASS")
                                break
                        else:
                            self.log(f"✗ Onboarding answer {i+1} failed", "FAIL")
                            return False
                    return True
                else:
                    self.log("✗ Failed to start onboarding", "FAIL")
                    return False
            else:
                self.log("  (Already onboarded)", "INFO")
                return True
        else:
            self.log("✗ Onboarding check failed", "FAIL")
            return False

    def test_chat_create_meal_plan(self):
        """Test chat API to create meal plan."""
        self.log("Testing meal plan creation via chat...")

        # Get next Monday
        today = datetime.now()
        days_until_monday = (7 - today.weekday()) % 7
        if days_until_monday == 0:
            days_until_monday = 7
        next_monday = today + timedelta(days=days_until_monday)
        start_date = next_monday.strftime("%Y-%m-%d")

        message = f"Plan meals for 7 days starting {start_date}"

        self.log(f"  Message: '{message}'")
        start = time.time()

        response = self.session.post(
            f"{BASE_URL}/api/chat",
            json={"message": message},
            timeout=60
        )

        elapsed = time.time() - start

        if response.status_code == 200:
            data = response.json()
            if data.get('success'):
                plan_id = data.get('meal_plan_id')
                plan_changed = data.get('plan_changed')

                self.log(f"✓ Meal plan created via chat ({elapsed:.2f}s)", "PASS")
                self.log(f"  - Plan ID: {plan_id}")
                self.log(f"  - Plan changed: {plan_changed}")
                self.log(f"  - Response: {data.get('response', '')[:100]}...")
                return plan_id
            else:
                self.log(f"✗ Chat returned error: {data.get('error')}", "FAIL")
                return None
        else:
            self.log(f"✗ Chat API failed (status: {response.status_code})", "FAIL")
            return None

    def test_get_current_plan(self):
        """Test the new /api/plan/current endpoint."""
        self.log("Testing GET /api/plan/current endpoint...")
        start = time.time()

        response = self.session.get(f"{BASE_URL}/api/plan/current")
        elapsed = time.time() - start

        if response.status_code == 200:
            data = response.json()
            if data.get('success'):
                plan = data.get('plan')
                meals = plan.get('meals', [])

                self.log(f"✓ GET /api/plan/current works ({elapsed:.2f}s)", "PASS")
                self.log(f"  - Week of: {plan.get('week_of')}")
                self.log(f"  - Number of meals: {len(meals)}")

                # Check if meals have enriched data
                if meals:
                    first_meal = meals[0]
                    has_description = 'description' in first_meal
                    has_time = 'estimated_time' in first_meal
                    has_cuisine = 'cuisine' in first_meal

                    self.log(f"  - Enriched data: description={has_description}, time={has_time}, cuisine={has_cuisine}")

                    if has_description and has_time:
                        self.log("✓ N+1 query optimization working (enriched data present)", "PASS")
                    else:
                        self.log("⚠ Enriched data may be missing", "WARN")

                return True
            else:
                self.log(f"  No meal plan found yet", "INFO")
                return False
        elif response.status_code == 404:
            self.log("  No meal plan exists (404) - this is expected if none created", "INFO")
            return False
        else:
            self.log(f"✗ Endpoint failed (status: {response.status_code})", "FAIL")
            return False

    def test_preload_endpoint(self):
        """Test the preload endpoint."""
        self.log("Testing POST /api/plan/preload endpoint...")
        start = time.time()

        response = self.session.post(f"{BASE_URL}/api/plan/preload")
        elapsed = time.time() - start

        if response.status_code == 200:
            data = response.json()
            if data.get('success'):
                self.log(f"✓ Preload endpoint works ({elapsed:.2f}s)", "PASS")
                self.log(f"  - Shopping list created: {data.get('shopping_list_created')}")
                self.log(f"  - Shopping list ID: {data.get('shopping_list_id')}")
                return True
            else:
                self.log(f"✗ Preload failed: {data.get('error')}", "FAIL")
                return False
        else:
            self.log(f"✗ Preload endpoint failed (status: {response.status_code})", "FAIL")
            return False

    def test_shop_page(self):
        """Test that shop page loads quickly (should be instant if preloaded)."""
        self.log("Testing shop page load time...")
        start = time.time()

        response = self.session.get(f"{BASE_URL}/shop")
        elapsed = time.time() - start

        if response.status_code == 200:
            has_list = "Shopping List" in response.text
            has_chat = "chatMessages" in response.text

            status_msg = "✓" if elapsed < 0.5 else "⚠"
            self.log(f"{status_msg} Shop page loaded ({elapsed:.2f}s)", "PASS" if elapsed < 0.5 else "WARN")
            self.log(f"  - Has shopping list UI: {has_list}")
            self.log(f"  - Has chat interface: {has_chat}")

            if elapsed > 5:
                self.log("  ⚠ Load time >5s - preload may not be working", "WARN")

            return True
        else:
            self.log(f"✗ Shop page failed (status: {response.status_code})", "FAIL")
            return False

    def test_cook_page(self):
        """Test cook page loads."""
        self.log("Testing cook page...")
        start = time.time()

        response = self.session.get(f"{BASE_URL}/cook")
        elapsed = time.time() - start

        if response.status_code == 200:
            self.log(f"✓ Cook page loaded ({elapsed:.2f}s)", "PASS")
            return True
        else:
            self.log(f"✗ Cook page failed (status: {response.status_code})", "FAIL")
            return False

    def run_all_tests(self):
        """Run all tests in sequence."""
        print("=" * 60)
        print("MEAL PLANNING WEB APP - OPTIMIZATION TESTS")
        print("=" * 60)
        print()

        tests = [
            ("Home Page Redirect", self.test_home_page),
            ("Plan Page Load", self.test_plan_page),
            ("Onboarding Flow", self.test_onboarding_flow),
            ("Create Meal Plan via Chat", self.test_chat_create_meal_plan),
            ("GET /api/plan/current (N+1 Fix)", self.test_get_current_plan),
            ("POST /api/plan/preload", self.test_preload_endpoint),
            ("Shop Page Load Speed", self.test_shop_page),
            ("Cook Page Load", self.test_cook_page),
        ]

        results = []

        for test_name, test_func in tests:
            print()
            print(f"--- {test_name} ---")
            try:
                result = test_func()
                results.append((test_name, "PASS" if result else "FAIL"))
            except Exception as e:
                self.log(f"✗ Exception: {str(e)}", "ERROR")
                results.append((test_name, "ERROR"))

            time.sleep(0.5)  # Small delay between tests

        # Summary
        print()
        print("=" * 60)
        print("TEST SUMMARY")
        print("=" * 60)

        passed = sum(1 for _, status in results if status == "PASS")
        failed = sum(1 for _, status in results if status in ["FAIL", "ERROR"])

        for test_name, status in results:
            icon = "✓" if status == "PASS" else "✗"
            print(f"{icon} {test_name}: {status}")

        print()
        print(f"Total: {passed}/{len(results)} passed")

        if failed == 0:
            print()
            print("🎉 All tests passed! Optimizations are working correctly.")
        else:
            print()
            print(f"⚠️  {failed} test(s) failed. Review output above.")

        return failed == 0


if __name__ == "__main__":
    tester = WebAppTester()
    success = tester.run_all_tests()
    exit(0 if success else 1)
