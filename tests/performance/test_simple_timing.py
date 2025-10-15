"""
Simple timing test for meal plan generation.

This test measures how long it takes to generate a meal plan with the
simple command: "make me a meal plan"

Run with: pytest tests/performance/test_simple_timing.py -v -s
"""

import pytest
import requests
import time
from typing import Dict, Any

from .instrumentation import (
    PerformanceMonitor,
    PerformanceTestContext,
)


BASE_URL = "http://127.0.0.1:5000"


class TestSimpleTiming:
    """Simple timing tests for common user actions."""

    @pytest.fixture(autouse=True)
    def setup(self):
        """Setup for each test - creates a new session."""
        self.session = requests.Session()
        self.monitor = PerformanceMonitor()
        yield
        self.session.close()

    @pytest.mark.timeout(120)
    @pytest.mark.performance
    def test_simple_meal_plan_timing(self):
        """
        Time how long it takes to create a meal plan with: "make me a meal plan"

        This test:
        - Completes onboarding if needed
        - Sends the simple message: "make me a meal plan"
        - Times the total duration
        - Breaks down LLM vs database time
        - Prints detailed timing report
        """
        with PerformanceTestContext("Simple Meal Plan Generation") as ctx:
            # Step 1: Check if onboarding needed
            print("\n  [1/2] Checking onboarding status...")
            response = self.session.get(f"{BASE_URL}/api/onboarding/check")
            assert response.status_code == 200

            needs_onboarding = response.json().get('needs_onboarding', False)

            if needs_onboarding:
                print("  Completing onboarding first...")
                self._complete_onboarding()
            else:
                print("  ✓ Already onboarded")

            # Step 2: Create meal plan with simple message
            print("\n  [2/2] Creating meal plan...")
            print("  Message: 'make me a meal plan'")
            print("  Starting timer...\n")

            start_time = time.time()

            response = self.session.post(
                f"{BASE_URL}/api/chat",
                json={"message": "make me a meal plan"},
                timeout=120  # 2 minute timeout
            )

            total_duration = time.time() - start_time

            # Validate response
            assert response.status_code == 200, f"Chat API failed: {response.status_code}"
            data = response.json()
            assert data.get('success'), f"Chat failed: {data.get('error')}"

            meal_plan_id = data.get('meal_plan_id')
            assert meal_plan_id, "No meal plan ID returned"

            # Get performance metrics
            metrics = ctx.get_metrics()
            summary = metrics.summary()

            # Print detailed timing report
            print("\n" + "="*70)
            print("     Simple Meal Plan Generation - Timing Report")
            print("="*70)
            print(f"\nUser message: \"make me a meal plan\"")
            print(f"\n⏱️  Total time: {total_duration:.2f}s")

            # LLM breakdown
            llm_stats = summary['llm_calls']
            if llm_stats['count'] > 0:
                print(f"\n🤖 LLM Calls:")
                print(f"  Count: {llm_stats['count']}")
                print(f"  Total time: {llm_stats['total_time']:.2f}s")
                print(f"  Average: {llm_stats['avg_time']:.2f}s per call")
                llm_percentage = (llm_stats['total_time'] / total_duration) * 100
                print(f"  % of total time: {llm_percentage:.1f}%")

            # Database breakdown
            db_stats = summary['database_queries']
            if db_stats['count'] > 0:
                print(f"\n💾 Database Queries:")
                print(f"  Count: {db_stats['count']}")
                print(f"  Total time: {db_stats['total_time']:.2f}s")
                print(f"  Average: {db_stats['avg_time']:.3f}s per query")
                db_percentage = (db_stats['total_time'] / total_duration) * 100
                print(f"  % of total time: {db_percentage:.1f}%")

            # HTTP breakdown
            http_stats = summary['http_requests']
            if http_stats['count'] > 0:
                print(f"\n🌐 HTTP Requests:")
                print(f"  Count: {http_stats['count']}")
                print(f"  Total time: {http_stats['total_time']:.2f}s")

            # Time breakdown
            llm_time = llm_stats['total_time']
            db_time = db_stats['total_time']
            other_time = total_duration - llm_time - db_time

            print(f"\n📊 Time Breakdown:")
            print(f"  LLM processing: {(llm_time/total_duration)*100:.1f}%")
            print(f"  Database: {(db_time/total_duration)*100:.1f}%")
            print(f"  Other (network, processing): {(other_time/total_duration)*100:.1f}%")

            # Result info
            print(f"\n✅ Result:")
            print(f"  Meal plan ID: {meal_plan_id}")
            print(f"  Response: {data.get('response', '')[:100]}...")

            print("\n" + "="*70 + "\n")

            # Assertions
            assert total_duration < 120, f"Took too long: {total_duration:.2f}s (>2 minutes)"

            if total_duration > 60:
                print(f"  ⚠️  Warning: Generation took {total_duration:.2f}s (>1 minute)")
            elif total_duration > 90:
                print(f"  🔴 SLOW: Generation took {total_duration:.2f}s (>90 seconds)")
            else:
                print(f"  ✓ Reasonable speed: {total_duration:.2f}s")

    @pytest.mark.timeout(120)
    @pytest.mark.performance
    def test_shopping_list_timing(self):
        """
        Time how long it takes to generate a shopping list.
        """
        # First ensure we have a meal plan
        self._ensure_meal_plan()

        with PerformanceTestContext("Shopping List Generation") as ctx:
            print("\n  Creating shopping list...")
            print("  Message: 'create shopping list'")
            print("  Starting timer...\n")

            start_time = time.time()

            response = self.session.post(
                f"{BASE_URL}/api/chat",
                json={"message": "create shopping list"},
                timeout=60
            )

            total_duration = time.time() - start_time

            assert response.status_code == 200
            data = response.json()
            assert data.get('success')

            # Get metrics
            metrics = ctx.get_metrics()
            summary = metrics.summary()

            # Print report
            print("\n" + "="*70)
            print("     Shopping List Generation - Timing Report")
            print("="*70)
            print(f"\n⏱️  Total time: {total_duration:.2f}s")

            llm_stats = summary['llm_calls']
            print(f"\n🤖 LLM Calls: {llm_stats['count']} ({llm_stats['total_time']:.2f}s)")

            db_stats = summary['database_queries']
            print(f"💾 Database Queries: {db_stats['count']} ({db_stats['total_time']:.2f}s)")

            print("\n" + "="*70 + "\n")

            assert total_duration < 60, f"Shopping list took too long: {total_duration:.2f}s"

    @pytest.mark.timeout(60)
    @pytest.mark.performance
    def test_cook_page_recipe_load_timing(self):
        """
        Time how long it takes to load a recipe on the cook page.
        """
        # Ensure meal plan exists
        self._ensure_meal_plan()

        # Get a recipe ID from the meal plan
        response = self.session.get(f"{BASE_URL}/api/plan/current")
        assert response.status_code == 200
        plan_data = response.json()

        if not plan_data.get('success') or not plan_data['plan']['meals']:
            pytest.skip("No meals in plan to test")

        recipe_id = plan_data['plan']['meals'][0]['recipe_id']

        with PerformanceTestContext("Cook Page Recipe Load") as ctx:
            print(f"\n  Loading recipe: {recipe_id}")
            print("  Starting timer...\n")

            start_time = time.time()

            response = self.session.get(f"{BASE_URL}/api/cook/{recipe_id}")

            total_duration = time.time() - start_time

            assert response.status_code == 200
            data = response.json()
            assert data.get('success')

            # Get metrics
            metrics = ctx.get_metrics()
            summary = metrics.summary()

            # Print report
            print("\n" + "="*70)
            print("     Cook Page Recipe Load - Timing Report")
            print("="*70)
            print(f"\n⏱️  Total time: {total_duration:.2f}s")

            llm_stats = summary['llm_calls']
            print(f"\n🤖 LLM Calls: {llm_stats['count']} ({llm_stats['total_time']:.2f}s)")

            db_stats = summary['database_queries']
            print(f"💾 Database Queries: {db_stats['count']} ({db_stats['total_time']:.2f}s)")

            print(f"\n✅ Recipe: {data.get('recipe_name')}")
            print(f"   Ingredients: {len(data.get('ingredients', []))}")
            print(f"   Steps: {len(data.get('steps', []))}")

            print("\n" + "="*70 + "\n")

            if total_duration > 10:
                print(f"  ⚠️  Warning: Recipe load took {total_duration:.2f}s (>10s)")

            assert total_duration < 30, f"Recipe load took too long: {total_duration:.2f}s"

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
            self.session.post(
                f"{BASE_URL}/api/chat",
                json={"message": "make me a meal plan"},
                timeout=120
            )


if __name__ == "__main__":
    # Run tests standalone
    pytest.main([__file__, "-v", "-s"])
