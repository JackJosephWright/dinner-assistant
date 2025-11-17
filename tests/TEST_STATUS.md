# Test Suite Status

Last Updated: 2025-11-07

## Summary

**Total: 103 passing, 20 failing, 7 errors**
**Test Time: 172 seconds (2m 52s)**

## Test Organization

```
tests/
├── unit/              # Fast, isolated tests (Phase 2 data models)
├── integration/       # Multi-component tests
├── e2e/              # End-to-end workflow tests
├── performance/      # Performance and benchmark tests
├── web/              # Web UI tests (Playwright)
└── legacy/           # Archived pre-Phase 2 tests (ignored by pytest)
```

## Passing Tests (103)

### Unit Tests - Phase 2 Data Models ✅
- `test_enhanced_recipe.py` - 7/7 tests
  - Ingredient parsing, scaling, allergen detection
  - Serialization/deserialization
  - Recipe helper methods

- `test_planned_meal.py` - 7/7 tests
  - PlannedMeal with embedded Recipe objects
  - Day assignment, meal types
  - Scaling and portion management

- `test_meal_plan.py` - 10/10 tests
  - MealPlan CRUD operations
  - Query/filter methods (by day, type, allergen)
  - Shopping list generation
  - 0-query architecture validation

### Integration Tests ✅
- `test_database_enriched.py` - Tests loading enriched recipes with structured ingredients
- `test_onboarding_integration.py` - User onboarding flow
- `test_quick_integration.py` - Quick smoke tests
- `test_plan_smart.py` - Smart meal planning logic

### Web Tests ✅
- `test_day_selector.py` - Week selector component
- `test_plan_page.py` - Plan page functionality
- `test_webapp.py` - General web app tests

### E2E Tests (Partial) ✅
- `test_incremental_swap.py` - Some swap scenarios passing

## Failing Tests (20)

### E2E Workflow Tests (4 failures) 🔴
**File**: `test_meal_planning_workflow.py`

Failures:
- `test_new_user_complete_journey`
- `test_returning_user_workflow`
- `test_plan_meals_without_onboarding`
- `test_onboard_after_using_system`

**Likely Cause**: Tests may expect old synchronous architecture, need updating for SSE state sync.

### Performance Tests (12 failures) 🔴
**Files**: `test_simple_timing.py`, `test_web_performance.py`

Failures in `test_simple_timing.py`:
- `test_simple_meal_plan_timing`
- `test_shopping_list_timing`
- `test_cook_page_recipe_load_timing`

Failures in `test_web_performance.py`:
- `test_home_page_performance`
- `test_plan_page_cold_load`
- `test_complete_meal_planning_workflow`
- `test_shopping_list_generation_performance`
- `test_shop_page_load_speed`
- `test_concurrent_request_handling`
- `test_plan_page_benchmark`
- `test_api_plan_current_benchmark`

**Likely Cause**: Benchmarks need recalibration after SSE infrastructure and Phase 2 changes.

### Chatbot Cache Tests (4 failures) 🔴
**File**: `test_chatbot_cache.py`

Failures:
- `test_check_backup_match_direct`
- `test_check_backup_match_related_terms`
- `test_check_backup_match_modifiers`
- `test_check_backup_match_no_match`

**Likely Cause**: Backup queue matching logic changed in recent chatbot updates.

## Errors (7)

### Integration Test Errors ⚠️
**File**: `test_grocery_list_incremental.py` (5 errors)
- `test_add_multiple_recipes`
- `test_add_non_enriched_recipe`
- `test_remove_recipe`
- `test_store_sections`
- `test_serialization`

**File**: `test_contributions.py` (2 errors)
- `test_remove_contributions`
- `test_serialization`

**Likely Cause**: Import errors or missing dependencies. Need investigation.

**File**: `test_vertical_slice.py` (1 error)
- `test_database_connection` - AssertionError

## Missing Test Coverage 🔍

### Critical (Needed for Current Features)
1. **SSE State Synchronization**
   - Cross-tab meal plan updates
   - Shopping list change notifications
   - State stream connection/reconnection
   - Multiple tabs listening simultaneously

2. **Shopping List Invalidation**
   - Cache clearing when meal plan changes
   - Stale notification display
   - Regeneration workflow

3. **Web UI State Management**
   - State broadcast after meal swap
   - State broadcast after shopping list generation
   - EventSource error handling

### Important (Should Add Soon)
4. **Agentic Shopping Agent**
   - Ingredient consolidation via LLM
   - Category organization
   - Scaling instructions handling

5. **Cross-Tab Coordination**
   - Plan tab auto-refresh on changes
   - Shop tab notification on meal plan changes
   - Cook tab integration (pending)

## Test Configuration

**pytest.ini**:
- Legacy tests excluded via `norecursedirs = tests/legacy`
- Markers: unit, integration, e2e, slow, performance, benchmark, web
- Coverage source: `src/`

## Running Tests

```bash
# All active tests (excludes legacy)
pytest

# By category
pytest -m unit
pytest -m integration
pytest -m e2e
pytest -m web
pytest -m performance

# Specific test file
pytest tests/unit/test_enhanced_recipe.py

# With coverage
pytest --cov=src --cov-report=html

# Fast tests only (skip slow/performance)
pytest -m "not slow and not performance"

# Phase 2 data model tests only
pytest tests/unit/test_enhanced_recipe.py tests/unit/test_planned_meal.py tests/unit/test_meal_plan.py
```

## Next Steps

### Immediate (To Get to 100% Passing)
1. Fix 7 import/assertion errors in integration tests
2. Update 4 chatbot cache tests for new backup logic
3. Recalibrate 12 performance benchmarks

### Short-term (Add Missing Coverage)
4. Add SSE state sync tests (new feature)
5. Add shopping list invalidation tests (new feature)
6. Update 4 e2e workflow tests for SSE architecture

### Long-term (Nice to Have)
7. Add agentic agent integration tests
8. Add cross-tab coordination tests
9. Add web UI state management tests

## Architecture Notes

The test suite reflects the **Phase 2 architecture** with:
- Enhanced recipes with structured ingredients
- Embedded data (0-query operations)
- SSE-based cross-tab synchronization
- LLM-powered shopping agent
- Rich MealPlan query methods

Tests in `tests/legacy/` expect the **pre-Phase 2 architecture** and are permanently archived.
