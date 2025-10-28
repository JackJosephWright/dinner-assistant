# Dinner Assistant - Project Context

## Overview
AI-powered multi-agent meal planning system using MCP (Model Context Protocol) and LangGraph. Helps users plan meals, generate shopping lists, and get cooking guidance based on 492K+ recipes and personal meal history.

## Tech Stack
- **Language**: Python 3.10+
- **AI Framework**: LangGraph (multi-agent orchestration)
- **Protocol**: MCP (Model Context Protocol) for tool servers
- **Database**: SQLite (recipes.db, user_data.db)
- **LLM**: Anthropic Claude (via API)
- **Testing**: pytest (77 tests, 92% model coverage)

## Architecture

```
User Input
    ↓
LangGraph Orchestrator
    ├─ Planning Agent (meal plan generation)
    ├─ Shopping Agent (grocery list consolidation)
    └─ Cooking Agent (step-by-step guidance)
    ↓
MCP Tool Server (search_recipes, get_meal_history, etc.)
    ↓
Database Interface (DatabaseInterface class)
    ↓
SQLite DBs (recipes.db, user_data.db)
```

## Key Components

### Data Layer (`src/data/`)
- **models.py** - Recipe, MealPlan, GroceryList data classes
- **database.py** - DatabaseInterface for SQLite operations

### MCP Server (`src/mcp_server/`)
- **server.py** - MCP protocol server implementation
- **tools/planning_tools.py** - Recipe search, meal history, preferences
- **tools/shopping_tools.py** - Ingredient consolidation, categorization
- **tools/cooking_tools.py** - Recipe details, substitutions

### Agents (`src/agents/`)
- **planning_agent.py** - Generates 7-day meal plans
- **shopping_agent.py** - Creates consolidated shopping lists
- **cooking_agent.py** - Provides cooking guidance

### Entry Points
- **src/main.py** - CLI interface (interactive/workflow modes)
- **src/chatbot.py** - Natural language chatbot mode
- **src/onboarding.py** - User preference collection

## Database Details

### recipes.db (Production)
- **Size:** 2.2 GB
- **Recipes:** 492,630 total, 5,000 enriched (1%)
- **Table:** recipes
- **Fields:** id, name, description, ingredients, ingredients_raw, ingredients_structured, steps, servings, tags, etc.
- **Indexed on:** name, tags, estimated_time
- **Status:** 5,000 recipes enriched with structured ingredients

### recipes_dev.db (Development) ⭐
- **Size:** 1.1 GB
- **Recipes:** 5,000 total, 5,000 enriched (100%)
- **Purpose:** Fast development environment with all enriched recipes
- **Query Speed:** 98x faster than production
- **Use for:** Feature development, testing enriched data features

### user_data.db
- **meal_history**: Historical meals for learning
- **meal_plans**: Generated meal plans
- **preferences**: User preferences and dietary restrictions
- **grocery_lists**: Shopping lists with store sections

## Current Status (Last Updated: 2025-10-28)

### ✅ Phase 1: Foundation - Complete
- Recipe database loaded (492,630 recipes)
- MCP server operational with planning tools
- Planning, Shopping, Cooking agents implemented
- MealEvent system with rich tracking
- UserProfile and onboarding complete
- 77 tests passing (5.30 seconds)

### 🔄 Phase 2: Recipe Enrichment - In Progress (75% complete)
**What's Working:**
- ✅ Enhanced Recipe with structured ingredients (Ingredient, NutritionInfo dataclasses)
- ✅ Ingredient parsing engine (98% accuracy, 0.958 avg confidence)
- ✅ Development database created (5,000 enriched recipes, 100% enriched)
- ✅ Recipe helper methods (scaling, allergen detection, serialization)
- ✅ Comprehensive documentation (13 design docs, 3 dev guides)

**Current:** Step 3 complete - Enhanced Recipe implemented
**Next:** Step 4 - Update DatabaseInterface to load structured ingredients

**Key Files:**
- `src/data/models.py:18-336` - Ingredient, NutritionInfo, Enhanced Recipe
- `scripts/enrich_recipe_ingredients.py` - Parser and enrichment engine
- `scripts/create_dev_database.py` - Dev database creation
- `data/recipes_dev.db` - 5,000 enriched recipes (1.1 GB, all enriched)
- `docs/development/CHECKPOINT_RECIPE_ENRICHMENT.md` - Complete phase summary

### 📋 Next Steps
- Step 4: Update DatabaseInterface for structured ingredients
- Steps 5-7: PlannedMeal & MealPlan redesign (embedded recipes)
- Steps 8-9: Update agents to use new structures
- Future: Full enrichment of 492K recipes

## Development Commands

```bash
# Run tests
pytest                              # All tests
pytest tests/unit/                  # Unit tests only
pytest --cov=src --cov-report=html  # With coverage
python3 test_enhanced_recipe.py     # Test enhanced Recipe implementation

# Run application
./run.sh chat                       # Chatbot mode
./run.sh interactive                # Interactive CLI
./run.sh workflow                   # One-shot workflow

# Database setup
python3 scripts/load_recipes.py     # Load recipe data (production)
python3 scripts/enrich_5k_recipes.py # Enrich 5,000 recipes
python3 scripts/create_dev_database.py # Create dev database

# Development database
# Use recipes_dev.db for feature development (5K enriched recipes)
# Use recipes.db for production testing (492K total, 5K enriched)

# Git
git log --oneline -10               # Recent commits
```

## Important Patterns

### Tool Response Format
All MCP tools return JSON:
```python
{
    "success": bool,
    "data": {...} | [...],
    "error": str | None
}
```

### Agent State Management
LangGraph agents use dataclasses for state:
```python
@dataclass
class PlanningState:
    user_prefs: dict
    meal_history: list[dict]
    context: str
    meal_plan: dict | None
```

### Testing Conventions
- Unit tests: Mock external dependencies
- Integration tests: Use test databases
- E2E tests: Full workflow validation
- Fixtures in conftest.py

## Key Files Reference

### Core Implementation
- `src/data/models.py:18-73` - Ingredient dataclass
- `src/data/models.py:76-99` - NutritionInfo dataclass
- `src/data/models.py:102-336` - Enhanced Recipe class
- `src/data/database.py:45` - DatabaseInterface.search_recipes()
- `src/agents/planning_agent.py:67` - PlanningAgent.create_plan()
- `src/chatbot.py:123` - Main chatbot loop

### Enrichment Scripts
- `scripts/ingredient_mappings.py` - 150+ category mappings, 50+ allergen mappings
- `scripts/enrich_recipe_ingredients.py` - SimpleIngredientParser, enrichment engine
- `scripts/enrich_5k_recipes.py` - Quick enrichment for dev database
- `scripts/create_dev_database.py` - Dev database creation tool

### Documentation
- `docs/development/CHECKPOINT_RECIPE_ENRICHMENT.md` - Phase 2 complete summary
- `docs/development/DEV_DATABASE.md` - Development database guide
- `docs/development/IMPLEMENTATION_STATUS.md` - What's built vs designed
- `docs/development/ROADMAP.md` - Project roadmap and phases
- `docs/design/decisions.md` - Architecture decision records
- `docs/design/step2e_enhanced_recipe_design.md` - Latest design doc

## Common Issues

1. **Large database files** - recipes.db (2.2 GB), recipes_dev.db (1.1 GB) are git-ignored
2. **Development database** - Use `recipes_dev.db` for feature development (100% enriched)
3. **Non-enriched recipes** - Only 5,000 out of 492K recipes are enriched currently
4. **API keys** - Required: ANTHROPIC_API_KEY in .env
5. **Import paths** - Use absolute imports: `from src.data import models`
6. **Test data** - Integration tests create temporary databases

## Notes

- Built with TDD (Test-Driven Development)
- Focus on clean architecture and separation of concerns
- Emphasis on type hints and comprehensive docstrings
- Production-ready code quality standards
