# Investigation: LLM-Assisted Recipe Modification via Patch + Persistence

**Date:** 2025-12-26
**Branch:** `investigation/llm-recipe-modification`
**Status:** Investigation Complete

---

## Executive Summary

LLM-assisted recipe modification via structured patches is **feasible with constraints**. The strategy is sound: LLMs propose changes, deterministic rules validate, persistence ensures reload stability. However, this requires careful scoping to avoid complexity explosion.

**Recommendation:** Feasible with constraints
**Estimated Complexity:** Medium-High
**Critical Constraint:** Keep patch ops minimal and explicit

---

## Architecture Diagram (Textual)

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                           USER REQUEST                                       │
│                 "Use brown rice instead of white rice"                       │
└─────────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                          LLM PATCH GENERATOR                                 │
│   Constrained prompt → outputs structured PatchOp JSON                       │
│   Temperature = 0, strict schema enforcement                                 │
└─────────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                        DETERMINISTIC VALIDATOR                               │
│   Schema check → Coverage check → Allergen check → Provenance tag            │
│   BLOCKS on hard failures, WARNS on soft failures                            │
└─────────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                          PATCH APPLICATOR                                    │
│   base_recipe + patch_ops → compiled_recipe (deterministic transform)        │
└─────────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                         SNAPSHOT PERSISTENCE                                 │
│   Store: { variant_id, base_recipe_id, patch_ops[], compiled_recipe }        │
│   Location: meal_plan_snapshots.snapshot_json                                │
└─────────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                            COOK ROUTE                                        │
│   /api/cook/variant:abc123 → load snapshot → return compiled_recipe          │
│   /api/cook/123456 → load from catalog DB (unchanged)                        │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## 1. Artifact Inventory

### 1.1 Base Catalog Recipe

| Attribute | Value |
|-----------|-------|
| **Location** | `recipes.db` (SQLite, read-only catalog) |
| **Owner** | System (Food.com import) |
| **Identifier** | Integer ID (e.g., `123456`) |
| **Invalidation** | Never (catalog is immutable) |

**Key Fields:**
```python
Recipe(
    id: str,
    name: str,
    ingredients: List[str],
    ingredients_raw: List[str],
    steps: List[str],
    servings: int,
    tags: List[str],
    # ...
)
```

### 1.2 Patch Operations (LLM-Generated)

| Attribute | Value |
|-----------|-------|
| **Location** | `meal_plan_snapshots.snapshot_json` (embedded in meal) |
| **Owner** | User (via LLM interaction) |
| **Identifier** | Array index within meal's `patch_ops[]` |
| **Invalidation** | When user requests new modification or clears variant |

**Structure:**
```json
{
  "patch_ops": [
    {
      "op": "replace_ingredient",
      "target_index": 3,
      "target_name": "white rice",
      "replacement": {"name": "brown rice", "quantity": "2 cups"},
      "reason": "user_request",
      "created_at": "2025-12-26T10:30:00Z"
    }
  ]
}
```

### 1.3 Recipe Variant (Compiled View)

| Attribute | Value |
|-----------|-------|
| **Location** | `meal_plan_snapshots.snapshot_json` (cached, re-computable) |
| **Owner** | User (derived from base + patches) |
| **Identifier** | `variant:{snapshot_id}:{date}` or UUID |
| **Invalidation** | When patch_ops change OR base recipe updates (rare) |

**Structure:**
```json
{
  "variant_id": "variant:mp_2025-01-01_123:2025-01-03",
  "base_recipe_id": "123456",
  "patch_ops": [...],
  "compiled_recipe": {
    "id": "variant:mp_2025-01-01_123:2025-01-03",
    "name": "Chicken Stir Fry (modified)",
    "ingredients_raw": ["2 cups brown rice", ...],
    "steps": [...],
    ...
  },
  "compiled_at": "2025-12-26T10:30:05Z"
}
```

### 1.4 MealBundle (Main + Side)

| Attribute | Value |
|-----------|-------|
| **Location** | `meal_plan_snapshots.snapshot_json` (within planned_meals) |
| **Owner** | User (via planning) |
| **Identifier** | `bundle:{snapshot_id}:{date}` |
| **Invalidation** | When any component changes |

**Structure:**
```json
{
  "date": "2025-01-03",
  "meal_type": "dinner",
  "components": [
    {
      "role": "main",
      "recipe_ref": "variant:mp_2025-01-01_123:2025-01-03",
      "is_variant": true
    },
    {
      "role": "side",
      "recipe_ref": "789012",
      "is_variant": false
    }
  ]
}
```

### 1.5 Stable Identifier Scheme

| ID Pattern | Meaning | Resolution |
|------------|---------|------------|
| `123456` | Catalog recipe | `db.get_recipe(id)` |
| `variant:{snapshot}:{date}` | Recipe variant | `snapshot.planned_meals[date].compiled_recipe` |
| `bundle:{snapshot}:{date}` | Meal bundle | `snapshot.planned_meals[date].components[]` |

---

## 2. Patch Operation Schema

### 2.1 Supported Operations

```typescript
type PatchOp =
  | ReplaceIngredientOp
  | AddIngredientOp
  | RemoveIngredientOp
  | EditStepOp
  | AddStepOp
  | RemoveStepOp
  | ScaleServingsOp
  | AddSideOp;

interface ReplaceIngredientOp {
  op: "replace_ingredient";
  target_index: number;           // Index in ingredients_raw[]
  target_name: string;            // Original name (for verification)
  replacement: {
    name: string;
    quantity?: string;
    unit?: string;
  };
  reason: "user_request" | "allergen" | "availability";
}

interface AddIngredientOp {
  op: "add_ingredient";
  ingredient: {
    name: string;
    quantity: string;
    unit?: string;
  };
  position?: "start" | "end" | number;  // Default: end
  reason: string;
}

interface RemoveIngredientOp {
  op: "remove_ingredient";
  target_index: number;
  target_name: string;            // For verification
  reason: string;
  acknowledged: true;             // EXPLICIT confirmation required
}

interface EditStepOp {
  op: "edit_step";
  target_index: number;
  original_snippet: string;       // First 50 chars for verification
  new_text: string;
  reason: string;
}

interface AddStepOp {
  op: "add_step";
  text: string;
  position: number | "start" | "end";
  reason: string;
}

interface RemoveStepOp {
  op: "remove_step";
  target_index: number;
  original_snippet: string;       // For verification
  reason: string;
  acknowledged: true;             // EXPLICIT confirmation required
}

interface ScaleServingsOp {
  op: "scale_servings";
  from_servings: number;
  to_servings: number;
  scale_factor: number;           // Redundant but explicit
}

interface AddSideOp {
  op: "add_side";
  recipe_id: string;              // Catalog ID or variant ID
  reason: string;
}
```

### 2.2 Explicit Acknowledgment Requirement

Operations that **remove** content MUST include `"acknowledged": true`:
- `remove_ingredient`
- `remove_step`

This prevents silent data loss from LLM hallucination.

### 2.3 Fields LLM Cannot Modify Directly

| Field | Reason |
|-------|--------|
| `id` | System-assigned |
| `tags` | Requires re-indexing |
| `nutrition` | Requires recalculation |
| `estimated_time` | Derived from tags |
| `cuisine` | Derived from tags |
| `difficulty` | Derived from tags |

These fields are recomputed deterministically after patches are applied.

---

## 3. Validation & Invariants

### 3.1 Validation Rules

| Check | Type | Action on Failure |
|-------|------|-------------------|
| **Schema validity** | Hard | BLOCK - Reject patch |
| **Target exists** | Hard | BLOCK - target_index/target_name must match |
| **No silent removal** | Hard | BLOCK - Remove ops require `acknowledged: true` |
| **Ingredient count ≥ 1** | Hard | BLOCK - Recipe must have at least 1 ingredient |
| **Step count ≥ 1** | Hard | BLOCK - Recipe must have at least 1 step |
| **Quantity sanity** | Soft | WARN - Flag if quantity seems extreme (>10x original) |
| **Allergen consistency** | Soft | WARN - Flag if new ingredient introduces allergen |
| **Provenance preserved** | Info | LOG - Record base_recipe_id and all ops |

### 3.2 Validation Implementation

```python
@dataclass
class ValidationResult:
    valid: bool
    hard_failures: List[str]
    soft_warnings: List[str]

def validate_patch_ops(base_recipe: Recipe, ops: List[PatchOp]) -> ValidationResult:
    """Validate patch operations before applying."""
    hard_failures = []
    soft_warnings = []

    for op in ops:
        # Schema check
        if not is_valid_schema(op):
            hard_failures.append(f"Invalid schema: {op}")
            continue

        # Target verification
        if hasattr(op, 'target_index'):
            if op.op.startswith('ingredient'):
                if op.target_index >= len(base_recipe.ingredients_raw):
                    hard_failures.append(f"Invalid ingredient index: {op.target_index}")
                elif op.target_name.lower() not in base_recipe.ingredients_raw[op.target_index].lower():
                    hard_failures.append(f"Ingredient mismatch at {op.target_index}")

        # Removal acknowledgment
        if op.op in ['remove_ingredient', 'remove_step']:
            if not getattr(op, 'acknowledged', False):
                hard_failures.append(f"Remove op requires acknowledged=true: {op.op}")

    # Post-apply checks (simulate)
    simulated = apply_patches_dry_run(base_recipe, ops)
    if len(simulated.ingredients_raw) < 1:
        hard_failures.append("Result would have no ingredients")
    if len(simulated.steps) < 1:
        hard_failures.append("Result would have no steps")

    return ValidationResult(
        valid=len(hard_failures) == 0,
        hard_failures=hard_failures,
        soft_warnings=soft_warnings
    )
```

---

## 4. Persistence & Reload Semantics

### 4.1 Cook Route ID Resolution

```python
@app.route('/api/cook/<recipe_id>', methods=['GET'])
def api_get_cooking_guide(recipe_id):
    """Get cooking guide - supports catalog IDs and variant IDs."""

    # Pattern: variant:{snapshot_id}:{date}
    if recipe_id.startswith('variant:'):
        parts = recipe_id.split(':')
        snapshot_id, date = parts[1], parts[2]
        snapshot = db.get_snapshot(snapshot_id)

        if snapshot:
            meal = find_meal_by_date(snapshot['planned_meals'], date)
            if meal and 'compiled_recipe' in meal:
                return jsonify({
                    "success": True,
                    "recipe_name": meal['compiled_recipe']['name'],
                    "ingredients": meal['compiled_recipe']['ingredients_raw'],
                    "steps": meal['compiled_recipe']['steps'],
                    # ...
                })
        return jsonify({"success": False, "error": "Variant not found"}), 404

    # Pattern: bundle:{snapshot_id}:{date}
    if recipe_id.startswith('bundle:'):
        # Return all components for multi-recipe view
        ...

    # Default: catalog recipe
    return assistant.get_cooking_guide(recipe_id)
```

### 4.2 Re-Hydration Flow

```
Load Request: /api/cook/variant:mp_2025-01-01_123:2025-01-03
              │
              ▼
┌─────────────────────────────────┐
│ 1. Parse variant ID             │
│    snapshot_id = "mp_2025..."   │
│    date = "2025-01-03"          │
└─────────────────────────────────┘
              │
              ▼
┌─────────────────────────────────┐
│ 2. Load snapshot from DB        │
│    snapshot = get_snapshot(id)  │
└─────────────────────────────────┘
              │
              ▼
┌─────────────────────────────────┐
│ 3. Find meal by date            │
│    meal = planned_meals[date]   │
└─────────────────────────────────┘
              │
              ▼
┌─────────────────────────────────┐
│ 4. Return compiled_recipe       │
│    (Already computed + stored)  │
└─────────────────────────────────┘
```

### 4.3 When to Recompile

| Event | Recompile? | Reason |
|-------|------------|--------|
| User adds new patch op | YES | New modification |
| User removes patch op | YES | Undo modification |
| Page reload | NO | Use cached compiled_recipe |
| Model/prompt update | NO | Compiled recipe is stable |
| Base recipe update in catalog | OPTIONAL | Rare, could offer "update from catalog" |

### 4.4 Base Recipe Update Handling

```python
def check_base_recipe_freshness(variant: dict) -> bool:
    """Check if base recipe has changed since variant was compiled."""
    base_id = variant['base_recipe_id']
    base_recipe = db.get_recipe(base_id)

    # Compare hash of key fields
    current_hash = hash_recipe(base_recipe)
    compiled_hash = variant.get('base_recipe_hash')

    if compiled_hash and current_hash != compiled_hash:
        return False  # Stale - base changed
    return True
```

When stale:
- Show warning: "Base recipe has been updated. Recompile?"
- User can accept recompile or keep current variant

---

## 5. Interaction with MealBundles

### 5.1 Component-Level Variants

A bundle component can reference:
- Catalog recipe: `"recipe_ref": "123456"`
- Recipe variant: `"recipe_ref": "variant:mp_...:2025-01-03"`

```json
{
  "date": "2025-01-03",
  "components": [
    {
      "role": "main",
      "recipe_ref": "variant:mp_2025-01-01_123:2025-01-03",
      "is_variant": true,
      "compiled_recipe": {...}
    },
    {
      "role": "side",
      "recipe_ref": "789012",
      "is_variant": false
    }
  ]
}
```

### 5.2 Patch Application Order

Patches apply **per-component, before bundling**:

```
User: "Add brown rice to the stir fry, and add a caesar salad"

1. Apply patch to main component:
   base: Chicken Stir Fry
   patch: [add_ingredient: "brown rice"]
   result: Chicken Stir Fry (modified)

2. Add side component (no patches):
   base: Caesar Salad
   patches: []
   result: Caesar Salad

3. Bundle:
   [main: Chicken Stir Fry (modified), side: Caesar Salad]
```

### 5.3 Shop Aggregation Across Variants + Components

```python
def collect_ingredients_from_bundle(bundle: dict) -> List[dict]:
    """Collect ingredients from all bundle components."""
    all_ingredients = []

    for component in bundle['components']:
        if component.get('is_variant') and 'compiled_recipe' in component:
            recipe = component['compiled_recipe']
        else:
            recipe = db.get_recipe(component['recipe_ref'])

        for ing in recipe['ingredients_raw']:
            all_ingredients.append({
                "ingredient": ing,
                "recipe": recipe['name'],
                "component_role": component['role']
            })

    return all_ingredients
```

The shopping agent already handles multi-source ingredients - this just adds another source.

---

## 6. Blast Radius Assessment

### 6.1 Estimated Complexity: MEDIUM-HIGH

| Component | Risk | Reason |
|-----------|------|--------|
| **Patch schema design** | Medium | Needs careful scoping to avoid feature creep |
| **Validation rules** | Medium | Must balance strictness vs usability |
| **Cook route changes** | Low | Additive - new ID patterns, existing unchanged |
| **Snapshot extension** | Low | JSON is already flexible |
| **LLM prompt design** | High | Getting consistent structured output is hard |
| **UI for patch editing** | High | Outside scope but will be requested |

### 6.2 Files Likely Affected

| File | Changes |
|------|---------|
| `src/data/models.py` | Add `PatchOp`, `RecipeVariant` dataclasses |
| `src/web/app.py` | Update cook route for variant IDs |
| `src/chatbot.py` | Add `modify_recipe` tool, patch generation prompt |
| `src/data/database.py` | Helper for variant storage in snapshots |
| New: `src/patch_engine.py` | Validation + application logic |
| `src/web/templates/cook.html` | Display variant indicator, modification list |

### 6.3 Highest-Risk Assumptions

1. **LLM outputs valid JSON consistently** - Needs retry + fallback
2. **Target indices are stable** - Recipe must not change between patch creation and application
3. **Users understand variants are plan-scoped** - Variant exists only in snapshot, not catalog
4. **Compiled recipe is trusted** - Once validated, we serve it without re-validation

### 6.4 What Breaks If We Get This Wrong

| Failure | Impact |
|---------|--------|
| Invalid patch passes validation | Corrupted recipe in cook view |
| Variant ID not found | 404 on cook route (recoverable) |
| LLM generates too many ops | Slow validation, complex recipe |
| Base recipe hash changes | Stale variants (detectable) |
| Patch removes all ingredients | Empty recipe (blocked by validation) |

---

## 7. Failure Modes & Mitigations

### 7.1 LLM Emits Malformed Ops

**Detection:** JSON schema validation
**Recovery:**
- Retry with simplified prompt (1 retry max)
- Fall back to "I couldn't make that change. Can you rephrase?"
- Log for debugging

```python
def generate_patch_ops(user_request: str, recipe: Recipe) -> List[PatchOp]:
    try:
        ops = llm_generate_patches(user_request, recipe)
        if not validate_schema(ops):
            # Retry once
            ops = llm_generate_patches(user_request, recipe, retry=True)
        return ops if validate_schema(ops) else []
    except Exception:
        return []  # Fallback to no modification
```

### 7.2 Patch Applies But Produces Weird Recipe

**Detection:** Soft validation warnings (quantity sanity, allergen checks)
**Recovery:**
- Show warning to user before saving
- Offer "undo" in UI
- Keep original base recipe always available

```python
result = validate_patch_ops(base, ops)
if result.soft_warnings:
    # Ask user confirmation
    yield "This change introduces the following considerations:\n"
    for warn in result.soft_warnings:
        yield f"  - {warn}\n"
    yield "Apply anyway? (y/n)"
```

### 7.3 User Reloads After Prompt/Model Update

**Detection:** N/A - compiled recipe is already stored
**Recovery:** None needed - we serve stored `compiled_recipe`, not re-generated

This is the key insight: **compiled recipes are deterministically derived and stored.** Model changes don't affect existing variants.

### 7.4 Variant Referenced by Multiple Plans

**Scenario:** User copies a meal with variant to another week
**Detection:** Reference counting or snapshot scanning
**Recovery:**
- Deep-copy variant into new snapshot (recommended)
- Or use stable variant IDs that can be shared

```python
def copy_meal_to_plan(meal: dict, target_snapshot: dict):
    if meal.get('is_variant'):
        # Deep copy - create new variant ID
        new_variant = copy.deepcopy(meal['compiled_recipe'])
        new_variant_id = f"variant:{target_snapshot['id']}:{meal['date']}"
        new_variant['id'] = new_variant_id
        meal['recipe_ref'] = new_variant_id
        meal['compiled_recipe'] = new_variant
    return meal
```

### 7.5 Concurrent Modification

**Scenario:** Two tabs editing same meal
**Detection:** Optimistic locking via `updated_at` timestamp
**Recovery:**
- Compare timestamps before save
- If conflict, show diff and ask which to keep
- Or: last-write-wins (simpler, less safe)

---

## 8. Trade-off Analysis

### 8.1 This Approach vs Deterministic-Only

| Aspect | LLM + Patch | Deterministic-Only |
|--------|-------------|-------------------|
| **User intent capture** | High - understands "use brown rice" | Low - needs exact commands |
| **Reload stability** | High - patches are stored | High - rules are code |
| **Complexity** | Medium-High | Low |
| **Flexibility** | High - any modification | Low - predefined ops only |
| **Trust** | Requires validation | Inherently trusted |

**Recommendation:** LLM + Patch is worth it for user experience, but constrain ops tightly.

### 8.2 This Approach vs Full Rewrite

| Aspect | LLM + Patch | Full LLM Rewrite |
|--------|-------------|------------------|
| **Reload stability** | High | None (drift risk) |
| **Provenance** | Clear (base + ops) | Lost |
| **Auditability** | High (ops are logged) | Low |
| **LLM cost** | Low (small prompts) | High (full recipes) |
| **Hallucination risk** | Contained | High |

**Recommendation:** Never use full rewrite. Patches are strictly better.

---

## 9. Recommendation

### Verdict: FEASIBLE WITH CONSTRAINTS

The LLM-assisted patch approach is viable but requires:

1. **Tight scope on patch ops** - Start with 4-5 ops only:
   - `replace_ingredient`
   - `add_ingredient`
   - `remove_ingredient` (with acknowledgment)
   - `scale_servings`
   - `add_side`

2. **Strict validation** - Hard failures block, soft warnings notify

3. **Compiled recipe caching** - Store result, never recompute on load

4. **Clear UI affordances** - Show "Modified" badge, list changes

### What We Need to Build

| Component | Effort | Priority |
|-----------|--------|----------|
| Patch schema + dataclasses | 1 day | P0 |
| Validation engine | 1 day | P0 |
| Patch applicator | 0.5 day | P0 |
| Cook route update | 0.5 day | P0 |
| LLM prompt for patch generation | 1 day | P1 |
| Chatbot tool integration | 1 day | P1 |
| Cook UI variant indicator | 0.5 day | P2 |

**Total: ~5-6 days for core functionality**

### What We Explicitly Defer

- UI for manual patch editing (use chat only)
- Patch undo/redo history
- Variant sharing across users
- Catalog variant contributions ("save my version")

---

## Appendix: Example Flows

### A.1 Simple Ingredient Swap

```
User: "Use brown rice instead of white rice in the stir fry"

LLM generates:
{
  "patch_ops": [{
    "op": "replace_ingredient",
    "target_index": 2,
    "target_name": "white rice",
    "replacement": {"name": "brown rice", "quantity": "2 cups"},
    "reason": "user_request"
  }]
}

Validation: PASS
Apply: ingredients_raw[2] = "2 cups brown rice"
Store: compiled_recipe in snapshot
Cook route: /api/cook/variant:mp_2025-01-01_123:2025-01-03 → returns modified recipe
```

### A.2 Add Side Dish

```
User: "Add a caesar salad to Monday's dinner"

LLM generates:
{
  "patch_ops": [{
    "op": "add_side",
    "recipe_id": "456789",  // Caesar Salad from catalog
    "reason": "user_request"
  }]
}

Result: Bundle with [main: original, side: Caesar Salad]
Cook route: /api/cook/bundle:mp_2025-01-01_123:2025-01-01
```

### A.3 Validation Failure

```
User: "Remove all the ingredients"

LLM generates:
{
  "patch_ops": [
    {"op": "remove_ingredient", "target_index": 0, ...},
    {"op": "remove_ingredient", "target_index": 1, ...},
    ...
  ]
}

Validation: FAIL - "Result would have no ingredients"
Response: "I can't remove all ingredients - the recipe needs at least one."
```
