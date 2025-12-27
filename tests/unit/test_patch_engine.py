"""
Unit tests for patch_engine.py - Recipe Variants v0.

Tests cover:
- PatchOp pydantic validation
- PatchGenResult validation
- RecipeVariant validation
- validate_ops() function
- apply_ops() function with ordering
- Variant ID utilities
"""

import pytest
from datetime import datetime

import sys
sys.path.insert(0, 'src')

from patch_engine import (
    PatchOp,
    PatchOpType,
    PatchGenResult,
    RecipeVariant,
    IngredientReplacement,
    ValidationError,
    validate_ops,
    apply_ops,
    create_variant_id,
    parse_variant_id,
    _parse_quantity,
    _format_quantity,
    _scale_ingredients,
)
from pydantic import ValidationError as PydanticValidationError


# =============================================================================
# PatchOp Model Tests
# =============================================================================

class TestPatchOpValidation:
    """Tests for PatchOp pydantic model validation."""

    def test_replace_ingredient_valid(self):
        """Valid replace_ingredient op."""
        op = PatchOp(
            op=PatchOpType.REPLACE_INGREDIENT,
            target_index=2,
            target_name="white rice",
            replacement=IngredientReplacement(name="brown rice", quantity="2 cups"),
        )
        assert op.op == PatchOpType.REPLACE_INGREDIENT
        assert op.target_index == 2
        assert op.replacement.name == "brown rice"

    def test_replace_ingredient_missing_target_index(self):
        """replace_ingredient without target_index fails."""
        with pytest.raises(PydanticValidationError) as exc:
            PatchOp(
                op=PatchOpType.REPLACE_INGREDIENT,
                target_name="white rice",
                replacement=IngredientReplacement(name="brown rice", quantity="2 cups"),
            )
        assert "target_index" in str(exc.value)

    def test_replace_ingredient_missing_replacement(self):
        """replace_ingredient without replacement fails."""
        with pytest.raises(PydanticValidationError) as exc:
            PatchOp(
                op=PatchOpType.REPLACE_INGREDIENT,
                target_index=2,
                target_name="white rice",
            )
        assert "replacement" in str(exc.value)

    def test_add_ingredient_valid(self):
        """Valid add_ingredient op."""
        op = PatchOp(
            op=PatchOpType.ADD_INGREDIENT,
            new_ingredient="1 tbsp fresh basil",
        )
        assert op.new_ingredient == "1 tbsp fresh basil"

    def test_add_ingredient_missing_new_ingredient(self):
        """add_ingredient without new_ingredient fails."""
        with pytest.raises(PydanticValidationError) as exc:
            PatchOp(op=PatchOpType.ADD_INGREDIENT)
        assert "new_ingredient" in str(exc.value)

    def test_remove_ingredient_valid(self):
        """Valid remove_ingredient op with acknowledged=True."""
        op = PatchOp(
            op=PatchOpType.REMOVE_INGREDIENT,
            target_index=3,
            target_name="cilantro",
            acknowledged=True,
        )
        assert op.acknowledged is True

    def test_remove_ingredient_not_acknowledged(self):
        """remove_ingredient without acknowledged=True fails."""
        with pytest.raises(PydanticValidationError) as exc:
            PatchOp(
                op=PatchOpType.REMOVE_INGREDIENT,
                target_index=3,
                target_name="cilantro",
                acknowledged=False,
            )
        assert "acknowledged" in str(exc.value)

    def test_scale_servings_valid(self):
        """Valid scale_servings op."""
        op = PatchOp(
            op=PatchOpType.SCALE_SERVINGS,
            scale_factor=2.0,
        )
        assert op.scale_factor == 2.0

    def test_scale_servings_negative(self):
        """scale_servings with negative factor fails."""
        with pytest.raises(PydanticValidationError) as exc:
            PatchOp(
                op=PatchOpType.SCALE_SERVINGS,
                scale_factor=-1.0,
            )
        assert "positive" in str(exc.value)

    def test_scale_servings_zero(self):
        """scale_servings with zero factor fails."""
        with pytest.raises(PydanticValidationError) as exc:
            PatchOp(
                op=PatchOpType.SCALE_SERVINGS,
                scale_factor=0,
            )
        assert "positive" in str(exc.value)


# =============================================================================
# PatchGenResult Tests
# =============================================================================

class TestPatchGenResult:
    """Tests for PatchGenResult model validation."""

    def test_valid_with_ops(self):
        """Valid result with operations."""
        result = PatchGenResult(
            ops=[
                PatchOp(
                    op=PatchOpType.REPLACE_INGREDIENT,
                    target_index=0,
                    target_name="chicken",
                    replacement=IngredientReplacement(name="tofu", quantity="1 lb"),
                )
            ]
        )
        assert len(result.ops) == 1
        assert not result.needs_clarification

    def test_valid_needs_clarification(self):
        """Valid result needing clarification."""
        result = PatchGenResult(
            needs_clarification=True,
            clarification_message="Which ingredient did you mean by 'the meat'?",
        )
        assert result.needs_clarification
        assert len(result.ops) == 0

    def test_clarification_with_ops_fails(self):
        """needs_clarification=True with ops fails."""
        with pytest.raises(PydanticValidationError) as exc:
            PatchGenResult(
                ops=[
                    PatchOp(
                        op=PatchOpType.SCALE_SERVINGS,
                        scale_factor=2.0,
                    )
                ],
                needs_clarification=True,
                clarification_message="This shouldn't be valid",
            )
        assert "needs_clarification" in str(exc.value)

    def test_clarification_without_message_fails(self):
        """needs_clarification=True without message fails."""
        with pytest.raises(PydanticValidationError) as exc:
            PatchGenResult(
                needs_clarification=True,
            )
        assert "clarification_message" in str(exc.value)


# =============================================================================
# RecipeVariant Tests
# =============================================================================

class TestRecipeVariant:
    """Tests for RecipeVariant model validation."""

    def test_valid_variant(self):
        """Valid variant with proper ID format."""
        variant = RecipeVariant(
            variant_id="variant:snap_abc123:2025-01-03:dinner",
            base_recipe_id="123456",
            patch_ops=[],
            compiled_recipe={"id": "123456", "name": "Test Recipe", "ingredients_raw": []},
        )
        assert variant.compiler_version == "v0"

    def test_invalid_variant_id_format(self):
        """Invalid variant ID format fails."""
        with pytest.raises(PydanticValidationError) as exc:
            RecipeVariant(
                variant_id="invalid-format",
                base_recipe_id="123456",
                patch_ops=[],
                compiled_recipe={},
            )
        assert "variant_id" in str(exc.value)

    def test_invalid_variant_id_missing_meal_type(self):
        """Variant ID without meal_type fails."""
        with pytest.raises(PydanticValidationError) as exc:
            RecipeVariant(
                variant_id="variant:snap_abc:2025-01-03",
                base_recipe_id="123456",
                patch_ops=[],
                compiled_recipe={},
            )
        assert "variant_id" in str(exc.value)

    def test_variant_id_all_meal_types(self):
        """All valid meal types work."""
        for meal_type in ["breakfast", "lunch", "dinner", "snack"]:
            variant = RecipeVariant(
                variant_id=f"variant:snap_abc:2025-01-03:{meal_type}",
                base_recipe_id="123456",
                patch_ops=[],
                compiled_recipe={},
            )
            assert meal_type in variant.variant_id


# =============================================================================
# validate_ops() Tests
# =============================================================================

class TestValidateOps:
    """Tests for validate_ops() function."""

    @pytest.fixture
    def sample_ingredients(self):
        """Sample ingredient list for testing."""
        return [
            "2 lbs chicken breast",
            "1 cup white rice",
            "2 tbsp soy sauce",
            "1 bunch cilantro, chopped",
            "3 cloves garlic, minced",
        ]

    def test_valid_replace(self, sample_ingredients):
        """Valid replace operation passes."""
        ops = [
            PatchOp(
                op=PatchOpType.REPLACE_INGREDIENT,
                target_index=0,
                target_name="chicken",
                replacement=IngredientReplacement(name="tofu", quantity="1 lb"),
            )
        ]
        is_valid, errors = validate_ops(ops, sample_ingredients)
        assert is_valid
        assert len(errors) == 0

    def test_target_name_mismatch(self, sample_ingredients):
        """Target name not in ingredient fails."""
        ops = [
            PatchOp(
                op=PatchOpType.REPLACE_INGREDIENT,
                target_index=0,
                target_name="beef",  # Wrong - ingredient is chicken
                replacement=IngredientReplacement(name="tofu", quantity="1 lb"),
            )
        ]
        is_valid, errors = validate_ops(ops, sample_ingredients)
        assert not is_valid
        assert len(errors) == 1
        assert "beef" in errors[0]

    def test_target_index_out_of_bounds(self, sample_ingredients):
        """Target index out of bounds fails."""
        ops = [
            PatchOp(
                op=PatchOpType.REPLACE_INGREDIENT,
                target_index=99,
                target_name="chicken",
                replacement=IngredientReplacement(name="tofu", quantity="1 lb"),
            )
        ]
        is_valid, errors = validate_ops(ops, sample_ingredients)
        assert not is_valid
        assert "out of bounds" in errors[0]

    def test_substring_match_works(self, sample_ingredients):
        """Substring match is sufficient."""
        ops = [
            PatchOp(
                op=PatchOpType.REPLACE_INGREDIENT,
                target_index=1,
                target_name="rice",  # Matches "white rice"
                replacement=IngredientReplacement(name="brown rice", quantity="1 cup"),
            )
        ]
        is_valid, errors = validate_ops(ops, sample_ingredients)
        assert is_valid

    def test_case_insensitive_match(self, sample_ingredients):
        """Target name match is case insensitive."""
        ops = [
            PatchOp(
                op=PatchOpType.REPLACE_INGREDIENT,
                target_index=0,
                target_name="CHICKEN",  # Uppercase
                replacement=IngredientReplacement(name="tofu", quantity="1 lb"),
            )
        ]
        is_valid, errors = validate_ops(ops, sample_ingredients)
        assert is_valid

    def test_multiple_ops_all_valid(self, sample_ingredients):
        """Multiple valid ops pass."""
        ops = [
            PatchOp(
                op=PatchOpType.REPLACE_INGREDIENT,
                target_index=0,
                target_name="chicken",
                replacement=IngredientReplacement(name="tofu", quantity="1 lb"),
            ),
            PatchOp(
                op=PatchOpType.REMOVE_INGREDIENT,
                target_index=3,
                target_name="cilantro",
                acknowledged=True,
            ),
        ]
        is_valid, errors = validate_ops(ops, sample_ingredients)
        assert is_valid

    def test_multiple_ops_one_invalid(self, sample_ingredients):
        """If any op is invalid, whole batch fails."""
        ops = [
            PatchOp(
                op=PatchOpType.REPLACE_INGREDIENT,
                target_index=0,
                target_name="chicken",
                replacement=IngredientReplacement(name="tofu", quantity="1 lb"),
            ),
            PatchOp(
                op=PatchOpType.REPLACE_INGREDIENT,
                target_index=1,
                target_name="pasta",  # Wrong - ingredient is rice
                replacement=IngredientReplacement(name="noodles", quantity="1 cup"),
            ),
        ]
        is_valid, errors = validate_ops(ops, sample_ingredients)
        assert not is_valid
        assert len(errors) == 1


# =============================================================================
# apply_ops() Tests
# =============================================================================

class TestApplyOps:
    """Tests for apply_ops() function."""

    @pytest.fixture
    def sample_ingredients(self):
        """Sample ingredient list for testing."""
        return [
            "2 lbs chicken breast",
            "1 cup white rice",
            "2 tbsp soy sauce",
            "1 bunch cilantro",
            "3 cloves garlic",
        ]

    def test_replace_ingredient(self, sample_ingredients):
        """Replace operation modifies ingredient in place."""
        ops = [
            PatchOp(
                op=PatchOpType.REPLACE_INGREDIENT,
                target_index=0,
                target_name="chicken",
                replacement=IngredientReplacement(name="tofu", quantity="1 lb"),
            )
        ]
        result, servings = apply_ops(ops, sample_ingredients)
        assert result[0] == "1 lb tofu"
        assert len(result) == len(sample_ingredients)

    def test_add_ingredient(self, sample_ingredients):
        """Add operation appends to end."""
        ops = [
            PatchOp(
                op=PatchOpType.ADD_INGREDIENT,
                new_ingredient="1 tbsp sesame oil",
            )
        ]
        result, servings = apply_ops(ops, sample_ingredients)
        assert len(result) == len(sample_ingredients) + 1
        assert result[-1] == "1 tbsp sesame oil"

    def test_remove_ingredient(self, sample_ingredients):
        """Remove operation removes ingredient."""
        ops = [
            PatchOp(
                op=PatchOpType.REMOVE_INGREDIENT,
                target_index=3,
                target_name="cilantro",
                acknowledged=True,
            )
        ]
        result, servings = apply_ops(ops, sample_ingredients)
        assert len(result) == len(sample_ingredients) - 1
        assert "cilantro" not in " ".join(result)

    def test_scale_servings_double(self, sample_ingredients):
        """Scale by 2x doubles quantities."""
        ops = [
            PatchOp(
                op=PatchOpType.SCALE_SERVINGS,
                scale_factor=2.0,
            )
        ]
        result, servings = apply_ops(ops, sample_ingredients, original_servings=4)
        assert servings == 8
        assert "4 lbs" in result[0]  # 2 lbs -> 4 lbs
        assert "2 cup" in result[1]  # 1 cup -> 2 cup (no pluralization in v0)

    def test_scale_servings_half(self, sample_ingredients):
        """Scale by 0.5 halves quantities."""
        ops = [
            PatchOp(
                op=PatchOpType.SCALE_SERVINGS,
                scale_factor=0.5,
            )
        ]
        result, servings = apply_ops(ops, sample_ingredients, original_servings=4)
        assert servings == 2
        assert "1 lb" in result[0]  # 2 lbs -> 1 lb

    def test_apply_ordering_remove_descending(self, sample_ingredients):
        """Multiple removes applied in descending order to preserve indices."""
        ops = [
            PatchOp(
                op=PatchOpType.REMOVE_INGREDIENT,
                target_index=1,
                target_name="rice",
                acknowledged=True,
            ),
            PatchOp(
                op=PatchOpType.REMOVE_INGREDIENT,
                target_index=3,
                target_name="cilantro",
                acknowledged=True,
            ),
        ]
        result, servings = apply_ops(ops, sample_ingredients)
        assert len(result) == 3
        assert "rice" not in " ".join(result)
        assert "cilantro" not in " ".join(result)
        # Remaining: chicken, soy sauce, garlic
        assert "chicken" in result[0]
        assert "soy sauce" in result[1]
        assert "garlic" in result[2]

    def test_complex_multi_op(self, sample_ingredients):
        """Complex operation with multiple op types."""
        ops = [
            PatchOp(
                op=PatchOpType.SCALE_SERVINGS,
                scale_factor=2.0,
            ),
            PatchOp(
                op=PatchOpType.REPLACE_INGREDIENT,
                target_index=0,
                target_name="chicken",
                replacement=IngredientReplacement(name="tofu", quantity="2 lbs"),
            ),
            PatchOp(
                op=PatchOpType.REMOVE_INGREDIENT,
                target_index=3,
                target_name="cilantro",
                acknowledged=True,
            ),
            PatchOp(
                op=PatchOpType.ADD_INGREDIENT,
                new_ingredient="1 tbsp ginger",
            ),
        ]
        result, servings = apply_ops(ops, sample_ingredients, original_servings=2)

        assert servings == 4
        assert "tofu" in result[0]
        assert "cilantro" not in " ".join(result)
        assert result[-1] == "1 tbsp ginger"
        assert len(result) == 5  # 5 original - 1 removed + 1 added = 5

    def test_does_not_mutate_original(self, sample_ingredients):
        """apply_ops does not mutate the original list."""
        original_copy = list(sample_ingredients)
        ops = [
            PatchOp(
                op=PatchOpType.REPLACE_INGREDIENT,
                target_index=0,
                target_name="chicken",
                replacement=IngredientReplacement(name="tofu", quantity="1 lb"),
            )
        ]
        result, _ = apply_ops(ops, sample_ingredients)
        assert sample_ingredients == original_copy


# =============================================================================
# Quantity Parsing Tests
# =============================================================================

class TestQuantityParsing:
    """Tests for quantity parsing helpers."""

    def test_parse_integer(self):
        """Parse integer quantity."""
        assert _parse_quantity("2") == 2.0

    def test_parse_decimal(self):
        """Parse decimal quantity."""
        assert _parse_quantity("1.5") == 1.5

    def test_parse_fraction(self):
        """Parse fraction quantity."""
        assert _parse_quantity("1/2") == 0.5
        assert _parse_quantity("3/4") == 0.75

    def test_parse_mixed_number(self):
        """Parse mixed number quantity."""
        assert _parse_quantity("1 1/2") == 1.5
        assert _parse_quantity("2 1/4") == 2.25

    def test_format_whole_number(self):
        """Format whole numbers."""
        assert _format_quantity(2.0) == "2"
        assert _format_quantity(10.0) == "10"

    def test_format_common_fractions(self):
        """Format common fractions."""
        assert _format_quantity(0.5) == "1/2"
        assert _format_quantity(0.25) == "1/4"
        assert _format_quantity(0.75) == "3/4"

    def test_format_mixed_numbers(self):
        """Format mixed numbers."""
        assert _format_quantity(1.5) == "1 1/2"
        assert _format_quantity(2.25) == "2 1/4"

    def test_scale_ingredients_simple(self):
        """Scale simple ingredient quantities."""
        ingredients = ["2 cups flour", "1 tsp salt"]
        result = _scale_ingredients(ingredients, 2.0)
        assert "4 cups" in result[0]
        assert "2 tsp" in result[1]

    def test_scale_ingredients_no_quantity(self):
        """Ingredients without quantity preserved as-is."""
        ingredients = ["salt to taste", "fresh herbs"]
        result = _scale_ingredients(ingredients, 2.0)
        assert result == ingredients


# =============================================================================
# Variant ID Utilities Tests
# =============================================================================

class TestVariantIdUtilities:
    """Tests for variant ID creation and parsing."""

    def test_create_variant_id(self):
        """Create valid variant ID."""
        vid = create_variant_id("snap_abc123", "2025-01-03", "dinner")
        assert vid == "variant:snap_abc123:2025-01-03:dinner"

    def test_parse_variant_id(self):
        """Parse valid variant ID."""
        snapshot_id, date, meal_type = parse_variant_id(
            "variant:snap_abc123:2025-01-03:dinner"
        )
        assert snapshot_id == "snap_abc123"
        assert date == "2025-01-03"
        assert meal_type == "dinner"

    def test_parse_invalid_variant_id(self):
        """Parse invalid variant ID raises error."""
        with pytest.raises(ValueError) as exc:
            parse_variant_id("invalid-format")
        assert "Invalid variant_id format" in str(exc.value)

    def test_roundtrip(self):
        """Create and parse roundtrip."""
        original_snapshot = "snap_xyz789"
        original_date = "2025-12-31"
        original_meal = "breakfast"

        vid = create_variant_id(original_snapshot, original_date, original_meal)
        parsed = parse_variant_id(vid)

        assert parsed == (original_snapshot, original_date, original_meal)
