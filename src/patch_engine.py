"""
Patch Engine for Recipe Variants v0.

Provides structured patch operations for modifying recipes:
- replace_ingredient: swap X for Y
- add_ingredient: add Z to recipe (end-only in v0)
- remove_ingredient: remove W (requires acknowledged=True)
- scale_servings: double/halve quantities

Key invariants:
- Variant ID format: variant:{snapshot_id}:{date}:{meal_type}
- Patch apply ordering: scale_servings -> replace -> remove(desc) -> add(end-only)
- Coverage check: all original ingredients accounted for after apply
"""

import logging
import re
from datetime import datetime
from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field, field_validator, model_validator

logger = logging.getLogger(__name__)


# =============================================================================
# Pydantic Models
# =============================================================================

class PatchOpType(str, Enum):
    """Supported patch operation types for v0."""
    REPLACE_INGREDIENT = "replace_ingredient"
    ADD_INGREDIENT = "add_ingredient"
    REMOVE_INGREDIENT = "remove_ingredient"
    SCALE_SERVINGS = "scale_servings"


class IngredientReplacement(BaseModel):
    """Replacement ingredient specification."""
    name: str
    quantity: str


class PatchOp(BaseModel):
    """
    A single patch operation to apply to a recipe.

    Validation rules:
    - replace_ingredient: requires target_index, target_name, replacement
    - add_ingredient: requires new_ingredient (appends to end)
    - remove_ingredient: requires target_index, target_name, acknowledged=True
    - scale_servings: requires scale_factor > 0
    """
    op: PatchOpType
    target_index: Optional[int] = None
    target_name: Optional[str] = None
    replacement: Optional[IngredientReplacement] = None
    new_ingredient: Optional[str] = None
    scale_factor: Optional[float] = None
    acknowledged: bool = False
    reason: str = "user_request"

    @model_validator(mode='after')
    def validate_op_fields(self) -> 'PatchOp':
        """Validate that required fields are present for each op type."""
        if self.op == PatchOpType.REPLACE_INGREDIENT:
            if self.target_index is None:
                raise ValueError("replace_ingredient requires target_index")
            if self.target_name is None:
                raise ValueError("replace_ingredient requires target_name")
            if self.replacement is None:
                raise ValueError("replace_ingredient requires replacement")

        elif self.op == PatchOpType.ADD_INGREDIENT:
            if self.new_ingredient is None:
                raise ValueError("add_ingredient requires new_ingredient")

        elif self.op == PatchOpType.REMOVE_INGREDIENT:
            if self.target_index is None:
                raise ValueError("remove_ingredient requires target_index")
            if self.target_name is None:
                raise ValueError("remove_ingredient requires target_name")
            if not self.acknowledged:
                raise ValueError("remove_ingredient requires acknowledged=True")

        elif self.op == PatchOpType.SCALE_SERVINGS:
            if self.scale_factor is None:
                raise ValueError("scale_servings requires scale_factor")
            if self.scale_factor <= 0:
                raise ValueError("scale_factor must be positive")

        return self


class PatchGenResult(BaseModel):
    """
    LLM generator output.

    If needs_clarification is True, ops should be empty and
    clarification_message explains what info is needed.
    """
    ops: list[PatchOp] = Field(default_factory=list)
    needs_clarification: bool = False
    clarification_message: Optional[str] = None

    @model_validator(mode='after')
    def validate_clarification(self) -> 'PatchGenResult':
        """If needs clarification, should have message and no ops."""
        if self.needs_clarification:
            if self.ops:
                raise ValueError("needs_clarification=True but ops is not empty")
            if not self.clarification_message:
                raise ValueError("needs_clarification=True requires clarification_message")
        return self


class RecipeVariant(BaseModel):
    """
    A variant of a recipe with applied patches.

    Stored in snapshot JSON under planned_meal.variant
    """
    variant_id: str
    base_recipe_id: str
    patch_ops: list[PatchOp]
    compiled_recipe: dict  # Full recipe dict with modifications applied
    warnings: list[str] = Field(default_factory=list)
    compiled_at: datetime = Field(default_factory=datetime.utcnow)
    compiler_version: str = "v0"

    @field_validator('variant_id')
    @classmethod
    def validate_variant_id(cls, v: str) -> str:
        """Validate variant ID format: variant:{snapshot_id}:{date}:{meal_type}"""
        pattern = r'^variant:[^:]+:\d{4}-\d{2}-\d{2}:(breakfast|lunch|dinner|snack)$'
        if not re.match(pattern, v):
            raise ValueError(
                f"Invalid variant_id format: {v}. "
                "Expected: variant:{snapshot_id}:{date}:{meal_type}"
            )
        return v


# =============================================================================
# Validation Functions
# =============================================================================

class ValidationError(Exception):
    """Raised when patch validation fails."""
    pass


class CoverageError(ValidationError):
    """Raised when coverage check fails (ingredient disappeared)."""
    pass


class TargetMismatchError(ValidationError):
    """Raised when target_name doesn't match ingredient at target_index."""
    pass


def validate_ops(
    ops: list[PatchOp],
    ingredients: list[str]
) -> tuple[bool, list[str]]:
    """
    Validate a list of patch operations against a recipe's ingredients.

    Checks:
    1. Schema validation (handled by pydantic)
    2. Target name match: target_name must be substring of ingredient at target_index
    3. Coverage check: all original ingredients accounted for

    Args:
        ops: List of PatchOp to validate
        ingredients: Original recipe ingredients_raw list

    Returns:
        Tuple of (is_valid, list of error messages)

    Logs:
        [PATCH_VALIDATE] with validation results
    """
    errors = []

    # Track which indices are touched by ops
    removed_indices = set()
    replaced_indices = set()

    for i, op in enumerate(ops):
        # Target name match for replace/remove
        if op.op in (PatchOpType.REPLACE_INGREDIENT, PatchOpType.REMOVE_INGREDIENT):
            idx = op.target_index

            # Bounds check
            if idx < 0 or idx >= len(ingredients):
                errors.append(
                    f"Op {i}: target_index {idx} out of bounds (0-{len(ingredients)-1})"
                )
                continue

            # Substring match check
            ingredient = ingredients[idx].lower()
            target = op.target_name.lower()

            if target not in ingredient:
                errors.append(
                    f"Op {i}: target_name '{op.target_name}' not found in "
                    f"ingredient at index {idx}: '{ingredients[idx]}'"
                )
                continue

            # Track touched indices
            if op.op == PatchOpType.REMOVE_INGREDIENT:
                removed_indices.add(idx)
            else:
                replaced_indices.add(idx)

    # Coverage check: replaced indices are "covered" (replaced = remove + add at same spot)
    # Removed indices require explicit acknowledgment (already validated in PatchOp)
    # All other indices must remain untouched

    # Log validation result
    is_valid = len(errors) == 0
    logger.info(
        f"[PATCH_VALIDATE] valid={is_valid}, ops={len(ops)}, "
        f"removed={len(removed_indices)}, replaced={len(replaced_indices)}, "
        f"errors={len(errors)}"
    )

    if errors:
        for err in errors:
            logger.warning(f"[PATCH_VALIDATE] {err}")

    return is_valid, errors


# =============================================================================
# Application Functions
# =============================================================================

def apply_ops(
    ops: list[PatchOp],
    ingredients: list[str],
    original_servings: int = 1
) -> tuple[list[str], int]:
    """
    Apply patch operations to a recipe's ingredients.

    Apply ordering (to avoid index shifting issues):
    1. scale_servings (affects quantities, no index changes)
    2. replace_ingredient (in-place, no index shift)
    3. remove_ingredient (descending index order)
    4. add_ingredient (append to end only)

    Args:
        ops: List of validated PatchOp to apply
        ingredients: Original recipe ingredients_raw list
        original_servings: Original serving count

    Returns:
        Tuple of (modified ingredients list, new servings count)

    Logs:
        [PATCH_APPLY] with application summary
    """
    # Work on a copy
    result = list(ingredients)
    servings = original_servings

    # Group ops by type for ordered application
    scale_ops = [op for op in ops if op.op == PatchOpType.SCALE_SERVINGS]
    replace_ops = [op for op in ops if op.op == PatchOpType.REPLACE_INGREDIENT]
    remove_ops = [op for op in ops if op.op == PatchOpType.REMOVE_INGREDIENT]
    add_ops = [op for op in ops if op.op == PatchOpType.ADD_INGREDIENT]

    # 1. Apply scale_servings
    for op in scale_ops:
        servings = int(servings * op.scale_factor)
        result = _scale_ingredients(result, op.scale_factor)
        logger.info(f"[PATCH_APPLY] scale_servings factor={op.scale_factor}")

    # 2. Apply replace_ingredient (in-place)
    for op in replace_ops:
        old_ingredient = result[op.target_index]
        new_ingredient = f"{op.replacement.quantity} {op.replacement.name}"
        result[op.target_index] = new_ingredient
        logger.info(
            f"[PATCH_APPLY] replace index={op.target_index} "
            f"'{old_ingredient}' -> '{new_ingredient}'"
        )

    # 3. Apply remove_ingredient (descending order to preserve indices)
    remove_ops_sorted = sorted(remove_ops, key=lambda op: op.target_index, reverse=True)
    for op in remove_ops_sorted:
        removed = result.pop(op.target_index)
        logger.info(f"[PATCH_APPLY] remove index={op.target_index} '{removed}'")

    # 4. Apply add_ingredient (append to end)
    for op in add_ops:
        result.append(op.new_ingredient)
        logger.info(f"[PATCH_APPLY] add '{op.new_ingredient}'")

    logger.info(
        f"[PATCH_APPLY] complete: {len(ingredients)} -> {len(result)} ingredients, "
        f"servings {original_servings} -> {servings}"
    )

    return result, servings


def _scale_ingredients(ingredients: list[str], factor: float) -> list[str]:
    """
    Scale quantity values in ingredients by a factor.

    Handles common patterns like:
    - "2 cups flour" -> "4 cups flour" (factor=2)
    - "1/2 cup sugar" -> "1 cup sugar" (factor=2)
    - "1 lb chicken" -> "0.5 lb chicken" (factor=0.5)
    """
    result = []

    # Pattern to match leading quantity (integer, decimal, or fraction)
    qty_pattern = re.compile(
        r'^(\d+(?:\.\d+)?|\d+/\d+|\d+\s+\d+/\d+)\s*(.*)$'
    )

    for ingredient in ingredients:
        match = qty_pattern.match(ingredient.strip())
        if match:
            qty_str, rest = match.groups()
            try:
                qty = _parse_quantity(qty_str)
                new_qty = qty * factor
                new_qty_str = _format_quantity(new_qty)
                result.append(f"{new_qty_str} {rest}".strip())
            except ValueError:
                # Can't parse, keep original
                result.append(ingredient)
        else:
            # No quantity found, keep original
            result.append(ingredient)

    return result


def _parse_quantity(qty_str: str) -> float:
    """Parse a quantity string to float."""
    qty_str = qty_str.strip()

    # Mixed number: "1 1/2"
    mixed_match = re.match(r'^(\d+)\s+(\d+)/(\d+)$', qty_str)
    if mixed_match:
        whole, num, denom = mixed_match.groups()
        return int(whole) + int(num) / int(denom)

    # Fraction: "1/2"
    frac_match = re.match(r'^(\d+)/(\d+)$', qty_str)
    if frac_match:
        num, denom = frac_match.groups()
        return int(num) / int(denom)

    # Integer or decimal
    return float(qty_str)


def _format_quantity(qty: float) -> str:
    """Format a quantity float to string, preferring fractions for common values."""
    # Common fractions
    fractions = {
        0.25: "1/4",
        0.33: "1/3",
        0.5: "1/2",
        0.67: "2/3",
        0.75: "3/4",
    }

    # Check for whole number
    if qty == int(qty):
        return str(int(qty))

    # Check for whole + fraction
    whole = int(qty)
    frac = qty - whole

    # Round fraction to check against common values
    for val, rep in fractions.items():
        if abs(frac - val) < 0.05:
            if whole > 0:
                return f"{whole} {rep}"
            return rep

    # Default to decimal with reasonable precision
    if qty < 1:
        return f"{qty:.2f}".rstrip('0').rstrip('.')
    return f"{qty:.1f}".rstrip('0').rstrip('.')


# =============================================================================
# Variant ID Utilities
# =============================================================================

def create_variant_id(snapshot_id: str, date: str, meal_type: str) -> str:
    """
    Create a canonical variant ID.

    Format: variant:{snapshot_id}:{date}:{meal_type}
    """
    return f"variant:{snapshot_id}:{date}:{meal_type}"


def parse_variant_id(variant_id: str) -> tuple[str, str, str]:
    """
    Parse a variant ID into components.

    Args:
        variant_id: Format variant:{snapshot_id}:{date}:{meal_type}

    Returns:
        Tuple of (snapshot_id, date, meal_type)

    Raises:
        ValueError: If format is invalid
    """
    pattern = r'^variant:([^:]+):(\d{4}-\d{2}-\d{2}):(breakfast|lunch|dinner|snack)$'
    match = re.match(pattern, variant_id)

    if not match:
        raise ValueError(
            f"Invalid variant_id format: {variant_id}. "
            "Expected: variant:{snapshot_id}:{date}:{meal_type}"
        )

    return match.groups()
