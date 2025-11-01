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

## Current Status (Last Updated: 2025-10-29)

### ✅ Phase 1: Foundation - Complete
- Recipe database loaded (492,630 recipes)
- MCP server operational with planning tools
- Planning, Shopping, Cooking agents implemented
- MealEvent system with rich tracking
- UserProfile and onboarding complete
- 77 tests passing (5.30 seconds)

### ✅ Phase 2: Data Objects - Complete
**What's Complete:**
- ✅ Enhanced Recipe with structured ingredients (Ingredient, NutritionInfo dataclasses)
- ✅ Ingredient parsing engine (98% accuracy, 0.958 avg confidence)
- ✅ Development database created (5,000 enriched recipes, 100% enriched)
- ✅ Recipe helper methods (scaling, allergen detection, serialization)
- ✅ DatabaseInterface loads structured ingredients automatically
- ✅ PlannedMeal with embedded Recipe objects (not just IDs)
- ✅ MealPlan with 10+ query/filter methods
- ✅ Shopping list generation organized by category
- ✅ Allergen detection across entire meal plans
- ✅ **0-query architecture** - All data embedded, works 100% offline
- ✅ Comprehensive documentation (15 design docs, 4 dev guides, 1 workflow report)

**Performance:**
- Initial load: 7 DB queries (~135ms)
- All subsequent operations: **0 queries** (<1ms each)
- Infinite performance improvement for embedded operations

**Test Coverage:**
- `test_enhanced_recipe.py`: 7/7 passing ✅
- `test_database_enriched.py`: 5/5 passing ✅
- `test_planned_meal.py`: 7/7 passing ✅
- `test_meal_plan.py`: 10/10 passing ✅
- `demo_meal_plan_workflow.py`: 11 steps successful ✅
- **Total: 22/22 tests passing**

**Key Files:**
- `src/data/models.py:18-73` - Ingredient dataclass (11 fields, scale method)
- `src/data/models.py:76-99` - NutritionInfo dataclass (placeholder)
- `src/data/models.py:102-336` - Enhanced Recipe (6 new methods)
- `src/data/models.py:340-460` - PlannedMeal with embedded Recipe
- `src/data/models.py:463-631` - MealPlan with 10+ methods
- `src/data/database.py:284-307` - DatabaseInterface with structured ingredient loading
- `docs/MEAL_PLAN_WORKFLOW_REPORT.md` - Complete workflow documentation
- `demo_meal_plan_workflow.py` - Live demonstration script

### 🔄 Phase 3: Chat Integration - In Progress
**What's Complete (2025-10-29):**
- ✅ **Hybrid backup matching strategy** - Vague swap requests now work (src/chatbot.py:182-287)
  - Tier 1: Fast algorithmic checks (vague terms, direct match, related terms)
  - Tier 2: LLM semantic fallback using Claude Haiku
  - Verbose debug output shows which tier matched
- ✅ **Improved LLM recipe selection** - Fixed Recipe ID vs index confusion (src/chatbot.py:71-197)
  - Enhanced prompt with 6-digit ID examples
  - Step-by-step instructions to prevent hallucination
  - Automatic filling of missing slots when LLM returns invalid IDs
- ✅ **Verbose meal plan display** - Always shows current plan state after each interaction (src/chatbot.py:1044-1071)
  - Shows all meals with ingredient counts
  - Displays backup recipes available
  - Clear visibility into meal plan state

**Test Results:**
- Multi-requirement planning working: "5 meals, one chicken, one beef, one thai" → 5 meals created ✅
- Vague swap requests working: "something else, no corned beef" → uses backup queue ✅
- All swaps complete in <10ms (95% faster than fresh search) ✅

**Benefits Ready:**
- ✅ 0-query operations (instant responses)
- ✅ Offline capability (no DB after load)
- ✅ Rich filtering (by day, type, allergen, category)
- ✅ Shopping list generation (one method call)
- ✅ Allergen detection (across entire plan)

### 🤔 Under Consideration - Side Dishes
**User Request:** "can you add a salad side dish to the honey garlic chicken"

**Current Limitation:** PlannedMeal only supports single recipe (no side dish support)

**Design Options Discussed (2025-10-29):**
- Option A: `side_recipes: List[Recipe]` - Separate list of side recipes (original design in docs)
- Option B: Modify recipe directly - Create combined recipe on-the-fly
- Option C: `side: Optional[Recipe]` - Single side dish field (user's suggestion)
- Option D: Recursive nesting - `side: Optional[PlannedMeal]` (discussed but semantically problematic)
- Option E: `sides: List[Recipe]` - Multiple sides as recipe list (cleanest approach)

**Decision Status:** ⏸️ **DEFERRED** - No decision made yet, exploring options

**Context for Next Session:**
- Design already exists in `docs/design/step4_planned_meal_design.md` (lines 321-346)
- Original decision was "Start with single recipe, add multi-recipe support later if needed"
- User is thinking about whether to use `side` (singular) or `sides` (list)
- Needs discussion on: single vs multiple sides, recursive vs list approach
- See conversation history for full analysis of pros/cons

### 📋 Next Steps
- **Immediate:** Decide on side dish architecture (if implementing)
- Step 9: Update agents to use embedded recipes
- Step 10: Design and document chat interface patterns
- Step 11: Integrate chat with MealPlan objects
- Future: Full enrichment of 492K recipes

## Development Commands

```bash
# Run tests
pytest                              # All tests (77 passing)
pytest tests/unit/                  # Unit tests only
pytest --cov=src --cov-report=html  # With coverage

# Test enhanced data objects
python3 test_enhanced_recipe.py     # Test Recipe with structured ingredients (7 tests)
python3 test_database_enriched.py   # Test DatabaseInterface loading (5 tests)
python3 test_planned_meal.py        # Test PlannedMeal with embedded Recipe (7 tests)
python3 test_meal_plan.py           # Test MealPlan methods (10 tests)
python3 demo_meal_plan_workflow.py  # Full workflow demonstration (11 steps)

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
- `docs/MEAL_PLAN_WORKFLOW_REPORT.md` - **Complete workflow report (50+ pages)**
- `docs/development/CHECKPOINT_RECIPE_ENRICHMENT.md` - Phase 2 enrichment summary
- `docs/development/DEV_DATABASE.md` - Development database guide
- `docs/development/IMPLEMENTATION_STATUS.md` - What's built vs designed
- `docs/development/ROADMAP.md` - Project roadmap and phases
- `docs/design/decisions.md` - Architecture decision records
- `docs/design/step2e_enhanced_recipe_design.md` - Enhanced Recipe design
- `docs/design/step4_planned_meal_design.md` - PlannedMeal with embedded recipes
- `docs/design/step5_meal_plan_design.md` - MealPlan with rich methods

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
