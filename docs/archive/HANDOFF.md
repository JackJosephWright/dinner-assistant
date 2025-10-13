# Meal Planning Assistant - Phase 1 Implementation Specification

## Project Context

The Meal Planning Assistant is a multi-agent system that helps users plan weekly meals, generate shopping lists, and guide cooking. It uses your 60-week meal history to understand preferences and leverages the Food.com dataset (500K recipes) for variety.

**Problem Solved:** Meal planning fatigue, inefficient grocery shopping, and the daily "what's for dinner?" question.

**Phase 1 Scope:** Core functionality - plan meals, generate shopping lists, provide cooking guidance. No UI, no advanced features.

**Technology Stack:**
- **MCP (Model Context Protocol):** Tool server architecture
- **LangGraph:** Agent orchestration
- **SQLite:** Recipe database (Food.com dataset)
- **Python 3.11+:** Primary language

## Technical Foundation

### Architecture Overview
```
User → LangGraph Orchestrator → 3 Specialized Agents → MCP Tool Server → Data
         ↓                         ↓
   [Planning Agent]         [Shopping Agent]      [Cooking Agent]
         ↓                         ↓                      ↓
   [Recipe Search]          [List Generation]      [Instructions]
   [Meal Planning]          [Consolidation]        [Substitutions]
   [Preferences]            [Store Mapping]        [Timers]
```

### File Structure
```
dinner-assistant/
├── HANDOFF.md                    # This document
├── examples/
│   ├── sample_recipes.json       # Test recipes
│   ├── test_meal_plan.json       # Expected output
│   └── test_search_recipes.py    # Test template
├── src/
│   ├── mcp_server/
│   │   ├── __init__.py
│   │   ├── server.py             # MCP server entry
│   │   └── tools/
│   │       ├── planning_tools.py
│   │       ├── shopping_tools.py
│   │       └── cooking_tools.py
│   ├── agents/
│   │   ├── planning_agent.py
│   │   ├── shopping_agent.py
│   │   └── cooking_agent.py
│   └── data/
│       ├── models.py             # Data classes
│       └── database.py           # SQLite interface
└── tests/
```

## Data Model

### Core Entities

#### Recipe (from Food.com dataset)
```python
class Recipe:
    id: str                      # "71247"
    name: str                    # "Cherry Streusel Cobbler"
    description: str             # Full description
    ingredients: List[str]       # ["cherry pie filling", "condensed milk"]
    ingredients_raw: List[str]   # ["2 (21 ounce) cans cherry pie filling"]
    steps: List[str]             # ["Preheat oven...", "Spread cherry..."]
    servings: int                # 6
    serving_size: str            # "1 (347 g)"
    tags: List[str]              # ["60-minutes-or-less", "desserts", "easy"]
    
    # Derived fields
    estimated_time: Optional[int]  # From tags
    cuisine: Optional[str]         # From tags
    difficulty: str                # "easy", "medium", "hard"
```

#### MealPlan
```python
class MealPlan:
    week_of: str                 # "2025-01-20"
    meals: List[PlannedMeal]
    created_at: datetime
    preferences_applied: List[str]

class PlannedMeal:
    date: str                    # "2025-01-20"
    meal_type: str               # "dinner"
    recipe_id: str
    recipe_name: str
    servings: int
    notes: Optional[str]
```

#### GroceryList
```python
class GroceryList:
    week_of: str
    items: List[GroceryItem]
    estimated_total: Optional[float]
    store_sections: Dict[str, List[GroceryItem]]

class GroceryItem:
    name: str                    # "Ground beef"
    quantity: str                # "2 lbs"
    category: str                # "meat"
    recipe_sources: List[str]    # ["Tacos", "Spaghetti"]
    notes: Optional[str]
```

### Database Schema

SQLite with two databases:
1. **recipes.db** - Food.com dataset (read-only)
2. **user_data.db** - Meal plans, preferences, history

## Implementation Scope

### Phase 1 Boundaries

**IN SCOPE:**
- Search recipes by keywords, tags, time
- Generate 7-day meal plans
- Create consolidated shopping lists
- Provide step-by-step cooking instructions
- Basic preference learning from history
- Ingredient substitution suggestions

**OUT OF SCOPE (Phase 2+):**
- User authentication
- Web UI
- Nutritional tracking
- Budget optimization
- Recipe ratings/reviews
- Multi-user support
- External API integrations
- Advanced dietary restrictions

## Agent Specifications

### Planning Agent

**Purpose:** Generate weekly meal plans based on preferences and variety.

**Capabilities:**
- Analyzes 60-week meal history for patterns
- Ensures variety (no recipe repeat within 2 weeks)
- Balances cuisines and cooking complexity
- Adapts to seasonal preferences

**Tools Used:**
- `search_recipes()` - Find recipes
- `get_meal_history()` - Check past meals
- `save_meal_plan()` - Store plans
- `get_user_preferences()` - Load preferences

**Interaction Example:**
```
User: "Plan next week's dinners"
Agent: "I'll create a balanced meal plan for January 20-26. Based on your history, 
        I see you enjoy Italian and Mexican, prefer quick weeknight meals, and 
        like to try new recipes on weekends..."
```

### Shopping Agent

**Purpose:** Generate organized, efficient grocery lists.

**Capabilities:**
- Consolidates ingredients across recipes
- Groups by store sections
- Handles unit conversions
- Identifies pantry staples vs. fresh items

**Tools Used:**
- `get_meal_plan()` - Load week's meals
- `consolidate_ingredients()` - Merge quantities
- `categorize_items()` - Organize by section
- `check_pantry()` - Skip staples

**Interaction Example:**
```
User: "Create shopping list for next week"
Agent: "I've consolidated ingredients for 7 meals. Your list has 24 items 
        organized by store section. I've combined the ground beef for both 
        Tacos and Spaghetti into one 2 lb purchase..."
```

### Cooking Agent

**Purpose:** Guide through recipe execution.

**Capabilities:**
- Provides step-by-step instructions
- Suggests ingredient substitutions
- Offers timing coordination
- Adapts to skill level

**Tools Used:**
- `get_recipe()` - Load full recipe
- `suggest_substitution()` - Alternative ingredients
- `calculate_timing()` - Coordinate steps
- `get_technique_video()` - How-to links

**Interaction Example:**
```
User: "How do I make tonight's salmon?"
Agent: "Let's make the Honey Glazed Salmon (25 min). I'll guide you step-by-step.
        First, preheat your oven to 400°F. While it heats, let's prep the glaze..."
```

## Tool Contracts

### Planning Tools

#### search_recipes(query, filters) → List[Recipe]
Searches Food.com SQLite database.

**Input:**
- query: str (optional) - Keywords
- max_time: int (optional) - Minutes
- tags: List[str] (optional) - Required tags
- exclude_ids: List[str] (optional) - Skip recipes
- limit: int = 20

**Output:**
- recipes: List[{id, name, tags, estimated_time}]

**Example:**
```python
search_recipes("salmon", max_time=30, tags=["healthy"])
→ [{id: "123", name: "Quick Salmon", tags: ["30-minutes-or-less", "healthy"]}]
```

#### get_meal_history(weeks_back) → List[PlannedMeal]
Retrieves past meal plans.

**Input:**
- weeks_back: int = 8

**Output:**
- meals: List[PlannedMeal]

### Shopping Tools

#### consolidate_ingredients(meal_plan_id) → GroceryList
Merges ingredients from week's recipes.

**Input:**
- meal_plan_id: str

**Output:**
- grocery_list: GroceryList with consolidated items

**Key Behavior:**
- Uses LLM to merge similar ingredients
- Converts units where sensible
- Groups by store section

### Cooking Tools

#### get_recipe(recipe_id) → Recipe
Loads complete recipe with instructions.

**Input:**
- recipe_id: str

**Output:**
- recipe: Full Recipe object

## Implementation Order

Build in this sequence for fastest validation:

1. **Data Layer** (Day 1)
   - SQLite setup
   - Data models
   - Load Food.com dataset

2. **MCP Server Scaffold** (Day 1)
   - Basic server.py
   - Tool registration framework

3. **Vertical Slice** (Day 2)
   - Implement `search_recipes()` tool
   - Basic Planning Agent
   - Test end-to-end flow

4. **Complete Planning** (Day 3)
   - Remaining planning tools
   - Full Planning Agent logic

5. **Shopping Features** (Day 4)
   - Shopping tools
   - Shopping Agent
   - Consolidation logic

6. **Cooking Features** (Day 5)
   - Cooking tools
   - Cooking Agent
   - Integration testing

## Testing Strategy

### Approach: Pragmatic Testing
Not full TDD, but test as you build.

### Pattern for Each Tool:
```python
def test_search_recipes_happy_path():
    results = search_recipes("chicken", max_time=30)
    assert len(results) > 0
    assert all(r.estimated_time <= 30 for r in results)

def test_search_recipes_no_results():
    results = search_recipes("impossible_recipe_name_xyz")
    assert results == []
```

### Coverage Goals:
- Every tool: Happy path + one edge case
- Each agent: One complete conversation
- Integration: Full weekly flow

## Quality Standards

### Definition of Done:
- [ ] All Phase 1 tools implemented
- [ ] All 3 agents functional
- [ ] Can complete: plan → shop → cook flow
- [ ] Basic tests pass
- [ ] Code documented
- [ ] No hardcoded test data

### Code Standards:
- Type hints on all functions
- Docstrings for public methods
- Error handling (no crashes)
- Logging for debugging

## Decision-Making Authority

### You MUST Follow:
- 3-agent architecture (Planning/Shopping/Cooking)
- MCP for tools, LangGraph for agents
- Tool contracts as specified
- Data model schemas
- Food.com as recipe source

### You Have Discretion On:
- Helper function organization
- Error message wording
- Internal code structure
- Logging verbosity

### When Tempted to "Improve":
- Not in Phase 1 scope → Don't build it
- Architecture change → Note in QUESTIONS.md
- "Nice to have" → Save for Phase 2

## Getting Started

### Prerequisites:
1. Python 3.11+
2. Food.com dataset (CSV → SQLite)
3. Your meal_history.csv

### First Steps:
```bash
# Setup
git clone [repo]
cd dinner-assistant
pip install -r requirements.txt

# Load data
python scripts/load_recipes.py --input food_com.csv
python scripts/load_history.py --input meal_history.csv

# Run
python src/mcp_server/server.py
```

### Prompting Claude Code:
```
You are implementing Phase 1 of the Meal Planning Assistant based on HANDOFF.md.

Your Task: Build the system exactly as specified. Architecture is finalized - 
your job is excellent execution, not redesign.

Before starting:
1. Read HANDOFF.md completely
2. Ask clarifying questions
3. Confirm understanding

As you work:
- Follow the implementation order
- Test each component
- Stay within Phase 1 scope
- Log improvements in SUGGESTIONS.md

Ready? Begin with step 1 (Data Models).
```

---

## Appendix: Key Design Decisions

### Why MCP + LangGraph?
- MCP: Clean tool/agent separation, future-proof
- LangGraph: Proven agent orchestration, state management

### Why 3 Agents?
- Separation of concerns
- Specialized prompts
- Easier testing/debugging
- Future scalability

### Why SQLite?
- No server required
- Handles 500K recipes easily
- Simple deployment
- Good enough for Phase 1

### Why No Ratings?
- Food.com dataset doesn't include them
- Tag-based scoring works well enough
- Can add in Phase 2 if needed

---

*Document Version: 1.0*
*Last Updated: January 2025*
*Phase: 1 - Core Functionality*