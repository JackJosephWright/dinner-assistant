#!/usr/bin/env python3
"""
Test script to verify day selector functionality.
"""

import requests
import time
from datetime import datetime, timedelta

BASE_URL = "http://127.0.0.1:5000"

class DaySelectorTester:
    def __init__(self):
        self.session = requests.Session()

    def log(self, message, status="INFO"):
        timestamp = datetime.now().strftime("%H:%M:%S")
        print(f"[{timestamp}] [{status}] {message}")

    def test_select_specific_days(self):
        """Test creating meal plan for specific days."""
        print("=" * 60)
        print("DAY SELECTOR FUNCTIONALITY TEST")
        print("=" * 60)
        print()

        # Get next Monday
        today = datetime.now()
        days_until_monday = (7 - today.weekday()) % 7
        if days_until_monday == 0:
            days_until_monday = 7
        next_monday = today + timedelta(days=days_until_monday)

        # Test 1: Plan for specific 3 days (Monday, Wednesday, Friday)
        self.log("Test 1: Planning meals for 3 specific days (Mon, Wed, Fri)")

        monday = next_monday.strftime("%Y-%m-%d")
        wednesday = (next_monday + timedelta(days=2)).strftime("%Y-%m-%d")
        friday = (next_monday + timedelta(days=4)).strftime("%Y-%m-%d")

        dates = [monday, wednesday, friday]
        message = f"Plan meals for me (for these 3 dates: {', '.join(dates)})"

        self.log(f"  Sending: '{message}'")

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
                self.log(f"✓ Chat accepted request ({elapsed:.2f}s)", "PASS")
                self.log(f"  Response: {data.get('response', '')[:150]}...")

                # Check the created plan
                time.sleep(1)
                plan_response = self.session.get(f"{BASE_URL}/api/plan/current")
                if plan_response.status_code == 200:
                    plan_data = plan_response.json()
                    if plan_data.get('success'):
                        meals = plan_data['plan']['meals']
                        self.log(f"  Created {len(meals)} meals", "INFO")

                        # Display meal dates
                        for i, meal in enumerate(meals):
                            meal_date = meal.get('meal_date') or meal.get('date')
                            recipe = meal.get('recipe_name')
                            self.log(f"    {i+1}. {meal_date}: {recipe}")

                        # Verify we got 3 meals
                        if len(meals) == 3:
                            self.log("✓ Created exactly 3 meals as requested", "PASS")
                        else:
                            self.log(f"⚠ Expected 3 meals, got {len(meals)}", "WARN")

                        return True
                    else:
                        self.log("✗ Could not fetch created plan", "FAIL")
                        return False
                else:
                    self.log("✗ Could not fetch plan", "FAIL")
                    return False
            else:
                self.log(f"✗ Chat failed: {data.get('error')}", "FAIL")
                return False
        else:
            self.log(f"✗ Request failed (status: {response.status_code})", "FAIL")
            return False

    def test_full_week(self):
        """Test creating meal plan for full 7 days."""
        print()
        print("-" * 60)
        self.log("Test 2: Planning meals for full week (7 days)")

        # Get next Monday
        today = datetime.now()
        days_until_monday = (7 - today.weekday()) % 7
        if days_until_monday == 0:
            days_until_monday = 7
        next_monday = today + timedelta(days=days_until_monday)
        start_date = next_monday.strftime("%Y-%m-%d")

        message = f"Plan meals for me (for 7 days starting {start_date})"

        self.log(f"  Sending: '{message}'")

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
                self.log(f"✓ Chat accepted request ({elapsed:.2f}s)", "PASS")

                # Check the created plan
                time.sleep(1)
                plan_response = self.session.get(f"{BASE_URL}/api/plan/current")
                if plan_response.status_code == 200:
                    plan_data = plan_response.json()
                    if plan_data.get('success'):
                        meals = plan_data['plan']['meals']
                        self.log(f"  Created {len(meals)} meals", "INFO")

                        # Verify we got 7 meals
                        if len(meals) == 7:
                            self.log("✓ Created exactly 7 meals as requested", "PASS")
                        else:
                            self.log(f"⚠ Expected 7 meals, got {len(meals)}", "WARN")

                        return True
                    else:
                        self.log("✗ Could not fetch created plan", "FAIL")
                        return False
                else:
                    self.log("✗ Could not fetch plan", "FAIL")
                    return False
            else:
                self.log(f"✗ Chat failed: {data.get('error')}", "FAIL")
                return False
        else:
            self.log(f"✗ Request failed (status: {response.status_code})", "FAIL")
            return False

    def test_swap_meal(self):
        """Test swapping a specific day's meal."""
        print()
        print("-" * 60)
        self.log("Test 3: Swapping a specific day's meal")

        # Get the current plan first
        plan_response = self.session.get(f"{BASE_URL}/api/plan/current")
        if plan_response.status_code != 200:
            self.log("✗ No plan exists to swap", "FAIL")
            return False

        plan_data = plan_response.json()
        if not plan_data.get('success'):
            self.log("✗ Could not fetch plan", "FAIL")
            return False

        meals = plan_data['plan']['meals']
        if not meals:
            self.log("✗ No meals in plan", "FAIL")
            return False

        # Get the first meal's date
        first_meal = meals[0]
        meal_date_str = first_meal.get('meal_date') or first_meal.get('date')
        original_recipe = first_meal.get('recipe_name')

        self.log(f"  Original meal on {meal_date_str}: {original_recipe}")

        # Try to swap it
        message = f"Swap {meal_date_str} for something vegetarian"
        self.log(f"  Sending: '{message}'")

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
                self.log(f"✓ Swap request accepted ({elapsed:.2f}s)", "PASS")
                self.log(f"  Response: {data.get('response', '')[:150]}...")

                # Check if plan was modified
                if data.get('plan_changed'):
                    self.log("✓ Plan was marked as changed", "PASS")

                    # Fetch updated plan
                    time.sleep(1)
                    updated_response = self.session.get(f"{BASE_URL}/api/plan/current")
                    if updated_response.status_code == 200:
                        updated_data = updated_response.json()
                        if updated_data.get('success'):
                            updated_meals = updated_data['plan']['meals']
                            updated_first_meal = updated_meals[0]
                            new_recipe = updated_first_meal.get('recipe_name')

                            self.log(f"  New meal: {new_recipe}")

                            if new_recipe != original_recipe:
                                self.log("✓ Meal was successfully swapped", "PASS")
                            else:
                                self.log("⚠ Recipe didn't change", "WARN")

                            return True
                else:
                    self.log("⚠ Plan change not detected", "WARN")
                    return False
            else:
                self.log(f"✗ Swap failed: {data.get('error')}", "FAIL")
                return False
        else:
            self.log(f"✗ Request failed (status: {response.status_code})", "FAIL")
            return False

    def run_all_tests(self):
        """Run all day selector tests."""
        results = []

        tests = [
            ("Select 3 Specific Days", self.test_select_specific_days),
            ("Full Week (7 days)", self.test_full_week),
            ("Swap Specific Day", self.test_swap_meal),
        ]

        for test_name, test_func in tests:
            try:
                result = test_func()
                results.append((test_name, "PASS" if result else "FAIL"))
            except Exception as e:
                self.log(f"✗ Exception: {str(e)}", "ERROR")
                results.append((test_name, "ERROR"))
            time.sleep(1)

        # Summary
        print()
        print("=" * 60)
        print("TEST SUMMARY")
        print("=" * 60)

        passed = sum(1 for _, status in results if status == "PASS")

        for test_name, status in results:
            icon = "✓" if status == "PASS" else "✗"
            print(f"{icon} {test_name}: {status}")

        print()
        print(f"Total: {passed}/{len(results)} passed")

        if passed == len(results):
            print()
            print("🎉 Day selector functionality works correctly!")
        else:
            print()
            print("⚠️  Some tests failed. Review output above.")

        return passed == len(results)


if __name__ == "__main__":
    tester = DaySelectorTester()
    success = tester.run_all_tests()
    exit(0 if success else 1)
