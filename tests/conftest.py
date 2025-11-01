"""
Pytest configuration and shared fixtures.

Fixtures are reusable test setup that can be injected into tests.
"""

import pytest
import tempfile
import shutil
import subprocess
import time
from pathlib import Path
from datetime import datetime

from src.data.database import DatabaseInterface
from src.data.models import Recipe, MealEvent, UserProfile, MealPlan, PlannedMeal


@pytest.fixture
def temp_db_dir():
    """
    Create a temporary database directory for testing.

    This fixture is automatically cleaned up after each test.
    """
    temp_dir = tempfile.mkdtemp()
    yield temp_dir
    shutil.rmtree(temp_dir)


@pytest.fixture
def db(temp_db_dir):
    """
    Create a fresh DatabaseInterface for each test.

    Usage in tests:
        def test_something(db):
            db.save_user_profile(...)
    """
    return DatabaseInterface(db_dir=temp_db_dir)


@pytest.fixture
def sample_recipe():
    """Sample recipe for testing."""
    return Recipe(
        id="12345",
        name="Honey Ginger Chicken",
        description="Delicious Asian-inspired chicken dish",
        ingredients=["chicken breast", "honey", "ginger", "soy sauce"],
        ingredients_raw=["2 lbs chicken breast", "3 tbsp honey", "2 tbsp ginger", "1/4 cup soy sauce"],
        steps=["Marinate chicken", "Cook on high heat", "Add sauce", "Serve with rice"],
        servings=4,
        serving_size="1 chicken breast",
        tags=["asian", "30-minutes-or-less", "easy"],
        estimated_time=30,
        cuisine="Asian",
        difficulty="easy",
    )


@pytest.fixture
def sample_user_profile():
    """Sample user profile for testing."""
    return UserProfile(
        household_size=4,
        cooking_for={"adults": 2, "kids": 2},
        dietary_restrictions=["dairy-free"],
        allergens=["peanuts"],
        favorite_cuisines=["italian", "mexican", "asian"],
        disliked_ingredients=["olives", "anchovies"],
        preferred_proteins=["chicken", "salmon"],
        spice_tolerance="medium",
        max_weeknight_cooking_time=45,
        max_weekend_cooking_time=90,
        variety_preference="high",
        onboarding_completed=True,
        created_at=datetime(2025, 10, 13, 10, 0, 0),
        updated_at=datetime(2025, 10, 13, 10, 0, 0),
    )


@pytest.fixture
def sample_meal_event(sample_recipe):
    """Sample meal event for testing."""
    return MealEvent(
        date="2025-10-20",
        day_of_week="Monday",
        meal_type="dinner",
        recipe_id=sample_recipe.id,
        recipe_name=sample_recipe.name,
        recipe_cuisine=sample_recipe.cuisine,
        recipe_difficulty=sample_recipe.difficulty,
        servings_planned=4,
        servings_actual=6,
        ingredients_snapshot=sample_recipe.ingredients_raw,
        modifications={"doubled_garlic": True},
        substitutions={"soy_sauce": "tamari"},
        user_rating=5,
        cooking_time_actual=35,
        notes="Kids loved this!",
        would_make_again=True,
        created_at=datetime(2025, 10, 20, 18, 30, 0),
    )


@pytest.fixture
def sample_meal_plan():
    """Sample meal plan for testing."""
    meals = [
        PlannedMeal(
            date="2025-10-20",
            meal_type="dinner",
            recipe_id="12345",
            recipe_name="Honey Ginger Chicken",
            servings=4,
        ),
        PlannedMeal(
            date="2025-10-21",
            meal_type="dinner",
            recipe_id="12346",
            recipe_name="Spaghetti Carbonara",
            servings=4,
        ),
    ]

    return MealPlan(
        week_of="2025-10-20",
        meals=meals,
        preferences_applied=["variety", "time_constraints"],
        created_at=datetime(2025, 10, 20, 10, 0, 0),
    )


# ============================================================================
# Playwright Web Testing Fixtures
# ============================================================================

@pytest.fixture(scope="session")
def flask_app():
    """
    Start Flask app in background for web testing.

    Yields the base URL where the app is running.
    Automatically stops the server when tests complete.
    """
    # Start Flask server in background
    flask_process = subprocess.Popen(
        ["python3", "src/web/app.py"],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        cwd="/home/jack_wright/dinner-assistant"
    )

    # Wait for server to start
    time.sleep(3)

    # Yield the base URL
    base_url = "http://localhost:5000"
    yield base_url

    # Cleanup: stop the server
    flask_process.terminate()
    flask_process.wait(timeout=5)


@pytest.fixture(scope="function")
def browser_context_args(browser_context_args):
    """
    Configure Playwright browser context for headed testing.

    Returns:
        dict: Browser context configuration with viewport and slowmo settings.
    """
    return {
        **browser_context_args,
        "viewport": {
            "width": 1920,
            "height": 1080,
        },
        "ignore_https_errors": True,
    }


@pytest.fixture(scope="session")
def browser_type_launch_args(browser_type_launch_args):
    """
    Configure browser launch args to use headless mode by default.
    This helps avoid dependency issues on systems without full GUI support.
    """
    return {
        **browser_type_launch_args,
        "headless": True,
        "args": [
            "--no-sandbox",
            "--disable-setuid-sandbox",
            "--disable-dev-shm-usage",
            "--disable-gpu",
        ],
    }
