"""Unit tests for backup_recipes serialization and round-trip."""
import pytest
from datetime import datetime
from src.data.models import MealPlan, PlannedMeal, Recipe


@pytest.fixture
def sample_recipe():
    """Create a sample recipe for testing."""
    return Recipe(
        id="recipe-123",
        name="Test Pasta",
        description="Delicious pasta",
        ingredients=["pasta", "tomato sauce"],
        ingredients_raw=["1 lb pasta", "2 cups tomato sauce"],
        steps=["Boil pasta", "Add sauce"],
        servings=4,
        serving_size="1 cup",
        tags=["italian", "main-dish", "vegetarian", "30-minutes-or-less"],
        estimated_time=30,
        cuisine="Italian",
    )


@pytest.fixture
def sample_backup_recipes():
    """Create sample backup recipes for testing."""
    return [
        Recipe(
            id=f"backup-{i}",
            name=f"Backup Recipe {i}",
            description="A backup option",
            ingredients=["ingredient1", "ingredient2"],
            ingredients_raw=["1 cup ingredient1", "2 tbsp ingredient2"],
            steps=["Step 1", "Step 2"],
            servings=4,
            serving_size="1 serving",
            tags=["main-dish", "vegetarian"] if i % 2 == 0 else ["main-dish", "healthy"],
            estimated_time=30 + i * 5,
            cuisine="American" if i % 2 == 0 else "Italian",
        )
        for i in range(5)
    ]


@pytest.fixture
def sample_meal_plan(sample_recipe, sample_backup_recipes):
    """Create a sample meal plan with backup recipes."""
    meals = [
        PlannedMeal(
            date="2025-01-20",
            meal_type="dinner",
            recipe=sample_recipe,
            servings=4,
        )
    ]
    return MealPlan(
        id="plan-123",
        week_of="2025-01-20",
        meals=meals,
        backup_recipes={"mixed": sample_backup_recipes},
    )


class TestBackupRecipesSerialization:
    """Test backup_recipes serialization in MealPlan.to_dict()."""

    def test_to_dict_includes_backup_recipes(self, sample_meal_plan):
        """Verify backup_recipes are included in to_dict() output."""
        result = sample_meal_plan.to_dict()

        assert "backup_recipes" in result
        assert len(result["backup_recipes"]) == 5

    def test_to_dict_backup_recipes_are_lightweight(self, sample_meal_plan):
        """Verify backup recipes only contain required fields."""
        result = sample_meal_plan.to_dict()

        for backup in result["backup_recipes"]:
            # Should have these fields
            assert "id" in backup
            assert "name" in backup
            assert "estimated_time" in backup
            assert "cuisine" in backup
            assert "diet_tags" in backup

            # Should NOT have heavy fields
            assert "description" not in backup
            assert "ingredients" not in backup
            assert "steps" not in backup

    def test_to_dict_extracts_diet_tags(self, sample_meal_plan):
        """Verify diet_tags are extracted from recipe tags."""
        result = sample_meal_plan.to_dict()

        # First backup has "vegetarian" tag
        backup_with_veg = [b for b in result["backup_recipes"] if "vegetarian" in b["diet_tags"]]
        assert len(backup_with_veg) > 0

    def test_to_dict_caps_at_20_backups(self, sample_recipe):
        """Verify backup recipes are capped at 20."""
        # Create 30 backup recipes
        many_backups = [
            Recipe(
                id=f"backup-{i}",
                name=f"Backup {i}",
                description="",
                ingredients=[],
                ingredients_raw=[],
                steps=[],
                servings=4,
                serving_size="",
                tags=["main-dish"],
            )
            for i in range(30)
        ]

        plan = MealPlan(
            week_of="2025-01-20",
            meals=[PlannedMeal(date="2025-01-20", meal_type="dinner", recipe=sample_recipe, servings=4)],
            backup_recipes={"mixed": many_backups},
        )

        result = plan.to_dict()
        assert len(result["backup_recipes"]) == 20

    def test_to_dict_empty_backups(self, sample_recipe):
        """Verify empty backup_recipes serializes to empty list."""
        plan = MealPlan(
            week_of="2025-01-20",
            meals=[PlannedMeal(date="2025-01-20", meal_type="dinner", recipe=sample_recipe, servings=4)],
            backup_recipes={},
        )

        result = plan.to_dict()
        assert result["backup_recipes"] == []


class TestBackupRecipesDeserialization:
    """Test backup_recipes deserialization in MealPlan.from_dict()."""

    def test_from_dict_restores_backup_recipes(self, sample_meal_plan):
        """Verify backup_recipes are restored from dict."""
        # Serialize
        data = sample_meal_plan.to_dict()

        # Deserialize
        restored = MealPlan.from_dict(data)

        assert "mixed" in restored.backup_recipes
        assert len(restored.backup_recipes["mixed"]) == 5

    def test_from_dict_backup_recipe_fields(self, sample_meal_plan):
        """Verify restored backup recipes have expected fields."""
        data = sample_meal_plan.to_dict()
        restored = MealPlan.from_dict(data)

        backup = restored.backup_recipes["mixed"][0]
        assert backup.id.startswith("backup-")
        assert backup.name.startswith("Backup Recipe")
        assert backup.estimated_time is not None
        assert backup.cuisine is not None

    def test_from_dict_handles_missing_backups(self, sample_recipe):
        """Verify from_dict handles missing backup_recipes gracefully."""
        # Old format without backup_recipes
        data = {
            "id": "plan-old",
            "week_of": "2025-01-20",
            "meals": [
                {
                    "date": "2025-01-20",
                    "meal_type": "dinner",
                    "recipe": sample_recipe.to_dict(),
                    "servings": 4,
                }
            ],
            "created_at": datetime.now().isoformat(),
            "preferences_applied": [],
            # No backup_recipes key
        }

        restored = MealPlan.from_dict(data)
        assert restored.backup_recipes == {}

    def test_round_trip_preserves_data(self, sample_meal_plan):
        """Verify full round-trip preserves backup recipe data."""
        # Serialize
        data = sample_meal_plan.to_dict()

        # Deserialize
        restored = MealPlan.from_dict(data)

        # Re-serialize
        data2 = restored.to_dict()

        # Compare
        assert len(data["backup_recipes"]) == len(data2["backup_recipes"])
        for orig, restored in zip(data["backup_recipes"], data2["backup_recipes"]):
            assert orig["id"] == restored["id"]
            assert orig["name"] == restored["name"]
            assert orig["estimated_time"] == restored["estimated_time"]
            assert orig["cuisine"] == restored["cuisine"]
