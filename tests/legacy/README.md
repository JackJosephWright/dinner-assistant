# Legacy Tests (Archived)

This directory contains tests that were written for the pre-Phase 2 architecture and are no longer compatible with the current system.

## Why These Tests Are Archived

In Phase 2, we made significant architectural changes:

1. **Enhanced Recipe Model**: Moved from simple dictionary recipes to structured `EnhancedRecipe` objects with `Ingredient` and `NutritionInfo` dataclasses
2. **Embedded Data Architecture**: Changed from ID-based references to fully embedded objects (0-query architecture)
3. **PlannedMeal Changes**: Now embeds full `Recipe` objects instead of just recipe IDs
4. **MealPlan Enhancements**: Added 10+ query/filter methods and rich functionality
5. **SSE State Synchronization**: Added server-sent events for cross-tab synchronization in web UI

These tests expect the old data models and will fail with import errors or assertion failures.

## Archived Tests

- `test_basic_integration.py` - Integration tests for old agent architecture
- `test_database.py` - Database tests expecting old schema
- `test_models.py` - Tests for old Recipe/MealPlan models
- `test_planning_tools_integration.py` - Planning tool tests with old data structures
- `test_planning.py` - Unit tests for old planning agent

## Current Test Status (After Cleanup)

**Total: 103 passing, 20 failing, 7 errors**

### Passing Tests by Category:
- **Unit Tests**: Enhanced recipe, planned meal, meal plan (Phase 2 data models)
- **Integration Tests**: Database enriched, onboarding, quick integration, plan smart
- **E2E Tests**: Some incremental swap tests
- **Web Tests**: Day selector, plan page, webapp

### Known Failing Tests:
- E2E workflow tests (4 failures - need updating for SSE architecture)
- Performance tests (12 failures - benchmarks need recalibration)
- Chatbot cache tests (4 failures - backup queue logic changed)

### Missing Test Coverage:
- SSE state synchronization (cross-tab updates)
- Shopping list invalidation on meal plan changes
- State broadcast infrastructure in app.py

## Restoration

If you need to restore any of these tests:

1. Update imports from old models to new Phase 2 models
2. Change assertions to expect embedded objects instead of IDs
3. Add structured ingredient handling where recipes are used
4. Update to use `DatabaseInterface` with enriched recipe loading

See `docs/MEAL_PLAN_WORKFLOW_REPORT.md` for details on Phase 2 architecture.
