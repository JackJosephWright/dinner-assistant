"""
Comprehensive web performance tests that operate the live website
and monitor backend behavior.

These tests:
- Make real HTTP requests to the running Flask app
- Track LLM API calls and timing
- Count database queries
- Detect duplicate/redundant requests
- Measure end-to-end performance
"""

import pytest
import requests
import time
from datetime import datetime, timedelta
from typing import Dict, Any

from .instrumentation import (
    PerformanceMonitor,
    PerformanceTestContext,
    detect_duplicate_requests
)


# Assumes Flask app is running on localhost:5000
BASE_URL = "http://127.0.0.1:5000"


class TestWebPerformance:
    """Performance tests for the web application."""

    @pytest.fixture(autouse=True)
    def setup(self):
        """Setup for each test - creates a new session."""
        self.session = requests.Session()
        self.monitor = PerformanceMonitor()
        yield
        self.session.close()

    def test_home_page_performance(self):
        """Test home page load time."""
        with PerformanceTestContext("Home Page Load"):
            response = self.session.get(f"{BASE_URL}/")

            assert response.status_code == 200
            # Should redirect to /plan quickly
            assert "/plan" in response.url

    def test_plan_page_cold_load(self):
        """Test plan page initial load (no meal plan yet)."""
        with PerformanceTestContext("Plan Page Cold Load"):
            start = time.time()
            response = self.session.get(f"{BASE_URL}/plan")
            duration = time.time() - start

            assert response.status_code == 200
            assert duration < 2.0, f"Plan page took {duration:.2f}s (should be <2s)"

            # Check for expected elements
            assert "chatContainer" in response.text or "meal" in response.text.lower()

    @pytest.mark.timeout(120)  # 2 minute timeout
    def test_complete_meal_planning_workflow(self):
        """
        Test complete workflow: onboarding → plan meals → get plan → preload

        This simulates a real user journey and tracks all backend activity.
        """
        with PerformanceTestContext("Complete Meal Planning Workflow") as ctx:
            # Step 1: Check onboarding status
            print("\n  [1/5] Checking onboarding status...")
            response = self.session.get(f"{BASE_URL}/api/onboarding/check")
            assert response.status_code == 200

            needs_onboarding = response.json().get('needs_onboarding', False)

            # Step 2: Complete onboarding if needed
            if needs_onboarding:
                print("  [2/5] Completing onboarding...")
                self._complete_onboarding()
            else:
                print("  [2/5] Already onboarded, skipping...")

            # Step 3: Create meal plan via chat
            print("  [3/5] Creating meal plan via chat...")
            plan_start = time.time()

            today = datetime.now()
            days_until_monday = (7 - today.weekday()) % 7 or 7
            next_monday = today + timedelta(days=days_until_monday)
            start_date = next_monday.strftime("%Y-%m-%d")

            message = f"Plan 7 days of meals starting {start_date}"

            response = self.session.post(
                f"{BASE_URL}/api/chat",
                json={"message": message},
                timeout=60
            )

            plan_duration = time.time() - plan_start

            assert response.status_code == 200, f"Chat API failed: {response.status_code}"
            data = response.json()
            assert data.get('success'), f"Chat failed: {data.get('error')}"

            meal_plan_id = data.get('meal_plan_id')
            assert meal_plan_id, "No meal plan ID returned"

            print(f"    ✓ Meal plan created in {plan_duration:.2f}s")
            print(f"      Plan ID: {meal_plan_id}")

            # Check if planning was reasonable speed
            if plan_duration > 60:
                print(f"    ⚠ Warning: Planning took {plan_duration:.2f}s (>60s)")

            # Step 4: Get current plan (test enriched data endpoint)
            print("  [4/5] Fetching current plan...")
            fetch_start = time.time()

            response = self.session.get(f"{BASE_URL}/api/plan/current")
            fetch_duration = time.time() - fetch_start

            assert response.status_code == 200
            plan_data = response.json()
            assert plan_data.get('success')

            meals = plan_data['plan']['meals']
            print(f"    ✓ Plan fetched in {fetch_duration:.2f}s")
            print(f"      Meals: {len(meals)}")

            # Verify enriched data present (N+1 query fix)
            if meals:
                first_meal = meals[0]
                has_enriched = all(k in first_meal for k in ['description', 'estimated_time', 'cuisine'])
                if has_enriched:
                    print("    ✓ Enriched data present (N+1 fix working)")
                else:
                    print("    ⚠ Missing enriched data - N+1 queries may be occurring")

            # Step 5: Preload shop/cook data
            print("  [5/5] Preloading shop & cook data...")
            preload_start = time.time()

            response = self.session.post(f"{BASE_URL}/api/plan/preload")
            preload_duration = time.time() - preload_start

            assert response.status_code == 200
            preload_data = response.json()
            assert preload_data.get('success')

            print(f"    ✓ Preload completed in {preload_duration:.2f}s")
            print(f"      Shopping list created: {preload_data.get('shopping_list_created')}")

            # Analyze metrics for issues
            metrics = ctx.get_metrics()
            duplicates = detect_duplicate_requests(metrics)

            if duplicates:
                print(f"\n  ⚠️  DUPLICATES DETECTED:")
                for dup in duplicates:
                    print(f"    - {dup['type'].upper()}: {dup['pattern']} ({dup['count']} times)")

            # Performance assertions
            assert plan_duration < 90, f"Planning took too long: {plan_duration:.2f}s"
            assert fetch_duration < 2, f"Fetch took too long: {fetch_duration:.2f}s"

    def test_shopping_list_generation_performance(self):
        """Test shopping list generation speed."""
        # First ensure we have a meal plan
        self._ensure_meal_plan()

        with PerformanceTestContext("Shopping List Generation"):
            start = time.time()

            response = self.session.post(f"{BASE_URL}/api/shop", json={})
            duration = time.time() - start

            if response.status_code == 200:
                data = response.json()
                if data.get('success'):
                    print(f"    ✓ Shopping list created in {duration:.2f}s")
                    print(f"      List ID: {data.get('grocery_list_id')}")

                    # Check if cached (should be fast)
                    if duration < 5:
                        print("    ✓ Fast generation (likely cached)")
                    else:
                        print(f"    ⚠ Slow generation: {duration:.2f}s")

    def test_shop_page_load_speed(self):
        """Test that shop page loads quickly after preload."""
        # Ensure preload happened
        self._ensure_meal_plan()
        self.session.post(f"{BASE_URL}/api/plan/preload")

        with PerformanceTestContext("Shop Page Load (After Preload)"):
            start = time.time()
            response = self.session.get(f"{BASE_URL}/shop")
            duration = time.time() - start

            assert response.status_code == 200

            if duration < 0.5:
                print(f"    ✓ FAST: {duration:.2f}s")
            elif duration < 2.0:
                print(f"    ✓ Good: {duration:.2f}s")
            else:
                print(f"    ⚠ Slow: {duration:.2f}s (preload may not be working)")

            # Should be nearly instant if preloaded
            assert duration < 5.0, f"Shop page too slow: {duration:.2f}s"

    def test_concurrent_request_handling(self):
        """Test how system handles concurrent requests (duplicate detection)."""
        self._ensure_meal_plan()

        with PerformanceTestContext("Concurrent Request Test"):
            import concurrent.futures

            # Simulate multiple tabs/requests at once
            def make_request():
                try:
                    response = self.session.post(f"{BASE_URL}/api/plan/preload")
                    return response.status_code, time.time()
                except Exception as e:
                    return None, time.time()

            with concurrent.futures.ThreadPoolExecutor(max_workers=5) as executor:
                futures = [executor.submit(make_request) for _ in range(5)]
                results = [f.result() for f in futures]

            successful = sum(1 for code, _ in results if code == 200)
            conflict = sum(1 for code, _ in results if code == 409)

            print(f"    Requests: 5 concurrent")
            print(f"    Successful: {successful}")
            print(f"    Conflicts (409): {conflict}")

            # Check for duplicate work
            metrics = self.monitor.get_metrics()
            duplicates = detect_duplicate_requests(metrics)

            if duplicates:
                print(f"    ⚠️  DUPLICATE WORK DETECTED:")
                for dup in duplicates:
                    print(f"      - {dup}")

    # Helper methods

    def _complete_onboarding(self):
        """Complete the onboarding flow."""
        response = self.session.post(f"{BASE_URL}/api/onboarding/start")
        assert response.status_code == 200

        answers = [
            "2 adults",
            "No allergies",
            "Italian, Mexican, Asian",
            "30-45 minutes",
            "None",
            "Medium spice",
            "yes"
        ]

        for answer in answers:
            response = self.session.post(
                f"{BASE_URL}/api/onboarding/answer",
                json={"answer": answer}
            )
            assert response.status_code == 200
            if response.json().get('is_complete'):
                break

    def _ensure_meal_plan(self):
        """Ensure a meal plan exists in the session."""
        response = self.session.get(f"{BASE_URL}/api/plan/current")
        if response.status_code == 404 or not response.json().get('success'):
            # Create a meal plan
            today = datetime.now()
            days_until_monday = (7 - today.weekday()) % 7 or 7
            next_monday = today + timedelta(days=days_until_monday)
            start_date = next_monday.strftime("%Y-%m-%d")

            self.session.post(
                f"{BASE_URL}/api/chat",
                json={"message": f"Plan 5 days starting {start_date}"},
                timeout=60
            )


@pytest.mark.benchmark
class TestPerformanceRegression:
    """Tests to catch performance regressions."""

    def test_plan_page_benchmark(self, benchmark):
        """Benchmark plan page load."""
        session = requests.Session()

        def load_plan_page():
            response = session.get(f"{BASE_URL}/plan")
            assert response.status_code == 200
            return response

        result = benchmark(load_plan_page)
        session.close()

    def test_api_plan_current_benchmark(self, benchmark):
        """Benchmark the /api/plan/current endpoint."""
        session = requests.Session()

        # Setup: ensure plan exists
        response = session.get(f"{BASE_URL}/api/plan/current")
        if response.status_code == 404:
            pytest.skip("No meal plan available for benchmark")

        def fetch_current_plan():
            response = session.get(f"{BASE_URL}/api/plan/current")
            assert response.status_code == 200
            return response

        result = benchmark(fetch_current_plan)
        session.close()


if __name__ == "__main__":
    # Run tests standalone
    pytest.main([__file__, "-v", "-s"])
