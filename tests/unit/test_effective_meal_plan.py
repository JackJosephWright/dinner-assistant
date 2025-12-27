"""
Tests for get_effective_meal_plan() - ensures variants from snapshots are used.
"""

import pytest
import json
import sqlite3
import tempfile
import os
from datetime import datetime
from unittest.mock import MagicMock, patch

from src.data.database import DatabaseInterface
from src.data.models import MealPlan, PlannedMeal, Recipe


@pytest.fixture
def temp_db():
    """Create a temporary database with required tables."""
    with tempfile.TemporaryDirectory() as tmpdir:
        user_db_path = os.path.join(tmpdir, "user_data.db")
        recipes_db_path = os.path.join(tmpdir, "recipes.db")

        # Create user_data.db with required tables
        conn = sqlite3.connect(user_db_path)
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS meal_plans (
                id TEXT PRIMARY KEY,
                user_id INTEGER NOT NULL,
                week_of TEXT NOT NULL,
                created_at TEXT NOT NULL,
                preferences_applied TEXT DEFAULT '{}',
                meals_json TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS meal_plan_snapshots (
                id TEXT PRIMARY KEY,
                user_id INTEGER NOT NULL,
                week_of TEXT NOT NULL,
                version INTEGER DEFAULT 1,
                snapshot_json TEXT NOT NULL,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );
        """)
        conn.close()

        # Create empty recipes.db
        conn = sqlite3.connect(recipes_db_path)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS recipes (
                id INTEGER PRIMARY KEY,
                name TEXT,
                description TEXT,
                ingredients TEXT,
                steps TEXT,
                tags TEXT
            )
        """)
        conn.close()

        # Create DatabaseInterface with temp directory
        db = DatabaseInterface(db_dir=tmpdir)
        yield db, user_db_path


def make_recipe_dict(name="Test Recipe", recipe_id="123"):
    """Create a minimal recipe dict."""
    return {
        "id": recipe_id,
        "name": name,
        "description": "A test recipe",
        "ingredients": ["ingredient1", "ingredient2"],
        "ingredients_raw": ["1 cup ingredient1", "2 tbsp ingredient2"],
        "steps": ["Step 1", "Step 2"],
        "servings": 4,
        "serving_size": "1 serving",
        "tags": ["main-dish"],
        "estimated_time": 30,
        "cuisine": None,
        "difficulty": "easy",
    }


def make_planned_meal_dict(date, recipe_name="Test Recipe", variant=None):
    """Create a minimal planned meal dict."""
    meal = {
        "date": date,
        "meal_type": "dinner",
        "recipe": make_recipe_dict(name=recipe_name),
        "servings": 4,
        "notes": None,
    }
    if variant is not None:
        meal["variant"] = variant
    return meal


class TestGetEffectiveMealPlan:
    """Tests for get_effective_meal_plan()."""

    def test_uses_snapshot_when_available(self, temp_db):
        """Snapshot with planned_meals should be preferred over meal_plans table."""
        db, user_db_path = temp_db
        plan_id = "mp_2025-01-01_20250101120000"
        user_id = 1

        # Insert into legacy meal_plans table (no variant)
        conn = sqlite3.connect(user_db_path)
        conn.execute(
            "INSERT INTO meal_plans (id, user_id, week_of, created_at, preferences_applied, meals_json) VALUES (?, ?, ?, ?, ?, ?)",
            (plan_id, user_id, "2025-01-01", datetime.now().isoformat(), "{}", json.dumps([
                make_planned_meal_dict("2025-01-01", "Original Recipe")
            ]))
        )

        # Insert snapshot with variant
        variant = {
            "id": f"variant:{plan_id}:2025-01-01:dinner",
            "patch_ops": [{"op": "replace_ingredient", "target_index": 0}],
            "compiled_recipe": make_recipe_dict(name="Modified Recipe"),
            "warnings": ["Cooking note 1"],
        }
        snapshot = {
            "id": plan_id,
            "user_id": user_id,
            "week_of": "2025-01-01",
            "created_at": datetime.now().isoformat(),
            "version": 1,
            "planned_meals": [
                make_planned_meal_dict("2025-01-01", "Original Recipe", variant=variant)
            ],
            "grocery_list": None,
        }
        conn.execute(
            "INSERT INTO meal_plan_snapshots (id, user_id, week_of, version, snapshot_json, created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?, ?)",
            (plan_id, user_id, "2025-01-01", 1, json.dumps(snapshot), datetime.now().isoformat(), datetime.now().isoformat())
        )
        conn.commit()
        conn.close()

        # Call get_effective_meal_plan
        result = db.get_effective_meal_plan(plan_id, user_id=user_id)

        # Should use snapshot data (has variant)
        assert result is not None
        assert len(result.meals) == 1
        assert result.meals[0].variant is not None
        assert result.meals[0].variant["compiled_recipe"]["name"] == "Modified Recipe"

    def test_falls_back_to_meal_plans_when_no_snapshot(self, temp_db):
        """Without snapshot, should fall back to meal_plans table."""
        db, user_db_path = temp_db
        plan_id = "mp_2025-01-02_20250102120000"
        user_id = 1

        # Insert into legacy meal_plans table only
        conn = sqlite3.connect(user_db_path)
        conn.execute(
            "INSERT INTO meal_plans (id, user_id, week_of, created_at, preferences_applied, meals_json) VALUES (?, ?, ?, ?, ?, ?)",
            (plan_id, user_id, "2025-01-02", datetime.now().isoformat(), "{}", json.dumps([
                make_planned_meal_dict("2025-01-02", "Legacy Recipe")
            ]))
        )
        conn.commit()
        conn.close()

        # Call get_effective_meal_plan
        result = db.get_effective_meal_plan(plan_id, user_id=user_id)

        # Should use legacy meal_plans data
        assert result is not None
        assert len(result.meals) == 1
        assert result.meals[0].variant is None
        assert result.meals[0].recipe.name == "Legacy Recipe"

    def test_falls_back_when_snapshot_has_no_planned_meals(self, temp_db):
        """Snapshot without planned_meals should fall back to meal_plans."""
        db, user_db_path = temp_db
        plan_id = "mp_2025-01-03_20250103120000"
        user_id = 1

        # Insert into legacy meal_plans table
        conn = sqlite3.connect(user_db_path)
        conn.execute(
            "INSERT INTO meal_plans (id, user_id, week_of, created_at, preferences_applied, meals_json) VALUES (?, ?, ?, ?, ?, ?)",
            (plan_id, user_id, "2025-01-03", datetime.now().isoformat(), "{}", json.dumps([
                make_planned_meal_dict("2025-01-03", "Fallback Recipe")
            ]))
        )

        # Insert partial snapshot (no planned_meals)
        snapshot = {
            "id": plan_id,
            "user_id": user_id,
            "week_of": "2025-01-03",
            "created_at": datetime.now().isoformat(),
            "version": 1,
            # No planned_meals!
            "grocery_list": {"items": []},
        }
        conn.execute(
            "INSERT INTO meal_plan_snapshots (id, user_id, week_of, version, snapshot_json, created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?, ?)",
            (plan_id, user_id, "2025-01-03", 1, json.dumps(snapshot), datetime.now().isoformat(), datetime.now().isoformat())
        )
        conn.commit()
        conn.close()

        # Call get_effective_meal_plan
        result = db.get_effective_meal_plan(plan_id, user_id=user_id)

        # Should fall back to legacy meal_plans
        assert result is not None
        assert result.meals[0].recipe.name == "Fallback Recipe"

    def test_returns_none_when_nothing_exists(self, temp_db):
        """Should return None when neither snapshot nor meal_plan exists."""
        db, _ = temp_db

        result = db.get_effective_meal_plan("nonexistent_id", user_id=1)

        assert result is None


class TestShoppingAgentUsesVariants:
    """Integration test: shopping agent should use variant ingredients."""

    def test_shopping_collects_variant_ingredients(self, temp_db):
        """Shopping agent should use mango (from variant) not pineapple (from base)."""
        db, user_db_path = temp_db
        plan_id = "mp_2025-01-04_20250104120000"
        user_id = 1

        # Base recipe has pineapple
        base_recipe = make_recipe_dict(name="Vegetarian Pineapple Curry")
        base_recipe["ingredients_raw"] = ["1 medium pineapple", "2 cups rice"]

        # Variant has mango instead
        variant_recipe = make_recipe_dict(name="Vegetarian Pineapple Curry (modified)")
        variant_recipe["ingredients_raw"] = ["1 medium mango", "2 cups rice"]

        variant = {
            "id": f"variant:{plan_id}:2025-01-04:dinner",
            "patch_ops": [{"op": "replace_ingredient", "target_index": 0}],
            "compiled_recipe": variant_recipe,
            "warnings": ["Mango cooks faster than pineapple"],
        }

        # Create snapshot with variant
        snapshot = {
            "id": plan_id,
            "user_id": user_id,
            "week_of": "2025-01-04",
            "created_at": datetime.now().isoformat(),
            "version": 1,
            "planned_meals": [{
                "date": "2025-01-04",
                "meal_type": "dinner",
                "recipe": base_recipe,
                "servings": 4,
                "notes": None,
                "variant": variant,
            }],
            "grocery_list": None,
        }

        conn = sqlite3.connect(user_db_path)
        conn.execute(
            "INSERT INTO meal_plan_snapshots (id, user_id, week_of, version, snapshot_json, created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?, ?)",
            (plan_id, user_id, "2025-01-04", 1, json.dumps(snapshot), datetime.now().isoformat(), datetime.now().isoformat())
        )
        conn.commit()
        conn.close()

        # Load meal plan - should get variant
        meal_plan = db.get_effective_meal_plan(plan_id, user_id=user_id)

        assert meal_plan is not None
        assert len(meal_plan.meals) == 1

        # get_effective_recipe should return variant recipe
        effective_recipe = meal_plan.meals[0].get_effective_recipe()
        assert effective_recipe is not None
        assert "mango" in effective_recipe.ingredients_raw[0].lower()
        assert "pineapple" not in effective_recipe.ingredients_raw[0].lower()
