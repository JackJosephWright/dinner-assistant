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

### recipes.db
- **recipes** table: 492,630 recipes from Food.com
- Indexed on: name, tags, minutes, calories
- Fields: id, name, minutes, tags, nutrition, n_steps, ingredients, etc.

### user_data.db
- **meal_history**: 294 historical meals (60 weeks)
- **meal_plans**: Generated meal plans
- **preferences**: User preferences and dietary restrictions
- **grocery_lists**: Shopping lists with store sections

## Current Status (Last Updated: 2025-10-28)

### ✅ Completed
- Day 1-2: Foundation complete
- Recipe database loaded and searchable
- MCP server operational with planning tools
- Planning agent structure implemented
- 77 tests passing (5.30 seconds)
- Natural language recipe scaling feature
- UI simplification (removed redundant Accept button)

### 🚧 In Progress
- Day 3: Completing Planning Agent (LLM integration, preference learning)

### 📋 Next Steps
- Day 4: Shopping Agent implementation
- Day 5: Cooking Agent + full integration

## Development Commands

```bash
# Run tests
pytest                              # All tests
pytest tests/unit/                  # Unit tests only
pytest --cov=src --cov-report=html  # With coverage

# Run application
./run.sh chat                       # Chatbot mode
./run.sh interactive                # Interactive CLI
./run.sh workflow                   # One-shot workflow

# Database setup
python scripts/load_recipes.py      # Load recipe data
python scripts/load_history.py      # Load meal history

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

- `src/data/database.py:45` - DatabaseInterface.search_recipes()
- `src/agents/planning_agent.py:67` - PlanningAgent.create_plan()
- `src/chatbot.py:123` - Main chatbot loop
- `docs/archive/STATUS.md` - Detailed project status
- `docs/archive/PROGRESS.md` - Development progress tracking

## Common Issues

1. **Large database files** - recipes.db is ~1.5GB, git-ignored
2. **API keys** - Required: ANTHROPIC_API_KEY in .env
3. **Import paths** - Use absolute imports: `from src.data import models`
4. **Test data** - Integration tests create temporary databases

## Notes

- Built with TDD (Test-Driven Development)
- Focus on clean architecture and separation of concerns
- Emphasis on type hints and comprehensive docstrings
- Production-ready code quality standards
