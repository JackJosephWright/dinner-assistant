# Test Suite Documentation

This directory contains all automated tests for the Dinner Assistant application, organized by test type and scope.

## Directory Structure

```
tests/
├── unit/                   # Fast, isolated unit tests (no external dependencies)
├── integration/            # Tests with database/multiple components
├── e2e/                    # End-to-end workflow tests
├── web/                    # Web UI and Flask app tests
├── performance/            # Performance benchmarks and timing tests
├── conftest.py            # Shared pytest fixtures
└── README.md              # This file
```

## Test Categories

### 1. Unit Tests (`tests/unit/`)

Fast, isolated tests that verify individual components without external dependencies.

**Data Models:**
- `test_models.py` - Core data models (Recipe, MealPlan, etc.)
- `test_enhanced_recipe.py` - Enhanced Recipe with structured ingredients
- `test_planned_meal.py` - PlannedMeal with embedded Recipe objects
- `test_meal_plan.py` - MealPlan with rich query/filter methods
- `test_ingredient_contribution.py` - IngredientContribution dataclass
- `test_grocery_item_incremental.py` - GroceryItem contribution tracking
- `test_contributions.py` - Contribution serialization and management

**Database:**
- `test_database.py` - DatabaseInterface methods (mocked)

**Agents:**
- `test_agentic_agents.py` - Agentic planning agent behaviors
- `test_planning.py` - Planning agent logic
- `test_chatbot_cache.py` - Chatbot caching mechanisms

**Run unit tests only:**
```bash
pytest tests/unit/ -v
```

### 2. Integration Tests (`tests/integration/`)

Tests that verify interactions between multiple components, typically involving database operations.

**Database Integration:**
- `test_database_enriched.py` - DatabaseInterface with enriched recipes
- `test_database_incremental_shopping.py` - Incremental shopping list updates
- `test_onboarding_integration.py` - User onboarding flow

**Feature Integration:**
- `test_grocery_list_incremental.py` - GroceryList add/remove operations
- `test_plan_smart.py` - Smart meal planning with filters
- `test_planning_tools_integration.py` - Planning tools with database

**General Integration:**
- `test_basic_integration.py` - Core integration scenarios
- `test_bug_fixes.py` - Regression tests for fixed bugs
- `test_quick_integration.py` - Fast integration smoke tests
- `test_vertical_slice.py` - Full vertical slice testing

**Run integration tests only:**
```bash
pytest tests/integration/ -v
```

### 3. End-to-End Tests (`tests/e2e/`)

Complete workflow tests that simulate real user scenarios.

- `test_meal_planning_workflow.py` - Full meal planning workflow
- `test_incremental_swap.py` - Meal swap with shopping list update

**Run e2e tests only:**
```bash
pytest tests/e2e/ -v
```

### 4. Web Tests (`tests/web/`)

Tests for Flask web application, UI components, and frontend functionality.

- `test_webapp.py` - Flask routes and endpoints
- `test_plan_page.py` - Meal plan page functionality
- `test_day_selector.py` - Day selector component

**Run web tests only:**
```bash
pytest tests/web/ -v
```

### 5. Performance Tests (`tests/performance/`)

Benchmarks and timing tests to track performance metrics.

- `test_simple_timing.py` - Basic operation timing
- `test_web_performance.py` - Web endpoint performance
- `instrumentation.py` - Performance measurement utilities

**Run performance tests only:**
```bash
pytest tests/performance/ -v
```

## Running Tests

### Run All Tests
```bash
# From project root
pytest

# With verbose output
pytest -v

# With coverage
pytest --cov=src --cov-report=html
```

### Run Specific Test Categories
```bash
# Unit tests only (fastest)
pytest tests/unit/

# Integration tests only
pytest tests/integration/

# E2E tests only (slowest)
pytest tests/e2e/

# Web tests only
pytest tests/web/

# Performance tests only
pytest tests/performance/
```

### Run Specific Test Files
```bash
# Single test file
pytest tests/unit/test_models.py

# Single test function
pytest tests/unit/test_models.py::test_recipe_creation

# Match pattern
pytest -k "incremental" -v
```

### Useful Options
```bash
# Stop on first failure
pytest -x

# Show print statements
pytest -s

# Run in parallel (requires pytest-xdist)
pytest -n auto

# Show slowest tests
pytest --durations=10

# Show test coverage
pytest --cov=src --cov-report=term-missing
```

## Test Guidelines

### Writing Unit Tests
- **No external dependencies** (database, API, filesystem)
- **Fast execution** (< 100ms per test)
- **Use mocks** for external services
- **Test one thing** per test function
- **Clear naming** (`test_<action>_<expected_result>`)

Example:
```python
def test_recipe_scales_ingredients_correctly():
    recipe = Recipe(...)
    scaled = recipe.scale_recipe(2.0)
    assert scaled.ingredients_structured[0].amount == 4.0
```

### Writing Integration Tests
- **Use test database** (via fixtures)
- **Test realistic scenarios** (multiple components)
- **Clean up after test** (fixtures handle this)
- **Acceptable execution time** (< 1s per test)

Example:
```python
def test_swap_meal_updates_shopping_list(db):
    plan = db.create_meal_plan(...)
    grocery_list = db.create_shopping_list(plan)

    db.swap_meal_in_plan(plan.id, date, new_recipe_id)

    updated_list = db.get_grocery_list(grocery_list.id)
    assert old_ingredient not in updated_list.items
    assert new_ingredient in updated_list.items
```

### Writing E2E Tests
- **Test complete workflows** (user perspective)
- **Minimal mocking** (use real components)
- **Verify end state** (not intermediate steps)
- **Slower execution acceptable** (< 10s per test)

Example:
```python
def test_user_creates_plan_and_swaps_meal(assistant):
    # Create plan
    result = assistant.plan_week(num_days=7)
    assert result["success"]

    # Swap meal
    swap_result = assistant.swap_meal(date, new_recipe)
    assert swap_result["success"]

    # Verify shopping list updated
    shopping_list = assistant.get_shopping_list()
    assert new_recipe.ingredients[0] in shopping_list
```

## Test Fixtures

Common fixtures are defined in `conftest.py`:

- `db` - Test database instance
- `test_recipes` - Sample recipe objects
- `mock_api` - Mocked API client
- `assistant` - Test assistant instance

## Continuous Integration

Tests are run automatically on:
- Every commit (via pre-commit hooks)
- Every pull request (via CI pipeline)
- Nightly builds (full test suite + performance)

## Test Coverage

Target coverage: **90%** for core functionality

Check current coverage:
```bash
pytest --cov=src --cov-report=html
open htmlcov/index.html
```

## Troubleshooting

### Tests failing after database changes
```bash
# Recreate test database
rm -f data/test_*.db
pytest tests/integration/ --setup-show
```

### Slow test execution
```bash
# Profile test execution
pytest --durations=0

# Run only fast tests
pytest -m "not slow"
```

### Import errors
```bash
# Ensure PYTHONPATH is set
export PYTHONPATH="${PYTHONPATH}:$(pwd)"

# Or run from project root
cd /home/jack_wright/dinner-assistant && pytest
```

## Contributing

When adding new tests:

1. **Choose the right category** (unit/integration/e2e/web/performance)
2. **Follow naming conventions** (`test_<module>.py`, `test_<action>_<result>`)
3. **Add docstrings** explaining what's being tested
4. **Keep tests independent** (no order dependencies)
5. **Use appropriate fixtures** (from conftest.py)
6. **Update this README** if adding new test categories

## Test Statistics

- **Total Test Files:** 35
- **Unit Tests:** 11 files
- **Integration Tests:** 10 files
- **E2E Tests:** 2 files
- **Web Tests:** 3 files
- **Performance Tests:** 3 files

Last updated: 2025-11-03
