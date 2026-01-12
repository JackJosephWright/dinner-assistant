"""
Recipe step modification module.

Handles modifying recipe cooking instructions when ingredients are swapped.
Uses LLM to intelligently update cooking times, doneness cues, and techniques.

v1: Protein swaps only, with tight safety guardrails.
"""

import hashlib
import json
import logging
import re
from dataclasses import dataclass, field
from typing import Optional

from anthropic import Anthropic

from src.cook_profiles import (
    CookProfile,
    get_cook_profile,
    has_cook_profile,
    should_refuse_instruction_mod,
)

logger = logging.getLogger(__name__)


# --- Step ID Generation ---

def generate_step_id(step_text: str, index: int) -> str:
    """
    Generate a stable ID for a recipe step.

    IDs are derived from content hash to ensure stability across sessions
    without requiring database schema changes.

    Args:
        step_text: The step instruction text
        index: The 0-based index of the step

    Returns:
        ID in format "s{index}_{hash[:6]}"
    """
    normalized = step_text.strip().lower()[:100]
    hash_part = hashlib.md5(normalized.encode()).hexdigest()[:6]
    return f"s{index}_{hash_part}"


def add_step_ids(steps: list[str]) -> list[dict]:
    """
    Add stable IDs to a list of step strings.

    Args:
        steps: List of step instruction strings

    Returns:
        List of dicts with step_id, index, and text
    """
    return [
        {
            "step_id": generate_step_id(step, i),
            "index": i,
            "text": step,
        }
        for i, step in enumerate(steps)
    ]


# --- Ingredient Delta ---

@dataclass
class IngredientDelta:
    """
    Represents a semantic ingredient substitution.

    Provides structured information about what changed and cooking implications.
    """
    original: str  # Original ingredient name
    replacement: str  # New ingredient name
    role: str  # "protein" | "vegetable" | "dairy" | "other"
    cook_profile_from: Optional[CookProfile] = None
    cook_profile_to: Optional[CookProfile] = None

    @property
    def has_profiles(self) -> bool:
        """Check if we have cooking profiles for both ingredients."""
        return self.cook_profile_from is not None and self.cook_profile_to is not None

    @property
    def time_diff_description(self) -> str:
        """Human-readable description of cooking time difference."""
        if not self.has_profiles:
            return "unknown"

        from_time = f"{self.cook_profile_from.min_time}-{self.cook_profile_from.max_time} min"
        to_time = f"{self.cook_profile_to.min_time}-{self.cook_profile_to.max_time} min"
        return f"{from_time} → {to_time}"


def build_ingredient_delta(
    patch_ops: list[dict],
    original_ingredients: list[str],
) -> Optional[IngredientDelta]:
    """
    Build an IngredientDelta from patch operations.

    Only returns a delta if:
    1. A protein ingredient was replaced (not added/removed)
    2. We have cooking profiles for both original and replacement

    Args:
        patch_ops: List of patch operations from generate_patch
        original_ingredients: Original recipe ingredient list

    Returns:
        IngredientDelta if a protein swap was detected, None otherwise
    """
    # Find "replace_ingredient" operations for proteins
    for op in patch_ops:
        # Handle both string and enum op types
        op_type = op.get("op", "")
        if hasattr(op_type, "value"):
            op_type = op_type.value  # Convert enum to string
        op_type = str(op_type)

        if op_type != "replace_ingredient":
            continue

        # Extract original and replacement ingredient names
        # New format: target_name + replacement.name
        original = op.get("target_name", "")
        replacement_data = op.get("replacement", {})
        if isinstance(replacement_data, dict):
            replacement = replacement_data.get("name", "")
        else:
            replacement = str(replacement_data)

        # Fallback to old format if new format not found
        if not original:
            original = op.get("value", {}).get("original_text", "")
        if not replacement:
            replacement = op.get("value", {}).get("modified_text", "")

        if not original or not replacement:
            continue

        logger.debug(f"[STEP_MOD] Checking: {original} -> {replacement}")

        # Check if this is a protein swap
        from_profile = get_cook_profile(original)
        to_profile = get_cook_profile(replacement)

        if from_profile and to_profile:
            logger.info(
                f"[STEP_MOD] Detected protein swap: {original} -> {replacement}"
            )
            return IngredientDelta(
                original=original,
                replacement=replacement,
                role="protein",
                cook_profile_from=from_profile,
                cook_profile_to=to_profile,
            )
        elif from_profile or to_profile:
            # One is a protein, one isn't - still interesting
            logger.info(
                f"[STEP_MOD] Partial protein match: {original} -> {replacement}"
            )
            return IngredientDelta(
                original=original,
                replacement=replacement,
                role="protein" if from_profile else "other",
                cook_profile_from=from_profile,
                cook_profile_to=to_profile,
            )

    return None


# --- Safety Validation ---

def validate_modified_steps(
    original_steps: list[dict],
    modified_steps: list[dict],
    delta: IngredientDelta,
) -> list[str]:
    """
    Validate LLM-generated step modifications for safety.

    Returns list of violation messages. Empty list means safe.
    """
    violations = []

    if not delta or delta.role != "protein":
        return violations

    # Rule 1: If original mentions meat temp, modified must retain OR replace with appropriate temp/cue
    original_has_temp = any(
        re.search(r'\d{2,3}°?F', s.get("text", ""))
        for s in original_steps
    )

    if original_has_temp:
        modified_has_temp = any(
            re.search(r'\d{2,3}°?F', s.get("text", ""))
            for s in modified_steps
        )

        if not modified_has_temp:
            # Check if we at least have a doneness cue
            doneness_cues = ['opaque', 'flakes', 'pink', 'browned', 'cooked through', 'golden']
            has_cue = any(
                any(cue in s.get("text", "").lower() for cue in doneness_cues)
                for s in modified_steps
            )
            if not has_cue:
                violations.append(
                    "Removed temperature guidance without adding doneness cue"
                )

    # Rule 2: Validate any temps mentioned are in safe ranges
    if delta.cook_profile_to and delta.cook_profile_to.safe_temp:
        expected_min = delta.cook_profile_to.safe_temp
        for step in modified_steps:
            temps = re.findall(r'(\d{2,3})°?F', step.get("text", ""))
            for temp in temps:
                temp_int = int(temp)
                # Allow 5°F tolerance
                if temp_int < expected_min - 5:
                    violations.append(
                        f"Temperature {temp}°F below safe minimum {expected_min}°F "
                        f"for {delta.replacement}"
                    )

    return violations


def validate_structural_limits(
    modification_result: dict,
) -> list[str]:
    """
    Validate that LLM response stays within structural limits.

    Returns list of violation messages.
    """
    violations = []

    new_steps = modification_result.get("new_steps", [])
    removed_steps = modification_result.get("removed_steps", [])

    # Tier 3: Hard limits
    if len(new_steps) > 1:
        violations.append(
            f"Too many new steps ({len(new_steps)}). Maximum 1 allowed."
        )

    if len(removed_steps) > 1:
        violations.append(
            f"Too many removed steps ({len(removed_steps)}). Maximum 1 allowed."
        )

    # Validate new step reasons
    allowed_new_step_reasons = {"drain grease", "pat dry", "thaw", "drain", "dry"}
    for step in new_steps:
        reason = step.get("reason", "").lower()
        if not any(r in reason for r in allowed_new_step_reasons):
            violations.append(
                f"New step reason '{reason}' not in allowed list. "
                f"Only drain/dry operations allowed."
            )

    return violations


# --- Confidence Scoring ---

def score_modification_confidence(
    num_steps_modified: int,
    num_steps_total: int,
    delta: IngredientDelta,
    violations: list[str],
) -> float:
    """
    Score confidence in the step modification.

    Returns:
        Float between 0.0 and 1.0
    """
    # Base score by modification extent
    if num_steps_modified == 0:
        base = 1.0  # No changes = trivial
    elif num_steps_modified <= 2:
        base = 0.85
    elif num_steps_modified <= 4:
        base = 0.70
    else:
        base = 0.50

    # Bonus if swap is in known profiles
    if delta.has_profiles:
        base += 0.05

    # Penalty for any violations
    base -= 0.15 * len(violations)

    return max(0.0, min(1.0, base))


# --- LLM Step Modification ---

STEP_MODIFICATION_PROMPT = """
Modify these recipe steps for an ingredient substitution.

RECIPE: {recipe_name}

SUBSTITUTION:
- Original: {original_ingredient}
- Replacement: {replacement_ingredient}
- Cooking time change: {time_diff}
- New doneness cue: "{new_cue}"

ORIGINAL STEPS (with step_id):
{numbered_steps}

Return JSON only, no markdown:
{{
  "modified_steps": [
    {{
      "step_id": "s1_abc123",
      "original_text": "exact original text",
      "modified_text": "updated text",
      "reason": "Updated cooking time for {replacement_ingredient}"
    }}
  ],
  "new_steps": [],
  "removed_steps": [],
  "cooking_notes": ["Important notes for the cook"]
}}

RULES:
1. Only modify steps that NEED to change (mention {original_ingredient} or its cooking time/cues)
2. Reference steps by step_id from the list above
3. Keep modifications minimal and precise
4. Update cooking times based on the profile: {time_diff}
5. Update doneness cues to: "{new_cue}"
6. Never reduce safe cooking temperatures
7. new_steps: max 1 (only for: drain grease, pat dry, thaw)
8. removed_steps: max 1
9. For simple word swaps (just changing ingredient name), still include them
"""


def generate_step_modifications(
    recipe_name: str,
    steps: list[str],
    delta: IngredientDelta,
    client: Anthropic,
) -> dict:
    """
    Generate step modifications using LLM.

    Args:
        recipe_name: Name of the recipe
        steps: Original recipe steps (list of strings)
        delta: IngredientDelta describing the substitution
        client: Anthropic client

    Returns:
        Dict with modified_steps, new_steps, removed_steps, cooking_notes
    """
    # Add step IDs
    steps_with_ids = add_step_ids(steps)

    # Format steps for prompt
    numbered_steps = "\n".join(
        f"[{s['step_id']}] {s['text']}"
        for s in steps_with_ids
    )

    # Build prompt
    time_diff = delta.time_diff_description if delta.has_profiles else "similar"
    new_cue = delta.cook_profile_to.cue if delta.cook_profile_to else "cooked through"

    prompt = STEP_MODIFICATION_PROMPT.format(
        recipe_name=recipe_name,
        original_ingredient=delta.original,
        replacement_ingredient=delta.replacement,
        time_diff=time_diff,
        new_cue=new_cue,
        numbered_steps=numbered_steps,
    )

    logger.info(f"[STEP_MOD] Generating modifications for {recipe_name}")
    logger.debug(f"[STEP_MOD] Delta: {delta.original} -> {delta.replacement}")

    # Call LLM
    response = client.messages.create(
        model="claude-sonnet-4-20250514",
        max_tokens=2000,
        messages=[{"role": "user", "content": prompt}],
    )

    # Parse response
    response_text = response.content[0].text.strip()

    # Handle potential markdown code blocks
    if response_text.startswith("```"):
        # Extract JSON from code block
        lines = response_text.split("\n")
        json_lines = []
        in_block = False
        for line in lines:
            if line.startswith("```"):
                in_block = not in_block
                continue
            if in_block:
                json_lines.append(line)
        response_text = "\n".join(json_lines)

    try:
        result = json.loads(response_text)
    except json.JSONDecodeError as e:
        logger.error(f"[STEP_MOD] Failed to parse LLM response: {e}")
        logger.error(f"[STEP_MOD] Response was: {response_text[:500]}")
        return {
            "modified_steps": [],
            "new_steps": [],
            "removed_steps": [],
            "cooking_notes": ["Failed to parse step modifications"],
            "error": str(e),
        }

    # Ensure expected keys exist
    result.setdefault("modified_steps", [])
    result.setdefault("new_steps", [])
    result.setdefault("removed_steps", [])
    result.setdefault("cooking_notes", [])

    logger.info(
        f"[STEP_MOD] Generated {len(result['modified_steps'])} modifications, "
        f"{len(result['new_steps'])} new steps, "
        f"{len(result['removed_steps'])} removed steps"
    )

    return result


def apply_step_modifications(
    original_steps: list[str],
    modification_result: dict,
) -> list[dict]:
    """
    Apply step modifications to create the final step list.

    Args:
        original_steps: Original recipe steps (list of strings)
        modification_result: Result from generate_step_modifications

    Returns:
        List of step dicts with step_id and text
    """
    # Start with original steps + IDs
    steps_with_ids = add_step_ids(original_steps)

    # Build lookup for modifications
    mods_by_id = {
        m["step_id"]: m
        for m in modification_result.get("modified_steps", [])
    }

    # Build lookup for removed steps
    removed_ids = {
        r.get("step_id") for r in modification_result.get("removed_steps", [])
    }

    # Apply modifications
    result = []
    for step in steps_with_ids:
        if step["step_id"] in removed_ids:
            continue

        if step["step_id"] in mods_by_id:
            mod = mods_by_id[step["step_id"]]
            result.append({
                "step_id": step["step_id"],
                "index": step["index"],
                "text": mod["modified_text"],
                "original_text": step["text"],
                "reason": mod.get("reason", ""),
            })
        else:
            result.append(step)

    # Insert new steps (max 1, adjacent to a modified step)
    new_steps = modification_result.get("new_steps", [])
    if new_steps:
        new_step = new_steps[0]
        insert_after = new_step.get("insert_after")

        # Find insertion point
        insert_idx = len(result)  # Default to end
        if insert_after:
            for i, step in enumerate(result):
                if step["step_id"] == insert_after:
                    insert_idx = i + 1
                    break

        # Create new step with generated ID
        new_step_obj = {
            "step_id": generate_step_id(new_step.get("text", ""), insert_idx),
            "index": insert_idx,
            "text": new_step.get("text", ""),
            "is_new": True,
            "reason": new_step.get("reason", ""),
        }

        result.insert(insert_idx, new_step_obj)

        # Re-index
        for i, step in enumerate(result):
            step["index"] = i

    return result


# --- Main Entry Point ---

@dataclass
class StepModificationResult:
    """Result of step modification attempt."""
    success: bool
    modified_steps: list[dict] = field(default_factory=list)
    original_steps: list[dict] = field(default_factory=list)
    step_modifications: list[dict] = field(default_factory=list)
    confidence: float = 0.0
    warnings: list[str] = field(default_factory=list)
    refused_reason: Optional[str] = None


def modify_recipe_steps(
    recipe_name: str,
    steps: list[str],
    user_request: str,
    patch_ops: list[dict],
    original_ingredients: list[str],
    client: Anthropic,
) -> StepModificationResult:
    """
    Main entry point for modifying recipe steps.

    Performs all safety checks, LLM generation, validation, and scoring.

    Args:
        recipe_name: Name of the recipe
        steps: Original recipe steps (list of strings)
        user_request: Original user request (for method change detection)
        patch_ops: Patch operations from ingredient modification
        original_ingredients: Original recipe ingredients
        client: Anthropic client

    Returns:
        StepModificationResult with modified steps or error info
    """
    # Tier 1: Check for cooking method changes
    if should_refuse_instruction_mod(user_request):
        logger.info(f"[STEP_MOD] Refusing: cooking method change detected")
        return StepModificationResult(
            success=False,
            refused_reason="Cooking method changes require manual recipe adaptation",
            original_steps=add_step_ids(steps),
        )

    # Build ingredient delta
    delta = build_ingredient_delta(patch_ops, original_ingredients)

    if not delta:
        logger.info(f"[STEP_MOD] No protein swap detected, skipping step modification")
        return StepModificationResult(
            success=True,
            modified_steps=add_step_ids(steps),
            original_steps=add_step_ids(steps),
            confidence=1.0,
            warnings=["No protein substitution detected - steps unchanged"],
        )

    if not delta.has_profiles:
        logger.info(
            f"[STEP_MOD] Missing cook profiles for {delta.original} -> {delta.replacement}"
        )
        return StepModificationResult(
            success=True,
            modified_steps=add_step_ids(steps),
            original_steps=add_step_ids(steps),
            confidence=0.5,
            warnings=[
                f"No cooking profile for {delta.replacement} - "
                "steps unchanged, use original cooking guidance"
            ],
        )

    # Generate modifications via LLM
    modification_result = generate_step_modifications(
        recipe_name=recipe_name,
        steps=steps,
        delta=delta,
        client=client,
    )

    if modification_result.get("error"):
        return StepModificationResult(
            success=False,
            refused_reason=f"Step modification failed: {modification_result['error']}",
            original_steps=add_step_ids(steps),
        )

    # Validate structural limits
    structural_violations = validate_structural_limits(modification_result)

    # Apply modifications to get final steps
    modified_steps = apply_step_modifications(steps, modification_result)

    # Validate safety
    safety_violations = validate_modified_steps(
        add_step_ids(steps),
        modified_steps,
        delta,
    )

    all_violations = structural_violations + safety_violations

    # Score confidence
    num_modified = len(modification_result.get("modified_steps", []))
    confidence = score_modification_confidence(
        num_steps_modified=num_modified,
        num_steps_total=len(steps),
        delta=delta,
        violations=all_violations,
    )

    # Determine if we should use modifications
    warnings = []
    if all_violations:
        warnings.extend(all_violations)

    if confidence < 0.60:
        logger.warning(
            f"[STEP_MOD] Low confidence ({confidence:.2f}), falling back to original"
        )
        warnings.append(
            f"Step modifications below confidence threshold ({confidence:.2f}). "
            "Using original instructions."
        )
        return StepModificationResult(
            success=True,
            modified_steps=add_step_ids(steps),
            original_steps=add_step_ids(steps),
            confidence=confidence,
            warnings=warnings,
        )

    # Add cooking notes as warnings
    cooking_notes = modification_result.get("cooking_notes", [])
    if cooking_notes:
        warnings.extend(cooking_notes)

    # Build step_modifications audit trail
    step_modifications = []
    for mod in modification_result.get("modified_steps", []):
        step_modifications.append({
            "step_id": mod["step_id"],
            "original_text": mod.get("original_text", ""),
            "modified_text": mod.get("modified_text", ""),
            "reason": mod.get("reason", ""),
        })

    logger.info(
        f"[STEP_MOD] Success: {num_modified} steps modified, "
        f"confidence={confidence:.2f}"
    )

    return StepModificationResult(
        success=True,
        modified_steps=modified_steps,
        original_steps=add_step_ids(steps),
        step_modifications=step_modifications,
        confidence=confidence,
        warnings=warnings,
    )
