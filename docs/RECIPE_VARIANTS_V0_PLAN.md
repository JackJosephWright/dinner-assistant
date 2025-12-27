# Recipe Variants v0 - Attack Plan

**Date:** 2025-12-27
**Status:** Approved, Ready for Implementation
**Prerequisite:** LLM_RECIPE_MODIFICATION_INVESTIGATION.md

---

## Scope Decisions (LOCKED)

### In Scope (v0)
- `replace_ingredient` - swap X for Y
- `add_ingredient` - add Z to recipe
- `remove_ingredient` - remove W (requires `acknowledged: true`)
- `scale_servings` - double/halve quantities

### Out of Scope (v0)
- ❌ Step ops (edit/add/remove step) - too much risk
- ❌ `add_side` - meal-level operation, Phase 3
- ❌ User recipe library / sharing
- ❌ Manual patch editor UI

### Key Invariants
- Variants are **plan-scoped** (snapshot only)
- IDs: `variant:{snapshot_id}:{date}:{slot}`
- Compiled recipe stored in snapshot - never recomputed on reload
- Coverage rule: nothing disappears unless explicit remove op
- Ambiguity rule: if target match unclear, BLOCK and ask

---

## Phased Implementation

### Phase 0: Lock Contract (½ day)
- [ ] Create `src/patch_engine.py` with PatchOp dataclasses
- [ ] Implement validators (schema, coverage, ambiguity)
- [ ] Unit tests for validation

### Phase 1: Recipe Variants (2-3 days)
- [ ] Extend snapshot JSON with `variant` field
- [ ] `generate_patch_ops()` - LLM generates ops
- [ ] `validate_ops()` - deterministic validation
- [ ] `apply_ops()` - deterministic transform
- [ ] Cook route: `/api/cook/variant:*` support
- [ ] Shop integration: use compiled_recipe if variant exists
- [ ] UI: "Modified" badge

### Phase 2: Bounded Warnings (½-1 day)
- [ ] `generate_warnings()` - LLM outputs warnings[]
- [ ] Strip numeric minutes/temps
- [ ] Cap at 3 warnings
- [ ] Cook UI: collapsible warnings section

### Phase 3: Meal Bundles (2-4 days, separate)
- [ ] MealEditOps: `add_component`, `remove_component`, `swap_component`
- [ ] Cook UI sections (main/side)
- [ ] Shop aggregation across components

---

## Acceptance Criteria

### Phase 1 Done When:
- [ ] Swap ingredient via chat creates a variant
- [ ] Reload doesn't change anything
- [ ] `/api/cook/variant:*` works
- [ ] Shop list reflects modified ingredients
- [ ] Shows "Modified" indicator

### Phase 2 Done When:
- [ ] Warnings are helpful, never claim precise time/temp
- [ ] Logs show warnings generation + stripping
- [ ] No regressions in Cook/Shop for non-variants

---

## Data Shape (Snapshot JSON)

```json
{
  "date": "2025-01-03",
  "meal_type": "dinner",
  "recipe_id": "123456",
  "variant": {
    "variant_id": "variant:mp_2025-01-01_123:2025-01-03",
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
      "id": "variant:mp_2025-01-01_123:2025-01-03",
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

## Files to Create/Modify

| File | Action | Purpose |
|------|--------|---------|
| `src/patch_engine.py` | CREATE | PatchOp schema, validators, applicator |
| `src/data/models.py` | MODIFY | Add RecipeVariant dataclass |
| `src/web/app.py` | MODIFY | Cook route variant support |
| `src/chatbot.py` | MODIFY | Add modify_recipe tool |
| `src/agents/agentic_shopping_agent.py` | MODIFY | Use compiled_recipe if variant |
| `tests/unit/test_patch_engine.py` | CREATE | Validation + application tests |
