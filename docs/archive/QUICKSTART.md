# Quick Start Guide

## What You Have Now

A working meal planning system foundation with:
- 492K+ recipes from Food.com in SQLite
- Your 60-week meal history loaded
- Recipe search engine (by keyword, time, tags)
- MCP server with planning tools
- Basic planning agent structure

## Verify Everything Works

```bash
# Test the vertical slice
python tests/test_vertical_slice.py
```

You should see:
```
✓ ALL TESTS PASSED!
```

## Try Recipe Search

Create a file `try_search.py`:

```python
from src.data.database import DatabaseInterface

db = DatabaseInterface(db_dir="data")

# Find quick salmon recipes
recipes = db.search_recipes(
    query="salmon",
    max_time=30,
    limit=5
)

print("Quick Salmon Recipes:")
for recipe in recipes:
    print(f"\n{recipe.name}")
    print(f"  Time: {recipe.estimated_time} min")
    print(f"  Servings: {recipe.servings}")
    print(f"  Difficulty: {recipe.difficulty}")
    print(f"  Ingredients: {len(recipe.ingredients)} items")
```

Run it:
```bash
python try_search.py
```

## Check Your Meal History

```python
from src.data.database import DatabaseInterface

db = DatabaseInterface(db_dir="data")

history = db.get_meal_history(weeks_back=4)

print(f"You've had {len(history)} meals in the last 4 weeks:")
for meal in history[:20]:
    print(f"  - {meal.recipe_name}")
```

## Project Status

### ✓ Complete (Day 1-2)
- Database layer
- Recipe search
- Data loading scripts
- MCP server scaffold
- Basic planning agent
- Tests passing

### → Next (Day 3)
- Enhanced planning agent with full LLM
- Preference learning
- Complete meal plan generation

### → After That (Day 4-5)
- Shopping agent (grocery lists)
- Cooking agent (step-by-step guidance)
- Full integration testing

## Directory Tour

```
dinner-assistant/
├── HANDOFF.md              # Full Phase 1 spec (read this!)
├── README.md               # Project overview
├── PROGRESS.md             # Detailed progress tracking
├── QUICKSTART.md           # This file
│
├── data/                   # Your databases
│   ├── recipes.db         # 492K recipes (1.5 GB)
│   └── user_data.db       # Your history & preferences
│
├── src/
│   ├── data/
│   │   ├── models.py      # Data classes
│   │   └── database.py    # SQLite interface
│   │
│   ├── mcp_server/
│   │   ├── server.py      # MCP server
│   │   └── tools/
│   │       └── planning_tools.py
│   │
│   └── agents/
│       └── planning_agent.py
│
├── scripts/
│   ├── load_recipes.py    # CSV → SQLite loader
│   └── load_history.py    # History loader
│
└── tests/
    └── test_vertical_slice.py
```

## Key Files to Read

1. **HANDOFF.md** - The master specification
2. **src/data/models.py** - Understand the data structures
3. **src/data/database.py** - See how data access works
4. **src/mcp_server/tools/planning_tools.py** - Available tools

## Example: Search Multiple Criteria

```python
from src.data.database import DatabaseInterface

db = DatabaseInterface(db_dir="data")

# Quick, easy, vegetarian recipes
recipes = db.search_recipes(
    tags=["easy", "vegetarian"],
    max_time=30,
    limit=10
)

print(f"Found {len(recipes)} recipes:")
for r in recipes:
    print(f"  • {r.name} ({r.estimated_time}min)")
```

## What's Working

### Recipe Search
- ✓ Keyword search (name, description)
- ✓ Time filtering (15, 30, 60 min, etc.)
- ✓ Tag filtering (easy, vegetarian, etc.)
- ✓ Exclude recent recipes
- ✓ Full recipe details (ingredients, steps)

### Meal History
- ✓ 294 historical meals loaded
- ✓ Retrievable by weeks back
- ✓ Includes dates and meal names

### Preferences
- ✓ Key-value preference storage
- ✓ Get/set operations
- ✓ Persistent across sessions

## Common Issues

### Import Errors
If you get import errors, make sure to run from the project root:
```bash
cd /home/jack_wright/dinner-assistant
python tests/test_vertical_slice.py
```

### Database Not Found
The databases should be in `data/`:
```bash
ls -lh data/
# Should show:
# recipes.db (~1.5 GB)
# user_data.db (~100 KB)
```

If missing, reload:
```bash
python scripts/load_recipes.py --input food_com_recipes.csv
python scripts/load_history.py --input meal_history.csv
```

## Next Steps for Development

When you're ready to continue (Day 3):

1. Read the Planning Agent code: `src/agents/planning_agent.py`
2. Review the tool definitions: `src/mcp_server/tools/planning_tools.py`
3. Start enhancing the planning agent with full LLM integration
4. Test meal plan generation end-to-end

See PROGRESS.md for detailed next steps.

## Questions?

- Check HANDOFF.md for specifications
- Read code docstrings for implementation details
- Run tests to verify functionality
- Review PROGRESS.md for what's done vs. what's next

---

**You're on track!** The foundation is solid and the vertical slice proves the core functionality works.
