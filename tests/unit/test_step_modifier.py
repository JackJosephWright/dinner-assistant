"""
Tests for recipe step modification module.

Tests cover:
- Step ID generation
- Cook profile lookups
- Ingredient delta building
- Safety validation
- Structural validation
- Confidence scoring
- Method change refusal
"""

import pytest
from unittest.mock import Mock, patch, MagicMock

from src.cook_profiles import (
    CookProfile,
    PROTEIN_COOK_PROFILES,
    normalize_protein_name,
    get_cook_profile,
    has_cook_profile,
    should_refuse_instruction_mod,
    METHOD_CHANGE_KEYWORDS,
)
from src.step_modifier import (
    generate_step_id,
    add_step_ids,
    IngredientDelta,
    build_ingredient_delta,
    validate_modified_steps,
    validate_structural_limits,
    score_modification_confidence,
    apply_step_modifications,
    modify_recipe_steps,
    StepModificationResult,
)


# =============================================================================
# Step ID Generation Tests
# =============================================================================

class TestStepIdGeneration:
    """Tests for step ID generation."""

    def test_generate_step_id_basic(self):
        """Step ID includes index and content hash."""
        step_id = generate_step_id("Preheat oven to 350°F.", 0)
        assert step_id.startswith("s0_")
        assert len(step_id) == 9  # s0_ + 6 hex chars

    def test_generate_step_id_deterministic(self):
        """Same content produces same ID."""
        id1 = generate_step_id("Brown the chicken until golden.", 1)
        id2 = generate_step_id("Brown the chicken until golden.", 1)
        assert id1 == id2

    def test_generate_step_id_different_content(self):
        """Different content produces different IDs."""
        id1 = generate_step_id("Brown the chicken until golden.", 1)
        id2 = generate_step_id("Brown the beef until golden.", 1)
        assert id1 != id2

    def test_generate_step_id_different_index(self):
        """Different index produces different IDs."""
        id1 = generate_step_id("Brown the chicken.", 0)
        id2 = generate_step_id("Brown the chicken.", 1)
        assert id1 != id2

    def test_generate_step_id_case_insensitive(self):
        """IDs are case-insensitive (normalized to lowercase)."""
        id1 = generate_step_id("Brown the chicken.", 0)
        id2 = generate_step_id("BROWN THE CHICKEN.", 0)
        assert id1 == id2

    def test_add_step_ids(self):
        """add_step_ids creates proper structure."""
        steps = ["Step one.", "Step two.", "Step three."]
        result = add_step_ids(steps)

        assert len(result) == 3
        for i, step in enumerate(result):
            assert "step_id" in step
            assert step["index"] == i
            assert step["text"] == steps[i]


# =============================================================================
# Cook Profile Tests
# =============================================================================

class TestCookProfiles:
    """Tests for cook profile lookups."""

    def test_normalize_protein_name_simple(self):
        """Simple protein names normalize correctly."""
        assert normalize_protein_name("chicken breast") == "chicken_breast"
        assert normalize_protein_name("ground beef") == "ground_beef"
        assert normalize_protein_name("shrimp") == "shrimp"

    def test_normalize_protein_name_with_adjectives(self):
        """Adjectives are stripped from protein names."""
        assert normalize_protein_name("boneless chicken breast") == "chicken_breast"
        assert normalize_protein_name("fresh large shrimp") == "shrimp"

    def test_normalize_protein_name_with_quantities(self):
        """Quantities are stripped from protein names."""
        assert normalize_protein_name("1 lb ground beef") == "ground_beef"
        assert normalize_protein_name("2 cups diced chicken") == "chicken"

    def test_get_cook_profile_exists(self):
        """get_cook_profile returns profile for known proteins."""
        profile = get_cook_profile("chicken breast")
        assert profile is not None
        assert profile.safe_temp == 165

    def test_get_cook_profile_shrimp(self):
        """Shrimp has no safe temp (visual doneness only)."""
        profile = get_cook_profile("shrimp")
        assert profile is not None
        assert profile.safe_temp is None
        assert "pink" in profile.cue.lower()

    def test_get_cook_profile_unknown(self):
        """get_cook_profile returns None for unknown ingredients."""
        profile = get_cook_profile("avocado")
        assert profile is None

    def test_has_cook_profile(self):
        """has_cook_profile correctly identifies proteins."""
        assert has_cook_profile("chicken breast") is True
        assert has_cook_profile("ground beef") is True
        assert has_cook_profile("lettuce") is False


# =============================================================================
# Method Change Refusal Tests
# =============================================================================

class TestMethodChangeRefusal:
    """Tests for cooking method change detection."""

    def test_should_refuse_air_fryer(self):
        """Air fryer requests should be refused."""
        assert should_refuse_instruction_mod("make it in the air fryer") is True
        assert should_refuse_instruction_mod("air fry the chicken") is True

    def test_should_refuse_slow_cooker(self):
        """Slow cooker requests should be refused."""
        assert should_refuse_instruction_mod("make it in slow cooker") is True
        assert should_refuse_instruction_mod("use my crockpot") is True

    def test_should_refuse_instant_pot(self):
        """Instant pot requests should be refused."""
        assert should_refuse_instruction_mod("make it in instant pot") is True
        assert should_refuse_instruction_mod("pressure cook it") is True

    def test_should_refuse_raw(self):
        """Raw/no-cook requests should be refused."""
        assert should_refuse_instruction_mod("make it raw") is True
        assert should_refuse_instruction_mod("no cook version") is True

    def test_should_allow_ingredient_swap(self):
        """Simple ingredient swaps should be allowed."""
        assert should_refuse_instruction_mod("use shrimp instead of chicken") is False
        assert should_refuse_instruction_mod("replace beef with tofu") is False

    def test_all_keywords_covered(self):
        """All method change keywords trigger refusal."""
        for keyword in METHOD_CHANGE_KEYWORDS:
            assert should_refuse_instruction_mod(f"please {keyword} this") is True


# =============================================================================
# Ingredient Delta Tests
# =============================================================================

class TestIngredientDelta:
    """Tests for ingredient delta building."""

    def test_build_delta_protein_swap(self):
        """Builds delta for protein swap with profiles."""
        # New format from patch_engine
        patch_ops = [{
            "op": "replace_ingredient",
            "target_name": "chicken breast",
            "replacement": {
                "name": "shrimp",
            }
        }]

        delta = build_ingredient_delta(patch_ops, ["1 lb chicken breast"])

        assert delta is not None
        assert delta.original == "chicken breast"
        assert delta.replacement == "shrimp"
        assert delta.role == "protein"
        assert delta.has_profiles is True

    def test_build_delta_no_profiles(self):
        """Builds delta without profiles for unknown ingredients."""
        # New format from patch_engine
        patch_ops = [{
            "op": "replace_ingredient",
            "target_name": "zucchini",
            "replacement": {
                "name": "squash",
            }
        }]

        delta = build_ingredient_delta(patch_ops, ["2 zucchini"])

        # May return None or delta with no profiles
        if delta:
            assert delta.has_profiles is False

    def test_build_delta_add_op_ignored(self):
        """Add operations don't create delta."""
        patch_ops = [{
            "op": "add_ingredient",
            "ingredient": {"name": "1 cup mushrooms"}
        }]

        delta = build_ingredient_delta(patch_ops, ["1 lb chicken"])
        assert delta is None

    def test_delta_time_diff_description(self):
        """Delta provides human-readable time diff."""
        delta = IngredientDelta(
            original="chicken breast",
            replacement="shrimp",
            role="protein",
            cook_profile_from=get_cook_profile("chicken breast"),
            cook_profile_to=get_cook_profile("shrimp"),
        )

        desc = delta.time_diff_description
        assert "min" in desc
        assert "→" in desc


# =============================================================================
# Safety Validation Tests
# =============================================================================

class TestSafetyValidation:
    """Tests for step modification safety validation."""

    def test_validate_temp_retained(self):
        """No violation when temp is retained."""
        original = [{"text": "Cook chicken to 165°F."}]
        modified = [{"text": "Cook shrimp to 145°F."}]
        delta = IngredientDelta(
            original="chicken",
            replacement="shrimp",
            role="protein",
            cook_profile_from=get_cook_profile("chicken"),
            cook_profile_to=get_cook_profile("shrimp"),
        )

        violations = validate_modified_steps(original, modified, delta)
        assert len(violations) == 0

    def test_validate_temp_replaced_with_cue(self):
        """No violation when temp replaced with doneness cue."""
        original = [{"text": "Cook chicken to 165°F."}]
        modified = [{"text": "Cook shrimp until pink and opaque."}]
        delta = IngredientDelta(
            original="chicken",
            replacement="shrimp",
            role="protein",
            cook_profile_from=get_cook_profile("chicken"),
            cook_profile_to=get_cook_profile("shrimp"),
        )

        violations = validate_modified_steps(original, modified, delta)
        assert len(violations) == 0

    def test_validate_temp_removed_violation(self):
        """Violation when temp removed without doneness cue."""
        original = [{"text": "Cook chicken to 165°F."}]
        modified = [{"text": "Cook the protein for a while."}]
        delta = IngredientDelta(
            original="chicken",
            replacement="shrimp",
            role="protein",
            cook_profile_from=get_cook_profile("chicken"),
            cook_profile_to=get_cook_profile("shrimp"),
        )

        violations = validate_modified_steps(original, modified, delta)
        assert len(violations) > 0
        assert "temperature" in violations[0].lower() or "doneness" in violations[0].lower()

    def test_validate_unsafe_temp(self):
        """Violation when modified temp is below safe minimum."""
        original = [{"text": "Cook to 165°F."}]
        modified = [{"text": "Cook chicken to 120°F."}]  # Way too low
        delta = IngredientDelta(
            original="shrimp",
            replacement="chicken",
            role="protein",
            cook_profile_from=get_cook_profile("shrimp"),
            cook_profile_to=get_cook_profile("chicken"),  # Requires 165°F
        )

        violations = validate_modified_steps(original, modified, delta)
        assert len(violations) > 0
        assert "120" in violations[0]


# =============================================================================
# Structural Limits Tests
# =============================================================================

class TestStructuralLimits:
    """Tests for structural limit validation."""

    def test_validate_single_new_step_ok(self):
        """Single new step is allowed."""
        result = {
            "new_steps": [{"text": "Drain the grease.", "reason": "drain grease"}],
            "removed_steps": [],
        }

        violations = validate_structural_limits(result)
        assert len(violations) == 0

    def test_validate_too_many_new_steps(self):
        """More than 1 new step is not allowed."""
        result = {
            "new_steps": [
                {"text": "Step A", "reason": "drain"},
                {"text": "Step B", "reason": "dry"},
            ],
            "removed_steps": [],
        }

        violations = validate_structural_limits(result)
        assert len(violations) > 0
        assert "Too many new steps" in violations[0]

    def test_validate_too_many_removed_steps(self):
        """More than 1 removed step is not allowed."""
        result = {
            "new_steps": [],
            "removed_steps": [
                {"step_id": "s1_abc"},
                {"step_id": "s2_def"},
            ],
        }

        violations = validate_structural_limits(result)
        assert len(violations) > 0
        assert "Too many removed steps" in violations[0]

    def test_validate_new_step_reason(self):
        """New step must have allowed reason."""
        result = {
            "new_steps": [{"text": "Add extra sauce.", "reason": "more flavor"}],
            "removed_steps": [],
        }

        violations = validate_structural_limits(result)
        assert len(violations) > 0
        assert "not in allowed list" in violations[0]


# =============================================================================
# Confidence Scoring Tests
# =============================================================================

class TestConfidenceScoring:
    """Tests for modification confidence scoring."""

    def test_score_no_modifications(self):
        """No modifications = high confidence."""
        delta = IngredientDelta(
            original="chicken",
            replacement="turkey",
            role="protein",
            cook_profile_from=get_cook_profile("chicken"),
            cook_profile_to=get_cook_profile("ground_turkey"),
        )

        score = score_modification_confidence(
            num_steps_modified=0,
            num_steps_total=5,
            delta=delta,
            violations=[],
        )
        assert score == 1.0

    def test_score_few_modifications(self):
        """1-2 modifications = good confidence."""
        delta = IngredientDelta(
            original="chicken",
            replacement="shrimp",
            role="protein",
            cook_profile_from=get_cook_profile("chicken"),
            cook_profile_to=get_cook_profile("shrimp"),
        )

        score = score_modification_confidence(
            num_steps_modified=2,
            num_steps_total=6,
            delta=delta,
            violations=[],
        )
        assert score >= 0.85

    def test_score_many_modifications(self):
        """Many modifications = lower confidence."""
        delta = IngredientDelta(
            original="chicken",
            replacement="shrimp",
            role="protein",
            cook_profile_from=get_cook_profile("chicken"),
            cook_profile_to=get_cook_profile("shrimp"),
        )

        score = score_modification_confidence(
            num_steps_modified=5,
            num_steps_total=6,
            delta=delta,
            violations=[],
        )
        assert score < 0.6

    def test_score_with_violations(self):
        """Violations reduce confidence."""
        delta = IngredientDelta(
            original="chicken",
            replacement="shrimp",
            role="protein",
            cook_profile_from=get_cook_profile("chicken"),
            cook_profile_to=get_cook_profile("shrimp"),
        )

        score = score_modification_confidence(
            num_steps_modified=1,
            num_steps_total=5,
            delta=delta,
            violations=["Violation 1", "Violation 2"],
        )
        assert score < 0.7  # 0.85 + 0.05 - 0.30 = 0.60

    def test_score_clamped_to_zero(self):
        """Score can't go below 0."""
        delta = IngredientDelta(
            original="chicken",
            replacement="shrimp",
            role="protein",
            cook_profile_from=get_cook_profile("chicken"),
            cook_profile_to=get_cook_profile("shrimp"),
        )

        score = score_modification_confidence(
            num_steps_modified=10,
            num_steps_total=10,
            delta=delta,
            violations=["V1", "V2", "V3", "V4", "V5"],  # -0.75
        )
        assert score == 0.0


# =============================================================================
# Apply Step Modifications Tests
# =============================================================================

class TestApplyStepModifications:
    """Tests for applying step modifications."""

    def test_apply_simple_modification(self):
        """Apply a simple text modification."""
        original = ["Step A", "Step B with chicken", "Step C"]
        mods = {
            "modified_steps": [{
                "step_id": "s1_placeholder",  # Will match by index
                "original_text": "Step B with chicken",
                "modified_text": "Step B with shrimp",
                "reason": "protein swap",
            }],
            "new_steps": [],
            "removed_steps": [],
        }

        # The step_id needs to match what add_step_ids generates
        steps_with_ids = add_step_ids(original)
        mods["modified_steps"][0]["step_id"] = steps_with_ids[1]["step_id"]

        result = apply_step_modifications(original, mods)

        assert len(result) == 3
        assert "shrimp" in result[1]["text"]
        assert result[1].get("original_text") == "Step B with chicken"

    def test_apply_removed_step(self):
        """Remove a step from the list."""
        original = ["Step A", "Remove this step", "Step C"]
        steps_with_ids = add_step_ids(original)

        mods = {
            "modified_steps": [],
            "new_steps": [],
            "removed_steps": [{"step_id": steps_with_ids[1]["step_id"]}],
        }

        result = apply_step_modifications(original, mods)

        assert len(result) == 2
        assert "Remove" not in result[0]["text"]
        assert "Remove" not in result[1]["text"]

    def test_apply_new_step(self):
        """Add a new step."""
        original = ["Step A", "Step B"]
        steps_with_ids = add_step_ids(original)

        mods = {
            "modified_steps": [],
            "new_steps": [{
                "text": "New drain step",
                "insert_after": steps_with_ids[0]["step_id"],
                "reason": "drain grease",
            }],
            "removed_steps": [],
        }

        result = apply_step_modifications(original, mods)

        assert len(result) == 3
        assert "drain" in result[1]["text"].lower()
        assert result[1].get("is_new") is True


# =============================================================================
# Full Integration Tests
# =============================================================================

class TestModifyRecipeSteps:
    """Integration tests for the full modify_recipe_steps function."""

    def test_modify_refuses_method_change(self):
        """Refuses requests involving cooking method changes."""
        result = modify_recipe_steps(
            recipe_name="Chicken Stir Fry",
            steps=["Cook chicken in pan."],
            user_request="make it in the air fryer",
            patch_ops=[],
            original_ingredients=["chicken"],
            client=Mock(),
        )

        assert result.success is False
        assert result.refused_reason is not None
        assert "method" in result.refused_reason.lower()

    def test_modify_no_protein_swap(self):
        """Returns unchanged steps when no protein swap detected."""
        result = modify_recipe_steps(
            recipe_name="Veggie Stir Fry",
            steps=["Cook vegetables."],
            user_request="add more salt",
            patch_ops=[{
                "op": "add",
                "value": {"text": "salt"}
            }],
            original_ingredients=["broccoli"],
            client=Mock(),
        )

        assert result.success is True
        assert result.confidence == 1.0
        assert len(result.modified_steps) == 1

    def test_modify_missing_profiles(self):
        """Handles protein swap without cook profiles gracefully."""
        # Use chicken (has profile) -> ostrich (no profile) to get partial match
        result = modify_recipe_steps(
            recipe_name="Mystery Dish",
            steps=["Cook the protein."],
            user_request="use ostrich instead of chicken",
            patch_ops=[{
                "op": "replace_ingredient",
                "target_name": "chicken",
                "replacement": {
                    "name": "ostrich",
                }
            }],
            original_ingredients=["chicken meat"],
            client=Mock(),
        )

        assert result.success is True
        assert result.confidence == 0.5
        assert "profile" in result.warnings[0].lower()

    @patch("src.step_modifier.generate_step_modifications")
    def test_modify_full_success(self, mock_generate):
        """Full successful modification flow."""
        # Need to get the actual step_id that will be generated
        step_text = "Cook chicken for 10 minutes."
        expected_step_id = generate_step_id(step_text, 0)

        mock_generate.return_value = {
            "modified_steps": [{
                "step_id": expected_step_id,
                "original_text": step_text,
                "modified_text": "Cook shrimp for 3 minutes until pink.",
                "reason": "Reduced time for shrimp",
            }],
            "new_steps": [],
            "removed_steps": [],
            "cooking_notes": ["Shrimp cooks much faster!"],
        }

        result = modify_recipe_steps(
            recipe_name="Kung Pao Chicken",
            steps=[step_text],
            user_request="use shrimp instead of chicken",
            patch_ops=[{
                "op": "replace_ingredient",
                "target_name": "chicken breast",
                "replacement": {
                    "name": "shrimp",
                }
            }],
            original_ingredients=["1 lb chicken breast"],
            client=Mock(),
        )

        assert result.success is True
        assert result.confidence >= 0.80
        assert len(result.step_modifications) == 1
        assert "shrimp" in result.modified_steps[0]["text"].lower()


# =============================================================================
# Edge Cases
# =============================================================================

class TestEdgeCases:
    """Edge case tests."""

    def test_empty_steps(self):
        """Handles empty steps list."""
        result = modify_recipe_steps(
            recipe_name="Empty Recipe",
            steps=[],
            user_request="use beef",
            patch_ops=[],
            original_ingredients=[],
            client=Mock(),
        )

        assert result.success is True
        assert len(result.modified_steps) == 0

    def test_very_long_step(self):
        """Step ID generation handles long steps."""
        long_step = "A" * 1000
        step_id = generate_step_id(long_step, 0)
        assert step_id.startswith("s0_")
        assert len(step_id) == 9

    def test_unicode_in_steps(self):
        """Handles Unicode characters in steps."""
        step_id = generate_step_id("Cook at 350°F for 30 minutes.", 0)
        assert step_id.startswith("s0_")

    def test_special_characters_in_step(self):
        """Handles special characters in steps."""
        step_id = generate_step_id("Add 1/2 cup (4 oz) milk & stir.", 0)
        assert step_id.startswith("s0_")
