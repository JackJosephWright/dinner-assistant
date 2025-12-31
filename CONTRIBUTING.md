# Contributing to Meal Planning Assistant

Thank you for your interest in contributing! This document provides guidelines and instructions for contributing to this project.

## 🎯 Code of Conduct

- Be respectful and inclusive
- Provide constructive feedback
- Focus on what is best for the community
- Show empathy towards other community members

## 🚀 Getting Started

### Prerequisites

- Python 3.10 or higher
- Git
- Anthropic API key (for testing AI features)

### Development Setup

1. **Fork and clone the repository**
   ```bash
   git clone https://github.com/yourusername/dinner-assistant.git
   cd dinner-assistant
   ```

2. **Set up Python environment**
   ```bash
   # Create virtual environment
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate

   # Install dependencies
   pip install -r requirements.txt
   pip install -r requirements-dev.txt
   ```

3. **Configure environment**
   ```bash
   cp .env.example .env
   # Edit .env and add your ANTHROPIC_API_KEY
   ```

4. **Initialize databases**
   ```bash
   # Download food_com_recipes.csv (link provided separately)
   python scripts/load_recipes.py
   ```

5. **Run tests to verify setup**
   ```bash
   pytest
   ```

## 🧪 Test-Driven Development

This project follows **Test-Driven Development (TDD)**:

### TDD Workflow: Red → Green → Refactor

1. **RED 🔴** - Write a failing test
2. **GREEN 🟢** - Write minimal code to pass
3. **REFACTOR ♻️** - Improve code quality

### Testing Requirements

**All contributions must include tests:**

```bash
# Run all tests
pytest

# Run with coverage (must maintain 80%+ on new code)
pytest --cov=src --cov-report=html

# Run specific test types
pytest tests/unit/           # Unit tests
pytest tests/integration/    # Integration tests
pytest tests/e2e/            # End-to-end tests

# Run tests on file change (recommended during development)
pytest-watch
```

### Writing Tests

**Test Structure:**
```python
"""
Description of what this test file covers.
"""
import pytest
from src.module import MyClass

class TestMyFeature:
    """Test suite for MyFeature."""

    def test_basic_functionality(self, db):
        """Test that basic operation works."""
        # Arrange
        instance = MyClass(db)

        # Act
        result = instance.do_something()

        # Assert
        assert result == expected_value
```

**Best Practices:**
- One test per behavior
- Clear test names (`test_save_meal_plan_creates_events`)
- Use fixtures for shared setup
- Test edge cases and error handling
- Keep tests fast (< 1 second each)

## 📝 Code Style

### Python Style Guide

We follow **PEP 8** with some modifications:

```python
# Good: Type hints on all functions
def save_meal_plan(
    week_of: str,
    meals: List[Dict[str, Any]],
    preferences_applied: Optional[List[str]] = None,
) -> Dict[str, Any]:
    """
    Save a meal plan with type-safe parameters.

    Args:
        week_of: ISO date string (e.g., "2025-01-20")
        meals: List of meal dictionaries
        preferences_applied: Optional preference list

    Returns:
        Result dictionary with success status
    """
    pass

# Good: Docstrings on all public methods
# Good: Type hints on parameters and returns
# Good: Clear variable names
```

### Code Quality Checks

```bash
# Format code (we use black)
black src/ tests/

# Type checking (we use mypy)
mypy src/

# Linting (we use pylint)
pylint src/
```

### Naming Conventions

- **Classes**: PascalCase (`MealEvent`, `PlanningTools`)
- **Functions**: snake_case (`save_meal_plan`, `get_recipe`)
- **Constants**: UPPER_SNAKE_CASE (`MAX_RECIPES`, `DEFAULT_SERVINGS`)
- **Private methods**: Leading underscore (`_get_recipe_safely`)

## 🔀 Git Workflow

### Branch Naming

- `feature/description` - New features
- `fix/description` - Bug fixes
- `docs/description` - Documentation only
- `test/description` - Test improvements
- `refactor/description` - Code refactoring

Examples:
- `feature/add-nutritional-tracking`
- `fix/recipe-search-timeout`
- `test/add-meal-event-tests`

### Commit Messages

Follow the [Conventional Commits](https://www.conventionalcommits.org/) format:

```
<type>(<scope>): <subject>

<body>

<footer>
```

**Types:**
- `feat`: New feature
- `fix`: Bug fix
- `docs`: Documentation
- `test`: Tests
- `refactor`: Code refactoring
- `style`: Formatting
- `chore`: Maintenance

**Examples:**
```
feat(planning): add cuisine preference learning

Implement automatic cuisine preference detection based on
meal history ratings. Updates planning agent to prioritize
highly-rated cuisines.

Closes #123
```

```
fix(database): handle missing recipes.db gracefully

Add try-catch around recipe lookup to allow meal events
to be created even when recipes.db is unavailable.

Fixes #456
```

```
test(integration): add meal event creation tests

Add 9 integration tests for save_meal_plan() to verify
meal events are created automatically.

Part of TDD implementation for meal events system.
```

### Pull Request Process

1. **Create feature branch**
   ```bash
   git checkout -b feature/my-new-feature
   ```

2. **Write tests first (TDD)**
   ```bash
   # Write failing tests
   pytest tests/test_my_feature.py  # Should fail
   ```

3. **Implement feature**
   ```bash
   # Write code to pass tests
   pytest tests/test_my_feature.py  # Should pass
   ```

4. **Refactor and verify**
   ```bash
   # Clean up code
   pytest  # All tests should still pass
   ```

5. **Commit changes**
   ```bash
   git add .
   git commit -m "feat(scope): description"
   ```

6. **Push and create PR**
   ```bash
   git push origin feature/my-new-feature
   ```

7. **PR Requirements:**
   - All tests passing (77+ tests)
   - Coverage maintained or improved
   - Documentation updated
   - Code reviewed by maintainer
   - No merge conflicts

## 📖 Documentation

### Code Documentation

**All public functions must have docstrings:**

```python
def save_meal_plan(
    week_of: str,
    meals: List[Dict[str, Any]],
) -> Dict[str, Any]:
    """
    Save a generated meal plan and create meal events.

    This method performs two operations:
    1. Saves the meal plan to the meal_plans table
    2. Creates individual meal_events for tracking

    Args:
        week_of: ISO date of Monday (e.g., "2025-01-20")
        meals: List of meal dictionaries with required keys:
            - date: ISO date string
            - recipe_id: Recipe identifier
            - recipe_name: Display name

    Returns:
        Dictionary with keys:
            - success: Boolean
            - meal_plan_id: ID if successful
            - error: Error message if failed

    Example:
        >>> result = tools.save_meal_plan(
        ...     week_of="2025-01-20",
        ...     meals=[{"date": "2025-01-20", ...}]
        ... )
        >>> result["success"]
        True

    Note:
        Recipe enrichment is attempted but gracefully handled
        if recipes.db is unavailable.
    """
    pass
```

### Documentation Files

When adding features, update relevant docs:

- `README.md` - If user-facing changes
- `docs/development/CURRENT_SYSTEM.md` - If architecture changes
- `docs/development/ROADMAP.md` - If completing roadmap items
- Add new docs to `docs/` as needed

## 🐛 Bug Reports

### Before Submitting

1. Check existing issues
2. Verify it's reproducible
3. Check if it's already fixed in main

### Bug Report Template

```markdown
**Description**
Clear description of the bug

**To Reproduce**
Steps to reproduce:
1. Run command X
2. Input Y
3. See error Z

**Expected Behavior**
What should happen

**Actual Behavior**
What actually happens

**Environment**
- OS: [e.g., Ubuntu 22.04]
- Python version: [e.g., 3.10.8]
- Project version: [commit hash or tag]

**Additional Context**
Logs, screenshots, etc.
```

## ✨ Feature Requests

### Feature Request Template

```markdown
**Problem Statement**
What problem does this solve?

**Proposed Solution**
How should it work?

**Alternatives Considered**
Other approaches you've considered

**Additional Context**
Use cases, examples, etc.
```

## 🎯 Areas for Contribution

### High Priority
- Nutritional tracking integration
- Budget optimization features
- Enhanced preference learning
- Performance optimizations

### Medium Priority
- Web interface (Flask)
- Additional cuisine support
- Recipe recommendation improvements
- Shopping list enhancements

### Good First Issues
- Documentation improvements
- Test coverage expansion
- Code refactoring
- Bug fixes

Look for issues labeled `good-first-issue` or `help-wanted`.

## 📊 Review Process

### What We Look For

✅ **Code Quality**
- Follows style guide
- Well-documented
- Properly tested
- No unnecessary complexity

✅ **Testing**
- Tests pass
- Coverage maintained
- Edge cases covered
- Fast execution

✅ **Documentation**
- Clear docstrings
- Updated relevant docs
- Examples provided
- Breaking changes noted

## 🤝 Community

- **Questions?** Open a discussion
- **Ideas?** Submit a feature request
- **Bug?** Open an issue
- **Contribution?** Open a pull request

## 📚 Resources

- [Testing Guide](docs/testing/TESTING.md)
- [TDD Workflow](docs/testing/TDD_COMPLETE.md)
- [System Architecture](docs/development/CURRENT_SYSTEM.md)
- [Roadmap](docs/development/ROADMAP.md)

---

**Thank you for contributing!** Every contribution makes this project better.
