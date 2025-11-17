# Complete System Walkthrough

How everything works together in the Meal Planning Assistant.

## Architecture Layers

```
┌─────────────────────────────────────────────────────────────────┐
│  Layer 1: USER INTERFACES                                       │
│  Files: src/chatbot.py, src/interactive.py, src/main.py         │
│  Purpose: Three ways to interact with the system                │
├─────────────────────────────────────────────────────────────────┤
│  Layer 2: AGENTIC AGENTS (LLM-Powered)                         │
│  Files: src/agents/agentic_planning_agent.py                    │
│         src/agents/agentic_shopping_agent.py                    │
│         src/agents/agentic_cooking_agent.py                     │
│  Purpose: AI reasoning and decision-making using LangGraph      │
├─────────────────────────────────────────────────────────────────┤
│  Layer 3: MCP TOOLS (Business Logic)                           │
│  Files: src/mcp_server/tools/planning_tools.py                  │
│         src/mcp_server/tools/shopping_tools.py                  │
│         src/mcp_server/tools/cooking_tools.py                   │
│  Purpose: Reusable business logic, database operations          │
├─────────────────────────────────────────────────────────────────┤
│  Layer 4: DATABASE LAYER                                        │
│  Files: src/data/database.py                                    │
│  Purpose: SQLite operations, CRUD for all entities              │
├─────────────────────────────────────────────────────────────────┤
│  Layer 5: DATA MODELS                                           │
│  Files: src/data/models.py                                      │
│  Purpose: Python dataclasses for type safety                    │
└─────────────────────────────────────────────────────────────────┘
```

## Complete Example: "Plan meals for next week"

### Step 1: User Input (Layer 1)

**File**: `src/chatbot.py`

```python
# User types: "Plan meals for next week"

def run_chatbot():
    # Initialize database and agent
    db = DatabaseInterface(db_dir="data")
    planning_agent = AgenticPlanningAgent(db)
    
    # AI chatbot processes message
    response = client.messages.create(
        model="claude-sonnet-4",
        messages=[{"role": "user", "content": user_message}],
        tools=[...]  # Planning tools available
    )
    
    # Claude decides: "I need to call plan_week()"
    agent_result = planning_agent.plan_week(week_of="2025-10-20", num_days=7)
```

### Step 2: Agent Reasoning (Layer 2)

**File**: `src/agents/agentic_planning_agent.py`

The agent uses **LangGraph** to create a workflow with 3 nodes:

#### Node 1: Analyze History

```python
def _analyze_history_node(state):
    # Get meal history from database
    history = self.db.get_meal_history(weeks_back=8)
    recent = self.db.get_meal_history(weeks_back=2)
    
    # Ask Claude to analyze patterns
    prompt = f"""
    Recent meals: {format_meals(recent)}
    Historical meals: {format_meals(history)}
    
    Analyze preferences, patterns, and suggest variety.
    """
    
    response = self.client.messages.create(
        model="claude-sonnet-4",
        messages=[{"role": "user", "content": prompt}]
    )
    
    # Claude returns analysis like:
    # "User frequently enjoys salmon (5x in 8 weeks), loves Italian 
    #  cuisine (avg 4.5★), needs more variety in proteins"
    
    state["history_summary"] = response.content[0].text
    return state
```

#### Node 2: Search Recipes

```python
def _search_recipes_node(state):
    # Ask Claude what to search for
    prompt = f"""
    Based on this analysis: {state["history_summary"]}
    User needs {state["num_days"]} meals.
    Max weeknight time: 45 min
    
    Provide 5-7 search keywords for diverse recipes.
    """
    
    response = self.client.messages.create(...)
    
    # Claude returns:
    # "salmon | User loves salmon
    #  tofu | Need vegetarian option
    #  chicken | Weeknight staple
    #  pasta | Quick Italian"
    
    # Execute each search
    for keyword in parse_keywords(response):
        recipes = self.db.search_recipes(
            query=keyword,
            max_time=45,
            limit=15
        )
        candidates.extend(recipes)
    
    state["recipe_candidates"] = candidates
    return state
```

#### Node 3: Select Meals

```python
def _select_meals_node(state):
    candidates = state["recipe_candidates"]  # ~50 recipes
    
    # Ask Claude to pick specific meals for each day
    prompt = f"""
    Days: Monday (weeknight), Tuesday (weeknight), ..., Sunday (weekend)
    
    Recipe candidates:
    1. Honey Ginger Chicken (Asian, 45 min, easy)
    2. Pasta Primavera (Italian, 30 min, easy)
    ... (50 more)
    
    Select one recipe for each day ensuring:
    - Good variety (cuisines, proteins)
    - Appropriate for weeknight/weekend
    - No repeats
    
    Format: 
    DAY 1: 5 | Quick salmon, user loves it
    DAY 2: 12 | Different protein, still fast
    """
    
    response = self.client.messages.create(...)
    
    # Parse Claude's selections
    selected_meals = parse_selections(response)
    # [
    #   {"recipe_id": "12345", "recipe_name": "Honey Ginger Chicken"},
    #   {"recipe_id": "12346", "recipe_name": "Pasta Primavera"},
    #   ...
    # ]
    
    state["selected_meals"] = selected_meals
    return state
```

**LangGraph Flow**:
```
analyze_history → search_recipes → select_meals → END
```

### Step 3: Save Plan (Layer 2 → Layer 3 → Layer 4)

**Agent calls Database**:

```python
# In agent (Layer 2)
meal_plan = MealPlan(
    week_of="2025-10-20",
    meals=[PlannedMeal(...), PlannedMeal(...), ...]  # 7 meals
)

plan_id = self.db.save_meal_plan(meal_plan)
```

**Database saves and creates meal events** (Layer 4):

```python
# In database.py
def save_meal_plan(meal_plan):
    # 1. Save to meal_plans table
    cursor.execute("""
        INSERT INTO meal_plans (id, week_of, meals_json, ...)
        VALUES (?, ?, ?, ...)
    """, (...))
    
    return plan_id
```

**Planning Tools auto-create meal_events** (Layer 3):

```python
# In planning_tools.py - TDD Refactored!
def save_meal_plan(week_of, meals, ...):
    # Save the plan
    plan_id = db.save_meal_plan(meal_plan)
    
    # Create learning events for each meal
    for meal_dict in meals:
        # Helper method (extracted during refactoring)
        event = self._create_meal_event_from_plan(meal_dict, plan_id)
        db.add_meal_event(event)
    
    # event = MealEvent(
    #     date="2025-10-20",
    #     day_of_week="Monday",
    #     recipe_id="12345",
    #     recipe_name="Honey Ginger Chicken",
    #     recipe_cuisine="Asian",          # Enriched from recipes.db
    #     recipe_difficulty="easy",        # Enriched from recipes.db
    #     servings_planned=4,
    #     ingredients_snapshot=[...],      # Enriched from recipes.db
    #     meal_plan_id=plan_id,
    #     created_at=now()
    # )
```

### Step 4: Data Persisted (Layer 5)

**Two tables updated**:

```sql
-- meal_plans table
INSERT INTO meal_plans VALUES (
    'mp_2025-10-20_...',
    '2025-10-20',
    '[{"date":"2025-10-20","recipe_id":"12345"...}]'
);

-- meal_events table (7 rows, one per day)
INSERT INTO meal_events VALUES (
    NULL,  -- id (auto-increment)
    '2025-10-20',  -- date
    'Monday',  -- day_of_week
    'dinner',  -- meal_type
    '12345',  -- recipe_id
    'Honey Ginger Chicken',  -- recipe_name
    'Asian',  -- recipe_cuisine (enriched!)
    'easy',  -- recipe_difficulty (enriched!)
    4,  -- servings_planned
    NULL,  -- servings_actual (filled after cooking)
    '["2 lbs chicken", "1/4 cup honey", ...]',  -- ingredients_snapshot
    '{}',  -- modifications (filled after cooking)
    '{}',  -- substitutions (filled after cooking)
    NULL,  -- user_rating (filled after cooking)
    NULL,  -- cooking_time_actual (filled after cooking)
    NULL,  -- notes (filled after cooking)
    NULL,  -- would_make_again (filled after cooking)
    'mp_2025-10-20_...',  -- meal_plan_id
    '2025-10-13T10:30:00'  -- created_at
);
-- ... 6 more rows for other days
```

### Step 5: Learning Loop (Future)

**When user cooks the meal**:

```python
# Cooking agent updates the event
db.update_meal_event(event_id=1, {
    "user_rating": 5,
    "cooking_time_actual": 42,
    "notes": "Kids loved it! Added extra garlic",
    "modifications": {"doubled_garlic": True},
    "would_make_again": True
})
```

**Next time planning**:

```python
# Agent gets preferences
prefs = tools.get_user_preferences()

# Returns enriched data:
{
    "household_size": 4,
    "dietary_restrictions": ["dairy-free"],
    "favorite_cuisines": ["italian", "mexican"],
    
    # LEARNED FROM MEAL_EVENTS:
    "cuisine_stats": {
        "Asian": {"frequency": 16, "avg_rating": 4.8},  # ⬆ Updated!
        "Italian": {"frequency": 15, "avg_rating": 4.5}
    },
    "favorite_recipes": [
        {"recipe_id": "12345", 
         "recipe_name": "Honey Ginger Chicken", 
         "avg_rating": 5.0, 
         "times_cooked": 1}  # ⬅ NEW FAVORITE!
    ]
}

# Agent sees this and suggests more Asian food + brings back favorites
```

## Key Design Patterns

### 1. **Layer Separation**

Each layer has ONE job:
- **UI**: Get input, show output
- **Agents**: AI reasoning and decisions
- **Tools**: Business logic, reusable operations
- **Database**: Data persistence
- **Models**: Type safety, serialization

### 2. **Dependency Injection**

```python
# Database flows down through layers
db = DatabaseInterface(db_dir="data")
tools = PlanningTools(db)  # ← Inject database
agent = AgenticPlanningAgent(db)  # ← Inject database

# Tests can inject mock database!
mock_db = MockDatabase()
tools = PlanningTools(mock_db)
```

### 3. **TDD Refactoring** (planning_tools.py:185-277)

Before refactoring (40+ lines in one method):
```python
for meal_dict in meals:
    try:
        recipe = self.db.get_recipe(meal_dict["recipe_id"])
        meal_date = datetime.fromisoformat(meal_dict["date"])
        day_of_week = meal_date.strftime("%A")
        event = MealEvent(
            date=meal_dict["date"],
            day_of_week=day_of_week,
            recipe_cuisine=recipe.cuisine if recipe else None,
            # ... 10 more parameters
        )
        self.db.add_meal_event(event)
    except Exception as e:
        logger.warning(...)
```

After refactoring (5 lines + extracted helpers):
```python
for meal_dict in meals:
    try:
        event = self._create_meal_event_from_plan(meal_dict, plan_id)
        self.db.add_meal_event(event)
        events_created += 1
    except Exception as e:
        logger.warning(...)

# Helper method (line 147):
def _create_meal_event_from_plan(meal_dict, meal_plan_id):
    recipe = self._get_recipe_safely(meal_dict["recipe_id"])  # ← Helper
    meal_date = datetime.fromisoformat(meal_dict["date"])
    day_of_week = meal_date.strftime("%A")
    
    return MealEvent(
        date=meal_dict["date"],
        day_of_week=day_of_week,
        recipe_cuisine=recipe.cuisine if recipe else None,
        # ... enriched with recipe data
    )
```

**Why this matters**:
- ✅ Single Responsibility Principle
- ✅ Testable in isolation
- ✅ Graceful error handling
- ✅ 77 tests protect against regressions

### 4. **Agentic Pattern** (LLM Reasoning)

**NOT algorithmic**:
```python
# OLD: Hard-coded scoring
def score_recipe(recipe, history):
    score = 0
    if recipe.cuisine in favorite_cuisines:
        score += 10
    if recipe.name not in recent_meals:
        score += 5
    return score
```

**Instead: LLM reasoning**:
```python
# NEW: Ask Claude to reason
prompt = """
Based on this user's history: {history}
And these preferences: {preferences}

Select meals for this week ensuring variety and balance.

REASONING: Explain your choices.
"""

response = client.messages.create(model="claude-sonnet-4", messages=[...])
# Claude returns: "I chose salmon because user loves it (5★), 
#                  but balanced with vegetarian tofu stir fry..."
```

## File Organization

```
src/
├── data/
│   ├── models.py              # Layer 5: Data models
│   └── database.py            # Layer 4: Database interface
│
├── mcp_server/
│   └── tools/
│       ├── planning_tools.py  # Layer 3: Planning business logic
│       ├── shopping_tools.py  # Layer 3: Shopping business logic
│       └── cooking_tools.py   # Layer 3: Cooking business logic
│
├── agents/
│   ├── agentic_planning_agent.py   # Layer 2: AI planning
│   ├── agentic_shopping_agent.py   # Layer 2: AI shopping
│   └── agentic_cooking_agent.py    # Layer 2: AI cooking
│
├── chatbot.py                 # Layer 1: AI chat interface
├── interactive.py             # Layer 1: Command-line interface
├── main.py                    # Layer 1: Workflow mode
└── onboarding.py              # User preference collection

tests/
├── unit/                      # Test Layer 5 & 4
├── integration/               # Test Layer 3 & 2
└── e2e/                       # Test full workflows
```

## Data Flow Summary

```
User Input
    ↓
Chatbot/Interactive (Layer 1)
    ↓
Agentic Agent (Layer 2)  ←─── LangGraph workflow
    │                          1. Analyze history (AI)
    │                          2. Search recipes (AI + DB)
    │                          3. Select meals (AI)
    ↓
MCP Tools (Layer 3)       ←─── save_meal_plan()
    │                          ├─ Create meal events
    │                          └─ Enrich with recipe data
    ↓
Database (Layer 4)        ←─── SQLite operations
    │                          ├─ meal_plans table
    │                          └─ meal_events table
    ↓
Data Models (Layer 5)     ←─── Type-safe objects
    │                          MealPlan, MealEvent
    ↓
SQLite Files
    ├─ recipes.db (1.1GB, 492K recipes)
    └─ user_data.db (your data)
```

## Why This Architecture?

1. **Testability**: Each layer can be tested independently (77 tests passing)
2. **Flexibility**: Swap AI agents without changing tools/database
3. **Reusability**: Tools work with both AI and algorithmic agents
4. **Learning**: meal_events table enables continuous improvement
5. **Type Safety**: Data models prevent bugs at compile time
6. **Maintainability**: Clear separation of concerns

## Key Takeaway

**The meal_events table is the "secret sauce"** that makes this a learning system:

```
Plan Meal → Save to meal_events with recipe details
            ↓
Cook Meal → Update meal_events with rating/feedback
            ↓
Next Plan → Agent reads meal_events statistics
            ↓
Better recommendations based on YOUR preferences!
```

This is why we spent so much time on TDD and refactoring - the learning loop is the core value proposition!

---

**Built with**: Claude AI • LangGraph • SQLite • Python • TDD • 77 Tests
