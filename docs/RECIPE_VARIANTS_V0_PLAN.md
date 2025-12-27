# Recipe Variants v0 - Attack Plan

**Date:** 2025-12-27
**Status:** Approved, Ready for Implementation
**Prerequisite:** LLM_RECIPE_MODIFICATION_INVESTIGATION.md

---

## Scope Decisions (LOCKED)

### In Scope (v0)
- `replace_ingredient` - swap X for Y
- `add_ingredient` - add Z to recipe (end-only in v0)
- `remove_ingredient` - remove W (requires `acknowledged: true`)
- `scale_servings` - double/halve quantities

### Out of Scope (v0)
- Step ops (edit/add/remove step) - too much risk
- `add_side` - meal-level operation, Phase 3
- User recipe library / sharing
- Manual patch editor UI
- Arbitrary add_ingredient positions (always append in v0)

### Key Invariants
- Variants are **plan-scoped** (snapshot only)
- **Variant ID format:** `variant:{snapshot_id}:{date}:{meal_type}`
- **Variant lookup:** `snapshot` → `planned_meals` match `(date, meal_type)` → `variant.compiled_recipe`
- **Patch apply ordering:** `scale_servings` → `replace` → `remove`(desc index) → `add`(end-only)
- **Generator ambiguity behavior:** if it can't select a single `target_index`, return no ops + a clarification message
- Compiled recipe stored in snapshot - never recomputed on reload

### Coverage Check Spec
The validator computes the set of ingredient indices removed/replaced. After `apply_ops()`:
- All original ingredients must still exist EXCEPT those explicitly removed via `remove_ingredient`
- `replace_ingredient` counts as: remove original at index + add replacement at same index (coverage passes)
- `add_ingredient` only appends (no coverage concern)
- If any ingredient "disappears" without explicit `remove_ingredient` op, validation FAILS

### Undo Story (v0)
Even without UI, chatbot can "clear modifications":
- `clear_variant(snapshot_id, date, meal_type)` - deletes `variant` field from that meal entry
- Returns meal to base recipe state
- No UI needed; chatbot tool can invoke it

---

## Phased Implementation

### Phase 0: Lock Contract (1/2 day)
- [ ] Create `src/patch_engine.py` with PatchOp pydantic models (runtime schema validation)
- [ ] Implement validators:
  - Schema validation (pydantic handles this)
  - Coverage check (per spec above)
  - Target name match (substring OK at `target_index`)
- [ ] Unit tests for validation

### Phase 1: Recipe Variants (2-3 days)
- [ ] Extend snapshot JSON with `variant` field
- [ ] `generate_patch_ops()` - LLM generates ops
  - If LLM can't select single target_index, return `needs_clarification=true` + message
- [ ] `validate_ops()` - deterministic validation
- [ ] `apply_ops()` - deterministic transform with ordering:
  1. `scale_servings` (affects quantities, no index changes)
  2. `replace_ingredient` (in-place, no index shift)
  3. `remove_ingredient` (descending index order to avoid shift issues)
  4. `add_ingredient` (append to end only)
- [ ] Cook route: `/api/cook/variant:*` lookup algorithm:
  1. Parse variant ID → extract `snapshot_id`, `date`, `meal_type`
  2. Load snapshot by `snapshot_id`
  3. Find `planned_meals[]` entry matching `(date, meal_type)`
  4. Return `variant.compiled_recipe` if exists, else 404
- [ ] Shop integration: use compiled_recipe if variant exists
- [ ] `clear_variant()` tool for undo
- [ ] UI: "Modified" badge

### Phase 2: Bounded Warnings (1/2-1 day)
- [ ] `generate_warnings()` - LLM outputs warnings[]
- [ ] Strip numeric minutes/temps
- [ ] Cap at 3 warnings
- [ ] Cook UI: collapsible warnings section

### Phase 3: Meal Bundles (2-4 days, separate)
- [ ] MealEditOps: `add_component`, `remove_component`, `swap_component`
- [ ] Cook UI sections (main/side)
- [ ] Shop aggregation across components

---

## Logging Tags

Define explicit log events for observability:

| Tag | Purpose |
|-----|---------|
| `[PATCH_GEN]` | LLM patch generation (input, output, latency) |
| `[PATCH_VALIDATE]` | Validation results (pass/fail, reasons) |
| `[PATCH_APPLY]` | Application of ops to recipe |
| `[WARN_GEN]` | LLM warning generation |
| `[WARN_STRIP]` | Numeric stripping from warnings |
| `[VARIANT_LOOKUP]` | Cook route variant resolution |
| `[VARIANT_CLEAR]` | Undo/clear variant action |

---

## Acceptance Criteria

### Phase 1 Done When:
- [ ] Swap ingredient via chat creates a variant
- [ ] Reload doesn't change anything
- [ ] `/api/cook/variant:*` works (lookup algorithm verified)
- [ ] Shop list reflects modified ingredients
- [ ] **Variant ingredient appears in final shopping list output** (not just raw collection)
- [ ] Shows "Modified" indicator
- [ ] "Remove modifications" via chat clears variant

### Phase 2 Done When:
- [ ] Warnings are helpful, never claim precise time/temp
- [ ] Logs show `[WARN_GEN]` and `[WARN_STRIP]` events
- [ ] No regressions in Cook/Shop for non-variants

---

## Data Shape (Snapshot JSON)

```json
{
  "date": "2025-01-03",
  "meal_type": "dinner",
  "recipe_id": "123456",
  "variant": {
    "variant_id": "variant:snap_abc123:2025-01-03:dinner",
    "base_recipe_id": "123456",
    "patch_ops": [
      {
        "op": "replace_ingredient",
        "target_index": 2,
        "target_name": "white rice",
        "replacement": {"name": "brown rice", "quantity": "2 cups"},
        "reason": "user_request"
      }
    ],
    "compiled_recipe": {
      "id": "variant:snap_abc123:2025-01-03:dinner",
      "name": "Chicken Stir Fry (modified)",
      "ingredients_raw": ["...", "2 cups brown rice", "..."],
      "steps": ["..."]
    },
    "warnings": [],
    "compiled_at": "2025-12-27T10:00:00Z",
    "compiler_version": "v0"
  }
}
```

---

## PatchOp Schema (Pydantic)

```python
from pydantic import BaseModel, Field
from typing import Literal, Optional
from enum import Enum

class PatchOpType(str, Enum):
    REPLACE_INGREDIENT = "replace_ingredient"
    ADD_INGREDIENT = "add_ingredient"
    REMOVE_INGREDIENT = "remove_ingredient"
    SCALE_SERVINGS = "scale_servings"

class IngredientReplacement(BaseModel):
    name: str
    quantity: str

class PatchOp(BaseModel):
    op: PatchOpType
    target_index: Optional[int] = None  # Required for replace/remove
    target_name: Optional[str] = None   # For validation: must match ingredient at index
    replacement: Optional[IngredientReplacement] = None  # For replace
    new_ingredient: Optional[str] = None  # For add (raw string)
    scale_factor: Optional[float] = None  # For scale_servings
    acknowledged: bool = False  # Required true for remove
    reason: str = "user_request"

class PatchGenResult(BaseModel):
    """LLM generator output"""
    ops: list[PatchOp] = Field(default_factory=list)
    needs_clarification: bool = False
    clarification_message: Optional[str] = None
```

---

## Files to Create/Modify

| File | Action | Purpose |
|------|--------|---------|
| `src/patch_engine.py` | CREATE | PatchOp pydantic models, validators, applicator |
| `src/data/models.py` | MODIFY | Add RecipeVariant dataclass |
| `src/web/app.py` | MODIFY | Cook route variant lookup support |
| `src/chatbot.py` | MODIFY | Add `modify_recipe` and `clear_variant` tools |
| `src/agents/agentic_shopping_agent.py` | MODIFY | Use compiled_recipe if variant exists |
| `tests/unit/test_patch_engine.py` | CREATE | Validation + application tests |
| `tests/integration/test_variant_shopping.py` | CREATE | Variant shows in final shopping list |

---

## Shopping Integration Notes

Verify where ingredients are sourced before modifying `agentic_shopping_agent.py`:

**Current flow (verify):**
1. `MealPlan.get_all_ingredients()` or similar aggregates ingredients
2. Shopping agent receives aggregated list
3. Agent categorizes and consolidates

**If ingredients come from MealPlan methods:**
- Modify `MealPlan.get_all_ingredients()` to check for `variant.compiled_recipe`
- Agent changes may be minimal or unnecessary

**Acceptance test (required):**
```python
def test_variant_ingredient_in_shopping_list():
    """Variant ingredient appears in final shopping list output."""
    # Create plan with "chicken"
    # Apply variant: replace "chicken" with "tofu"
    # Generate shopping list
    # Assert "tofu" in final list, "chicken" NOT in list
```
