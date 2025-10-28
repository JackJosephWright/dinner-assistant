# Planning Tool Implementation Summary

**Date**: October 28, 2025
**Phase**: 3.1 - 3.2 Complete
**Status**: ✅ COMPLETE

## Overview

Implemented the `plan_meals_smart` tool in the chat interface that enables intelligent meal planning using:
- SQL search across 5,000 enriched recipes
- Exact allergen filtering using structured ingredient data
- MealPlan creation with embedded Recipe objects
- 0-query operations for shopping lists and allergen checks after initial load

## Implementation Details

### Files Modified

#### `src/chatbot.py`

1. **Added imports** (lines 12-17):
   - `datetime, timedelta` for date handling
   - `PlannedMeal, MealPlan` from `src.data.models`
   - Fixed import: `from src.main import MealPlanningAssistant`

2. **Added `_select_recipes_with_llm()` method** (lines 44-112):
   - Intelligently selects recipes considering variety and preferences
   - Takes recent meal history to avoid repetition
   - Falls back to first N recipes if LLM fails
   - Uses Claude Sonnet 4.5 with compact prompts

3. **Added `plan_meals_smart` tool** (lines 172-198):
   - Tool definition with schema for:
     - `num_days`: Number of days to plan
     - `search_query`: Keywords for SQL search
     - `exclude_allergens`: Array of allergens to avoid
     - `max_time`: Maximum cooking time constraint

4. **Added tool execution logic** (lines 327-395):
   - Step 1: Generate date range from today
   - Step 2: SQL search for 100 candidates
   - Step 3: Filter by allergens using `recipe.has_allergen()`
   - Step 4: LLM selects with variety consideration
   - Step 5: Create PlannedMeal objects with embedded recipes
   - Step 6: Create and save MealPlan
   - Step 7: Return summary with ingredients and allergens

### Test Coverage

**File**: `test_plan_smart.py`

Three comprehensive tests:

1. **TEST 1: Basic Planning**
   - SQL search → filter → create plan → save → load
   - Verifies: 4 meals created, 58 ingredients, allergens detected
   - ✅ PASSED

2. **TEST 2: Allergen Filtering**
   - Searches for beef, excludes dairy
   - Verifies: 53 dairy-free recipes found, plan is dairy-free
   - ✅ PASSED

3. **TEST 3: Shopping List Generation**
   - Creates 3-meal plan with embedded recipes
   - Generates shopping list WITHOUT database queries
   - Verifies: 7 categories, 26 total ingredients
   - ✅ PASSED - 0 queries!

## Key Architecture Decisions

### 1. No RAG/Vector Search

**Decision**: Use SQL + exact filtering instead of RAG

**Rationale**:
- RAG saves only 40ms on 2660ms operation (1.5% improvement)
- Structured ingredient data enables exact boolean filtering
- "no gluten" requires exact filtering, not fuzzy similarity
- LLM processing (2000-3000ms) is real bottleneck, not SQL (50-100ms)

### 2. Embedded Recipe Objects

**Decision**: PlannedMeal contains full Recipe object (not just ID)

**Benefits**:
- Shopping list generation: 0 queries
- Allergen checking: 0 queries
- Ingredient access: 0 queries
- All operations work offline after initial plan load

### 3. SQL + LLM Hybrid

**Decision**: Wide SQL search (100 recipes) → exact filter → LLM selection

**Flow**:
1. SQL finds candidates matching keywords
2. Exact filtering removes allergens/time violations
3. LLM selects considering variety and preferences

**Why**:
- SQL is fast and handles exact constraints
- Structured data enables precise boolean filtering
- LLM adds intelligence for variety and taste

## Performance Characteristics

### Development Database (5K recipes, 100% enriched)

- **SQL search**: ~50ms for 100 recipes
- **Allergen filtering**: ~10ms (boolean checks on loaded objects)
- **LLM selection**: ~2000-3000ms (dominates total time)
- **MealPlan creation**: ~5ms
- **Database save**: ~20ms
- **Total**: ~2-3 seconds

### Production Scaling (492K recipes, 1% enriched)

- SQL search will be similar (~50-100ms with indexes)
- Need to enrich more recipes (currently only 5K enriched)
- LLM selection time remains constant (processes 100 candidates)

## Example Usage

```python
# User: "Plan 4 days of chicken meals, no dairy"

tool_input = {
    "num_days": 4,
    "search_query": "chicken",
    "exclude_allergens": ["dairy"]
}

# Returns:
# ✓ Created 4-day meal plan!
#
# Meals:
# - 2025-10-28: Grilled Chicken Salad (12 ingredients)
# - 2025-10-29: Chicken Stir Fry (15 ingredients)
# - 2025-10-30: Lemon Herb Chicken (10 ingredients)
# - 2025-10-31: Chicken Tacos (14 ingredients)
#
# 📊 51 total ingredients, allergens: eggs, gluten
```

## What Works Now

✅ SQL search across 5,000 enriched recipes
✅ Exact allergen filtering using `recipe.has_allergen()`
✅ Time constraint filtering
✅ LLM-based recipe selection for variety
✅ MealPlan creation with embedded recipes
✅ Database persistence and loading
✅ Shopping list generation (0 queries)
✅ Allergen checking across entire plan (0 queries)

## What's Next (Future Phases)

### Phase 3.3: Additional Chat Tools
- Tool: `swap_meal` - Replace a meal with alternative
- Tool: `adjust_servings` - Scale specific recipes
- Tool: `check_allergens` - Detailed allergen report

### Phase 3.4: Full Chat Flow Testing
- Test multi-turn conversations
- Test iterative refinement
- Test tool chaining
- Performance optimization

### Future: Full Recipe Enrichment
- Enrich all 492K recipes (currently only 5K)
- Run enrichment pipeline on production database
- Estimated time: ~10 hours for full enrichment

## Success Metrics

- ✅ All 3 tests passing
- ✅ 0-query architecture working for post-load operations
- ✅ Exact allergen filtering functional
- ✅ Embedded recipes enable offline operations
- ✅ SQL + LLM hybrid approach validated

## Technical Insights

1. **Structured ingredients are MORE valuable than RAG**
   - Enable exact boolean filtering
   - Support precise allergen detection
   - Allow accurate quantity scaling
   - Provide categorization for shopping lists

2. **Embedded objects eliminate N+1 query problem**
   - Traditional: 1 query per meal to get recipe (N queries)
   - Our approach: 0 queries after initial plan load
   - Shopping list: 0 queries (all data embedded)
   - Allergen check: 0 queries (all data embedded)

3. **LLM is best for variety, not search**
   - SQL handles keyword matching efficiently
   - Structured data handles exact constraints
   - LLM adds intelligence for taste/variety
   - Each component plays to its strengths

## Conclusion

The `plan_meals_smart` tool successfully demonstrates the value of our Phase 2 work (enhanced Recipe objects with structured ingredients). The 0-query architecture enables fast, offline operations after initial load, and exact allergen filtering provides reliable safety features that fuzzy similarity search cannot match.

**Ready for**: Integration testing with full chat flow and user testing with conversational interface.
