# Step 2d: Subset Enrichment Strategy

**Date:** 2025-10-28
**Status:** In Progress
**Decision:** Enrich working subset for development, defer full enrichment

---

## Why This Approach is Smart

### ✅ Advantages

1. **Fast iteration** - Can modify parser and re-run quickly
2. **Smaller dataset** - Easier to inspect and debug
3. **Lower risk** - Don't commit to full enrichment before validating workflow
4. **Flexibility** - Can change structure without re-processing 492K recipes
5. **Testing-friendly** - Enough data to test all features

### 🎯 Use Cases Covered

With subset enrichment, we can fully develop and test:
- Recipe object with structured ingredients
- PlannedMeal with embedded recipes
- MealPlan with dict-by-day structure
- Shopping list generation (no parsing needed!)
- Recipe scaling (pure math!)
- Chat interface with full context
- Allergen filtering
- All agents using new structures

**Everything except searching across the full recipe database**

---

## Subset Size Recommendation

### Option 1: Small Dev Set (5,000 recipes) ⭐ RECOMMENDED
**Rationale:**
- Covers diverse cuisines, difficulties, ingredients
- Fast to enrich (~1-2 minutes)
- Quick to re-enrich if we change parser
- Enough for realistic meal planning (weeks of variety)

**Command:**
```bash
python3 scripts/enrich_recipe_ingredients.py --sample 5000
```

### Option 2: Medium Dev Set (25,000 recipes)
**Rationale:**
- ~5% of full database
- More representative sample
- Still fast to re-enrich (~10 minutes)

### Option 3: Large Dev Set (100,000 recipes)
**Rationale:**
- ~20% of full database
- Near-production experience
- Takes longer (~30 minutes)

**Recommendation:** Start with **5,000 recipes** (Option 1)

---

## Implementation Strategy

### Script Enhancement
Update `enrich_recipe_ingredients.py` to support:

```bash
# Current
--sample N        # Process first N recipes (for testing)
--full            # Process all recipes

# Add
--subset N        # Process N recipes AND mark them (for development)
--subset-random N # Process N random recipes
```

### Database Strategy

**Option A: Mark enriched recipes with flag**
```sql
ALTER TABLE recipes ADD COLUMN enriched BOOLEAN DEFAULT FALSE;

-- Mark enriched recipes
UPDATE recipes
SET enriched = TRUE
WHERE ingredients_structured IS NOT NULL;
```

**Option B: Separate development table** (overkill)

**Option C: Just use first N** (simplest - RECOMMENDED)
- Enrich first 5,000 recipes
- Development code works with these
- Later: enrich rest when ready

**Choose Option C for simplicity**

---

## Updated Enrichment Script

### Add --limit parameter

```python
def enrich_recipes(self, limit: Optional[int] = None) -> Dict:
    """
    Enrich recipes with optional limit.

    Args:
        limit: Max recipes to process (None = all)
    """
    cursor.execute("""
        SELECT id, name, ingredients_raw
        FROM recipes
        WHERE ingredients_raw IS NOT NULL
        LIMIT ?
    """, (limit,) if limit else ())

    # ... rest of processing
```

---

## How to Use During Development

### 1. Enrich Subset
```bash
python3 scripts/enrich_recipe_ingredients.py --sample 5000
```

### 2. Develop with Subset
Code works normally - just operates on 5,000 enriched recipes:

```python
# Database queries work same way
recipes = db.search_recipes(query="chicken", limit=20)

# But only first 5,000 have structured ingredients
for recipe in recipes:
    if recipe.ingredients_structured:
        # Use structured data
        for ing in recipe.ingredients_structured:
            print(f"{ing.quantity} {ing.unit} {ing.name}")
    else:
        # Fallback to raw
        for ing in recipe.ingredients_raw:
            print(ing)
```

### 3. Test Everything
- Create meal plans
- Generate shopping lists
- Scale recipes
- Chat interface
- All features work!

### 4. Later: Full Enrichment
When ready (after validating approach):
```bash
# Re-run with --full
python3 scripts/enrich_recipe_ingredients.py --full

# Picks up where subset left off
# Only enriches remaining 487,630 recipes
```

---

## Code Pattern: Handle Partial Enrichment

### Recipe Model
```python
@dataclass
class Recipe:
    # ... existing fields ...

    ingredients_structured: Optional[List[Ingredient]] = None

    def has_structured_ingredients(self) -> bool:
        """Check if recipe has been enriched."""
        return self.ingredients_structured is not None

    def get_ingredients_for_shopping(self) -> List:
        """Get ingredients, preferring structured."""
        if self.has_structured_ingredients():
            return self.ingredients_structured
        else:
            # Fallback: parse on-the-fly (slower but works)
            return self._parse_ingredients_lazy()
```

### Shopping Agent
```python
def create_grocery_list(self, meal_plan_id: str):
    """Generate shopping list."""
    meal_plan = self.db.get_meal_plan(meal_plan_id)

    for meal in meal_plan.meals_by_day.values():
        recipe = meal.main_recipe

        if recipe.has_structured_ingredients():
            # Fast path: use structured
            for ing in recipe.ingredients_structured:
                all_ingredients.append(ing)
        else:
            # Slow path: parse now
            for raw in recipe.ingredients_raw:
                parsed = self.parser.parse(raw)
                all_ingredients.append(parsed)

    # ... consolidate and generate list
```

**Result:** Everything works whether recipe is enriched or not!

---

## Benefits of This Approach

### During Development
✅ Work with real enriched data
✅ Fast iteration (re-enrich 5K in ~2 min if needed)
✅ Easy to inspect and debug
✅ Enough variety for testing
✅ Can modify parser without guilt

### When Ready for Production
✅ Run full enrichment once
✅ Already validated the approach
✅ Parser improvements incorporated
✅ No surprises

### Flexibility
✅ Can add more recipes to subset anytime
✅ Can change enrichment strategy
✅ Can improve parser and re-enrich subset
✅ No commitment to full DB until ready

---

## Testing Strategy with Subset

### What to Test

1. **Recipe Object** - Load enriched recipes, verify structure
2. **PlannedMeal** - Create meals with full recipe objects
3. **MealPlan** - Dict-by-day access patterns
4. **Shopping List** - Consolidation with structured ingredients
5. **Recipe Scaling** - Math operations on quantities
6. **Chat Interface** - Full context, filtering, suggestions
7. **Performance** - Measure speed improvements

### Test Data Selection

**Ensure 5,000-recipe subset includes:**
- [ ] Common cuisines (Italian, Mexican, Asian, American)
- [ ] Various difficulties (easy, medium, hard)
- [ ] Different time ranges (15 min, 30 min, 60 min+)
- [ ] Vegetarian, vegan, gluten-free options
- [ ] Simple recipes (5 ingredients)
- [ ] Complex recipes (20+ ingredients)

**How to ensure diversity:**
Use stratified sampling (future enhancement) or just take first 5,000 (likely diverse enough given Food.com dataset randomness)

---

## Migration Path

### Phase 1: Development (Now)
- Enrich 5,000 recipes
- Develop all features
- Test with subset
- Iterate on parser if needed

### Phase 2: Expanded Testing (Later)
- Enrich 25,000 recipes
- Test at scale
- Validate performance
- Ensure no issues

### Phase 3: Production (When Ready)
- Enrich all 492,630 recipes
- Deploy to production
- Monitor for any issues

---

## Documentation

### Mark in Code
```python
# NOTE: Currently only first 5,000 recipes are enriched
# To enrich all: python3 scripts/enrich_recipe_ingredients.py --full
```

### Update decisions.md
```markdown
## Decision 4: Subset Enrichment for Development

**Date:** 2025-10-28
**Status:** ✅ Approved

**Decision:** Enrich 5,000 recipes for development, defer full enrichment

**Rationale:**
- Fast iteration during development
- Can modify parser without re-processing 492K recipes
- Enough data for realistic testing
- Lower risk, more flexible

**Full enrichment:** Scheduled for later after validation
```

---

## Command to Run

```bash
# Enrich 5,000 recipes for development
python3 scripts/enrich_recipe_ingredients.py --sample 5000

# Estimated time: 1-2 minutes
# Database growth: ~11 MB (vs 1 GB for full)
# Recipes covered: 1% of database (plenty for dev)
```

---

## Success Criteria

After subset enrichment:
✅ 5,000 recipes have `ingredients_structured`
✅ Can load and use structured ingredients
✅ Shopping list generation works with enriched recipes
✅ Recipe scaling works
✅ All tests pass
✅ Chat interface can use full context

**Then proceed to Step 2e: Design Enhanced Recipe Object**

---

**End of Step 2d Subset Enrichment Strategy**
