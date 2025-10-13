# Testing Guide

**Date**: October 13, 2025
**Status**: ✅ 39 unit tests passing

---

## Overview

This project uses **pytest** for testing with a comprehensive test suite covering:
- **Unit tests** - Individual functions/methods in isolation
- **Integration tests** - Multiple components working together
- **End-to-end tests** - Complete workflows from start to finish

---

## Testing Terminology

### Unit Tests
Test individual functions/methods **in isolation** without external dependencies.

**Example**: Test that `MealEvent.to_dict()` returns the correct dictionary format.

**Location**: `tests/unit/`

### Integration Tests
Test how **multiple components work together**.

**Example**: Test that `save_meal_plan()` correctly saves to database AND creates meal_events.

**Location**: `tests/integration/`

### End-to-End (E2E) Tests
Test **complete workflows** from start to finish, simulating real user interactions.

**Example**: Test the entire flow: onboarding → plan meals → save plan → verify events created.

**Location**: `tests/e2e/`

### Fixtures
**Reusable test data/setup** that can be injected into tests (pytest feature).

**Example**: `@pytest.fixture` that creates a fresh test database for each test.

**Location**: `tests/conftest.py`

---

## Setup

### Install Testing Dependencies

```bash
pip3 install -r requirements-dev.txt
```

This installs:
- `pytest` - Testing framework
- `pytest-asyncio` - For testing async functions
- `pytest-cov` - Code coverage reports
- `pytest-mock` - Mocking support
- `freezegun` - Mock datetime for consistent tests

---

## Running Tests

### Run All Tests

```bash
pytest
```

### Run Specific Test Categories

```bash
# Unit tests only
pytest tests/unit/

# Integration tests only
pytest tests/integration/

# End-to-end tests only
pytest tests/e2e/
```

### Run Specific Test File

```bash
pytest tests/unit/test_models.py
```

### Run Specific Test Class or Function

```bash
# Run one class
pytest tests/unit/test_models.py::TestRecipe

# Run one test
pytest tests/unit/test_models.py::TestRecipe::test_recipe_creation
```

### Verbose Output

```bash
pytest -v
```

### Show Print Statements

```bash
pytest -s
```

### Stop on First Failure

```bash
pytest -x
```

### Run Failed Tests Only

```bash
pytest --lf  # last failed
```

---

## Code Coverage

### Generate Coverage Report

```bash
pytest --cov=src --cov-report=html
```

This creates an HTML report in `htmlcov/index.html` showing which lines are covered by tests.

### View Coverage in Terminal

```bash
pytest --cov=src --cov-report=term-missing
```

Shows coverage percentage and lists uncovered lines.

---

## Test Structure

```
tests/
├── __init__.py
├── conftest.py              # Shared fixtures
├── unit/                    # Unit tests
│   ├── __init__.py
│   ├── test_models.py       # ✅ 19 tests
│   └── test_database.py     # ✅ 20 tests
├── integration/             # Integration tests
│   ├── __init__.py
│   └── test_planning_tools.py  # TODO
└── e2e/                     # End-to-end tests
    ├── __init__.py
    └── test_meal_planning_workflow.py  # TODO
```

---

## Current Test Coverage

### ✅ Unit Tests (39 tests passing)

**test_models.py** (19 tests):
- Recipe creation, serialization, field extraction
- MealEvent creation, to_dict/from_dict
- UserProfile creation, defaults, serialization
- PlannedMeal and MealPlan operations

**test_database.py** (20 tests):
- Database initialization and table creation
- Meal event CRUD operations
- User profile CRUD operations
- Meal plan CRUD operations
- Favorite recipes and cuisine preferences
- Recent meals and variety enforcement

### ⏳ Integration Tests (TODO)

**test_planning_tools.py**:
- Test that planning tools correctly integrate with database
- Test save_meal_plan creates meal_events
- Test get_user_preferences reads from user_profile
- Test get_meal_history returns meal_events

### ⏳ End-to-End Tests (TODO)

**test_meal_planning_workflow.py**:
- Complete onboarding flow
- Generate and save meal plan
- Verify meal events created
- Query preferences and history

---

## Writing Tests

### Basic Test Structure

```python
def test_something(db):  # Fixtures injected as parameters
    """Test description."""
    # Arrange - Set up test data
    profile = UserProfile(household_size=4)

    # Act - Perform the operation
    db.save_user_profile(profile)

    # Assert - Verify results
    result = db.get_user_profile()
    assert result.household_size == 4
```

### Using Fixtures

Fixtures are defined in `conftest.py` and automatically available:

```python
def test_with_fixtures(db, sample_user_profile, sample_meal_event):
    """Fixtures are injected automatically."""
    db.save_user_profile(sample_user_profile)
    event_id = db.add_meal_event(sample_meal_event)

    assert event_id > 0
```

### Testing Exceptions

```python
def test_invalid_input():
    """Test that invalid input raises error."""
    with pytest.raises(ValueError):
        UserProfile(household_size=-1)
```

### Testing Async Functions

```python
@pytest.mark.asyncio
async def test_async_function():
    """Test async function."""
    result = await some_async_function()
    assert result is not None
```

---

## Available Fixtures

Defined in `tests/conftest.py`:

### `temp_db_dir`
Creates a temporary database directory, automatically cleaned up after test.

### `db`
Fresh DatabaseInterface instance with temp database for each test.

```python
def test_something(db):
    db.save_user_profile(...)
```

### `sample_recipe`
Pre-configured Recipe object for testing.

### `sample_user_profile`
Pre-configured UserProfile with typical values.

### `sample_meal_event`
Pre-configured MealEvent with ratings and notes.

### `sample_meal_plan`
Pre-configured MealPlan with 2 meals.

---

## Best Practices

### 1. Each Test is Independent
Tests should not depend on each other or shared state.

```python
# GOOD - Fresh database for each test
def test_create(db):
    db.save_user_profile(profile)

def test_read(db):
    # This test gets its own fresh database
    db.save_user_profile(profile)
    result = db.get_user_profile()
```

### 2. Arrange, Act, Assert Pattern

```python
def test_example():
    # Arrange - Set up test data
    profile = UserProfile(household_size=4)

    # Act - Perform the operation
    db.save_user_profile(profile)

    # Assert - Verify results
    result = db.get_user_profile()
    assert result.household_size == 4
```

### 3. Descriptive Test Names

```python
# GOOD
def test_get_user_profile_returns_none_when_not_found():
    ...

# BAD
def test_profile():
    ...
```

### 4. Test One Thing

```python
# GOOD - Tests one behavior
def test_save_user_profile_creates_profile():
    ...

def test_save_user_profile_updates_existing_profile():
    ...

# BAD - Tests multiple things
def test_user_profile():
    # saves, updates, deletes, queries...
```

### 5. Use Fixtures for Setup

```python
# GOOD - Reuse fixtures
def test_something(db, sample_user_profile):
    db.save_user_profile(sample_user_profile)

# BAD - Duplicate setup in every test
def test_something(db):
    profile = UserProfile(
        household_size=4,
        cooking_for={"adults": 2, "kids": 2},
        # ... 20 more lines ...
    )
```

---

## Continuous Integration (CI)

### GitHub Actions Example

Create `.github/workflows/test.yml`:

```yaml
name: Tests

on: [push, pull_request]

jobs:
  test:
    runs-on: ubuntu-latest

    steps:
    - uses: actions/checkout@v3

    - name: Set up Python
      uses: actions/setup-python@v4
      with:
        python-version: '3.10'

    - name: Install dependencies
      run: |
        pip install -r requirements.txt
        pip install -r requirements-dev.txt

    - name: Run tests
      run: pytest --cov=src --cov-report=xml

    - name: Upload coverage
      uses: codecov/codecov-action@v3
```

---

## Debugging Failed Tests

### Show Full Traceback

```bash
pytest --tb=long
```

### Show Local Variables

```bash
pytest --showlocals
```

### Drop into Debugger on Failure

```bash
pytest --pdb
```

### Run with Print Statements

```bash
pytest -s  # Shows print() output
```

---

## Test Statistics

**Current Coverage**:
- ✅ 39 unit tests passing
- ✅ Models fully tested (19 tests)
- ✅ Database operations fully tested (20 tests)
- ⏳ Integration tests needed
- ⏳ End-to-end tests needed

**Run all tests**:
```bash
pytest -v

============================= test session starts ==============================
tests/unit/test_database.py::TestDatabaseInitialization::test_database_creates_tables PASSED
tests/unit/test_database.py::TestDatabaseInitialization::test_database_creates_indexes PASSED
tests/unit/test_database.py::TestMealEventOperations::test_add_meal_event PASSED
... (36 more tests)
============================== 39 passed in 1.42s ===============================
```

---

## Next Steps

1. ⏳ Add integration tests for planning_tools.py
2. ⏳ Add unit tests for onboarding.py
3. ⏳ Add end-to-end workflow tests
4. ⏳ Set up CI/CD pipeline
5. ⏳ Add performance tests for large datasets

---

*Testing framework established: October 13, 2025*
*39 tests passing with 100% coverage of tested modules*
