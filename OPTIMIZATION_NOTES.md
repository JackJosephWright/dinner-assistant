# Query Optimization Implementation Notes

## Overview
This document describes the structured query optimization implemented in the `feature/structured-query-optimization` branch.

## Changes Made

### 1. Database Enhancement (`scripts/migrate_recipes_enhanced.py`)
- Created `recipes_enhanced` table with pre-computed indexed fields
- **New columns**:
  - `cuisine` (indexed) - Pre-extracted from tags
  - `difficulty` (indexed) - Pre-extracted from tags
  - `estimated_time` (indexed) - Pre-extracted from tags
  - `primary_protein` (indexed) - Extracted from ingredients (chicken, beef, fish, tofu, etc.)
  - `dietary_flags` - JSON array: vegetarian, vegan, gluten-free, dairy-free
  - `ingredient_list` - Searchable concatenated ingredient names

- **Migration stats** (492,630 recipes):
  - With cuisine: ~25%
  - With time: ~94%
  - With protein: ~47%
  - Processing time: ~5 minutes

### 2. Structured Search Method (`database.py:263-397`)
- New method: `search_recipes_structured()`
- **Parameters**:
  - `cuisines`: List[str] - Filter by cuisine types
  - `min_time`/`max_time`: int - Time range filtering
  - `difficulty`: List[str] - easy, medium, hard
  - `proteins`: List[str] - chicken, beef, tofu, etc.
  - `dietary_flags`: List[str] - vegetarian, vegan, etc.
  - `exclude_ingredients`: List[str] - Ingredients to avoid
  - `exclude_ids`: List[str] - Recipe IDs to skip
  - `limit`: int - Max results (default 15)

- **Returns**: Compact dictionaries optimized for LLM:
  ```python
  {
    "id": "12345",
    "name": "Salmon Teriyaki Bowl",
    "cuisine": "Japanese",
    "time": 35,
    "difficulty": "medium",
    "protein": "salmon"
  }
  ```

- **Fallback**: If `recipes_enhanced` doesn't exist, falls back to original `search_recipes()`

### 3. Planning Agent Updates (✅ COMPLETED)
- ✅ Replaced keyword generation with structured filter generation
- ✅ Use single LLM call to generate all search criteria (JSON format)
- ✅ Reduced candidate list from 50 → 20 recipes max (60% reduction)
- ✅ Reduced token usage with compact format (single line per recipe)
- ✅ Updated both `_search_recipes_node()` and `swap_meal()` to use structured search
- ✅ Token reduction: max_tokens reduced from 1024 → 512 for search generation

## Performance Improvements

### Expected Gains:
- **DB Query Speed**: 50-200ms → 10-30ms (indexed lookups)
- **Candidate Count**: 50 recipes → 15 recipes (70% reduction)
- **Token Usage**: 200-400 tokens → 50-100 tokens (75% reduction)
- **LLM Selection Time**: 30-50s → 10-20s (50% faster)
- **Total Meal Planning**: 60s → 25-35s (40-60% faster)

### Quality Improvements:
- More precise filtering (cuisine, protein, dietary)
- Better respect for user preferences
- Less "wasted" candidates sent to LLM
- Faster iterations on meal plan changes

## Next Steps

1. ✅ Database migration script created
2. ✅ Structured search method added
3. ✅ Update planning agent to use structured search
4. ✅ Migration completed (492,630 recipes processed)
5. ⏳ Test performance improvements
6. ⏳ Measure actual speed gains
7. ⏳ Compare with baseline

## Testing Plan

### Test Scenarios:
1. **Basic meal planning**: "Plan meals for the week"
2. **With preferences**: "Plan meals, mostly Italian and Mexican"
3. **With constraints**: "Plan meals under 45 minutes, vegetarian"
4. **Meal swaps**: "Swap Tuesday for something with chicken"

### Metrics to Track:
- Time to generate initial plan
- Time to swap a meal
- Number of LLM API calls
- Total tokens used
- Quality of meal selections
- User satisfaction

## Rollback Plan

If optimization doesn't work as expected:
1. The `search_recipes_structured()` method has built-in fallback
2. Original `search_recipes()` method is untouched
3. Can easily revert planning agent changes
4. Enhanced table can coexist with original table

## Notes

- Migration is idempotent (can be run multiple times safely)
- Enhanced table adds ~10-20% to database size
- All changes are backward-compatible
- Original functionality preserved as fallback
