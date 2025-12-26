# Dinner Assistant - Project Context

## Overview
AI-powered multi-agent meal planning system using MCP (Model Context Protocol) and LangGraph. Helps users plan meals, generate shopping lists, and get cooking guidance based on 492K+ recipes and personal meal history.

## Tech Stack
- **Language**: Python 3.10+
- **AI Framework**: LangGraph (multi-agent orchestration)
- **Protocol**: MCP (Model Context Protocol) for tool servers
- **Database**: SQLite (recipes.db, user_data.db)
- **LLM**: Anthropic Claude (via API)
- **Web Framework**: Flask with SSE (Server-Sent Events)
- **Testing**: pytest (103 passing tests, Playwright for web UI)

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

### ✅ Phase 3: Web UI & SSE Integration - Complete (2025-11-17)
**What's Complete:**
- ✅ **SSE Cross-Tab Synchronization** - Real-time state sync across browser tabs (src/web/app.py:29-64)
  - State broadcasting infrastructure with EventSource
  - Automatic shopping list regeneration on meal plan changes
  - Plan tab updates immediately after meal swap
  - Shop tab auto-reloads when shopping list changes
  - Cook tab uses embedded recipes and SSE updates
  - No manual regeneration needed - always stays current

- ✅ **Parallel LLM Execution** - Plan and Shop LLMs run concurrently
  - Planning LLM broadcasts `meal_plan_changed` immediately
  - Shopping LLM runs in background thread (daemon)
  - Broadcasts `shopping_list_changed` when complete
  - **5-10 second faster** Plan tab response time
  - Auto-regeneration on BOTH meal swap AND new plan creation

- ✅ **Cook Tab 0-Query Architecture** - Embedded recipes eliminate DB queries (2025-11-17)
  - `/cook` route embeds full Recipe objects in current_plan (src/web/app.py:368-438)
  - JavaScript stores embedded recipes (cook.html:152-158)
  - `loadRecipe()` checks embedded data first, API fallback (cook.html:230-280)
  - `updateMealDisplay()` for dynamic SSE updates without reload (cook.html:365-450)
  - SSE listener triggers dynamic update instead of page reload
  - Matches Plan tab architecture pattern

- ✅ **Shop Tab Smart List Loading** - Always shows latest shopping list (2025-11-17)
  - `/shop` route queries for LATEST grocery list by week_of (src/web/app.py:368-409)
  - No longer relies solely on session ID (background thread can't update session)
  - Automatically picks up new shopping list after background regeneration
  - Fixes bug where Shop tab showed old recipes after creating new plan

- ✅ **Flask Web Application** - Full-featured web interface (src/web/app.py)
  - Plan tab: Interactive meal planning with chat interface
  - Shop tab: Organized shopping lists by category, always current
  - Cook tab: Recipe cooking guides with embedded recipes and SSE
  - Session-based state management
  - Progress streaming via SSE

**Test Coverage (2025-11-07):**
- **103 tests passing**, 20 failing, 7 errors
- Legacy pre-Phase 2 tests archived to `tests/legacy/`
- New SSE tests: `tests/web/test_state_sync.py` (11 tests, 10 passing)
- Shopping invalidation tests: `tests/web/test_shopping_invalidation.py` (10 tests, 8 passing)
- Playwright integration tests with webapp-testing skill
- See `tests/TEST_STATUS.md` for full breakdown

**Architecture:**
```
User creates/swaps meal in Plan tab
    ↓
Backend updates meal plan
    ↓
✨ IMMEDIATE: Broadcast meal_plan_changed (Plan tab updates ~5-10s)
    ↓
[Background Daemon Thread - Non-Blocking]
    ↓
Shopping LLM regenerates list (~3-5s parallel)
    ↓
✨ Broadcast shopping_list_changed
    ↓
    ├─ Shop tab: Reloads, fetches LATEST grocery list from DB
    └─ Cook tab: Dynamic update with new meals (no page reload)
```

**Key Files:**
- `src/web/app.py:29-64` - SSE state broadcasting infrastructure
- `src/web/app.py:368-409` - Shop route with smart latest list loading
- `src/web/app.py:392-438` - Cook route with embedded Recipe objects
- `src/web/app.py:501-534` - Background shopping regeneration (/api/plan)
- `src/web/app.py:505-538` - Background shopping regeneration (/api/swap-meal)
- `src/web/app.py:786-829` - Background shopping regeneration (/api/chat)
- `src/web/templates/plan.html:1265-1292` - Plan tab SSE listener
- `src/web/templates/shop.html:381-394` - Shop tab SSE listener & auto-reload
- `src/web/templates/cook.html:152-158` - Embedded recipe storage
- `src/web/templates/cook.html:230-280` - 0-query loadRecipe() with fallback
- `src/web/templates/cook.html:365-450` - Dynamic updateMealDisplay()
- `tests/TEST_STATUS.md` - Complete test suite documentation
- `tests/legacy/README.md` - Archived test documentation
- `docs/development/SESSION_2025_11_17.md` - Today's session notes

**Run Web App:**
```bash
python3 src/web/app.py  # http://localhost:5000
```

### ✅ Phase 5: Menu Generation Latency Optimization - Complete (2025-12-26)
**Problem:** Menu generation was taking 60+ seconds in production for 7-day meal plans due to `ORDER BY RANDOM()` causing full table scans on 492K recipes.

**What's Complete:**
- ✅ **Rowid Pre-Sampling** - Replace ORDER BY RANDOM() with 2-query pattern
  - Fetch matching rowids (fast index scan)
  - Sample in Python with seeded RNG for week-reproducible variety
  - SQLite PRAGMAs for read-only optimization (query_only, cache_size, temp_store)

- ✅ **Normalized recipe_tags Table** - Index-based tag lookups instead of LIKE '%tag%'
  - `recipe_tags(recipe_id, tag)` with 8.3M rows (492K recipes × ~17 avg tags)
  - Smart query ordering: smallest tag result set first + EXISTS clauses
  - Auto-detection: falls back to LIKE queries if table doesn't exist

**Performance Results:**
| Metric | Before | After |
|--------|--------|-------|
| 5-day plan | 60+ sec | **4.7 sec** |
| Single pool query | 1-14 sec | **130-570ms** |
| Improvement | - | **12x faster** |

**Key Files:**
- `src/data/database.py:569-678` - `search_recipes_sampled()` with rowid pre-sampling
- `src/data/database.py:680-781` - `_search_with_recipe_tags()` with smart tag ordering
- `src/chatbot.py:425-490` - Per-day pool building with seeded sampling
- `scripts/create_recipe_tags.py` - Migration script to build normalized table

**Instrumentation:**
- `[POOL]` log lines show per-query timing and method (recipe_tags vs like)
- `[PLAN-TIMING]` log lines show total plan generation breakdown

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
- Add SSE integration to Cook tab (Plan and Shop complete)
- Fix 20 failing tests (performance benchmarks, chatbot cache, e2e workflows)
- Resolve 7 test errors (incremental grocery list, contributions)
- Consider: Side dish support in PlannedMeal
- Future: Full enrichment of 492K recipes

## Development Commands

```bash
# Run tests
pytest                              # All tests (103 passing, 20 failing, 7 errors)
pytest tests/unit/                  # Unit tests only
pytest tests/web/                   # Web UI and SSE tests
pytest --cov=src --cov-report=html  # With coverage

# Test enhanced data objects
pytest tests/unit/test_enhanced_recipe.py     # Recipe with structured ingredients (7 tests)
pytest tests/unit/test_planned_meal.py        # PlannedMeal with embedded Recipe (7 tests)
pytest tests/unit/test_meal_plan.py           # MealPlan methods (10 tests)

# Test SSE and web UI
pytest tests/web/test_state_sync.py           # SSE cross-tab sync (11 tests)
pytest tests/web/test_shopping_invalidation.py # Shopping list invalidation (10 tests)

# Run application
python3 src/web/app.py              # Web UI (http://localhost:5000)
./run.sh chat                       # Chatbot mode (CLI)
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
