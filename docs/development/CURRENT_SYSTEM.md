# Current System Analysis

**Date**: October 13, 2025
**Purpose**: Comprehensive analysis of the Meal Planning Assistant as-built

---

## Executive Summary

We have successfully built a **working, intelligent meal planning system** with:
- **492,630 recipes** from Food.com loaded and searchable
- **294 historical meals** for preference learning
- **3 specialized agents** (Planning, Shopping, Cooking) - each with dual implementations
- **LLM-powered reasoning** via LangGraph workflows
- **Full workflow**: Plan → Shop → Cook → Swap meals
- **Interactive chatbot** with natural language interface

### What Works Well ✅
1. **Agentic architecture** - LLM agents make intelligent decisions
2. **LangGraph workflows** - Clean state management for complex operations
3. **Meal swapping** - Recently added, works great
4. **Database layer** - Solid SQLite foundation with clean models
5. **Recipe search** - Fast, flexible, with multiple filters
6. **Backward compatibility** - Falls back to algorithmic agents without API key

### Integration Issues 🔧
1. **Monolithic chatbot** - All 3 agents bundled into one conversation
2. **Tight coupling** - Agents initialized together in main.py
3. **Session-based context** - No shared state across processes
4. **No separation** - Can't run Planning, Shopping, Cooking independently

---

## System Inventory

### Code Structure (3,972 lines total)

```
src/
├── agents/ (2,624 lines)
│   ├── agentic_planning_agent.py (766 lines) - LLM-powered planning with LangGraph
│   ├── agentic_shopping_agent.py (503 lines) - LLM-powered shopping
│   ├── agentic_cooking_agent.py (429 lines) - LLM-powered cooking
│   ├── enhanced_planning_agent.py (334 lines) - Algorithmic fallback
│   ├── shopping_agent.py (85 lines) - Algorithmic fallback
│   ├── cooking_agent.py (107 lines) - Algorithmic fallback
│   └── planning_agent.py (older version, kept for reference)
│
├── data/ (728 lines)
│   ├── database.py (490 lines) - SQLite interface with CRUD operations
│   └── models.py (238 lines) - Recipe, MealPlan, GroceryList, GroceryItem
│
├── main.py (264 lines) - Orchestrator: initializes all 3 agents together
├── chatbot.py (434 lines) - Unified chat interface for all agents
│
└── mcp_server/ (not actively used in current implementation)
```

### Database Schema

**recipes.db** (1.18 GB, read-only)
- 492,630 recipes with full ingredients, steps, tags
- Indexed on id, name, tags for fast search

**user_data.db** (168 KB)
```sql
meal_plans (id, week_of, created_at, preferences_applied, meals_json)
meal_history (id, date, meal_name, day_of_week, meal_type)
grocery_lists (id, week_of, created_at, estimated_total, items_json)
user_preferences (key, value, updated_at)
```

---

## Component Deep Dive

### 1. Planning Agent (Agentic)

**File**: `src/agents/agentic_planning_agent.py` (766 lines)

**LangGraph Workflow**:
```python
analyze_history → search_recipes → select_meals
```

**Key Methods**:
- `plan_week(week_of, num_days)` - Main entry point
- `swap_meal(meal_plan_id, date, requirements)` - NEW: Swap meals intelligently
- `explain_plan(meal_plan_id)` - LLM-generated explanations
- `_analyze_history_node()` - LLM analyzes user preferences
- `_search_recipes_node()` - LLM decides what to search for
- `_select_meals_node()` - LLM picks specific meals

**State Management**:
```python
class PlanningState(TypedDict):
    week_of: str
    num_days: int
    preferences: Dict[str, Any]
    history_summary: Optional[str]      # LLM analysis
    recipe_candidates: List[Dict]       # Search results
    selected_meals: List[Dict]          # Final picks
    reasoning: str                      # Explanations
    error: Optional[str]
```

**What Makes It Smart**:
- LLM analyzes 60 weeks of meal history
- LLM generates search queries based on patterns
- LLM selects meals with variety reasoning
- Handles swap requests by finding suitable replacements

**Recent Fix** (Oct 13):
- Fixed search query parsing (was failing on markdown formatting)
- Now properly extracts keywords from LLM responses
- Successfully finds 30+ recipe candidates per planning session

### 2. Shopping Agent (Agentic)

**File**: `src/agents/agentic_shopping_agent.py` (503 lines)

**LangGraph Workflow**:
```python
collect_ingredients → consolidate_with_llm → save_list
```

**Key Methods**:
- `create_grocery_list(meal_plan_id)` - Main entry point
- `format_shopping_list(list_id)` - Pretty-printed output
- `_collect_ingredients_node()` - Gathers from all recipes
- `_consolidate_ingredients_node()` - LLM merges quantities
- `_save_list_node()` - Persists to database

**State Management**:
```python
class ShoppingState(TypedDict):
    meal_plan_id: str
    raw_ingredients: List[Dict]         # From recipes
    consolidated_items: List[Dict]      # LLM merged
    grocery_list_id: Optional[str]
    error: Optional[str]
```

**What Makes It Smart**:
- LLM intelligently merges similar ingredients
- Handles different units (cups, tablespoons, etc.)
- Categorizes by store section
- Tracks which recipes need each ingredient

**Example**:
```
Input:
- "2 cups all-purpose flour" (Pancakes)
- "1 cup flour" (Cookies)

LLM Output:
- "3 cups all-purpose flour" (Pancakes, Cookies)
```

### 3. Cooking Agent (Agentic)

**File**: `src/agents/agentic_cooking_agent.py` (429 lines)

**LangGraph Workflow**:
```python
load_recipe → generate_tips → analyze_timing → format_instructions
```

**Key Methods**:
- `get_cooking_guide(recipe_id)` - Main entry point
- `format_cooking_instructions(recipe_id)` - Pretty output
- `_load_recipe_node()` - Fetch from database
- `_generate_tips_node()` - LLM contextual advice
- `_analyze_timing_node()` - LLM breaks down prep vs cook
- `_format_instructions_node()` - Structured output

**State Management**:
```python
class CookingState(TypedDict):
    recipe_id: str
    recipe: Optional[Recipe]
    cooking_tips: List[str]             # LLM tips
    timing_breakdown: Dict              # LLM timing
    formatted_instructions: str
    error: Optional[str]
```

**What Makes It Smart**:
- LLM generates contextual tips based on difficulty
- LLM estimates prep vs cook time from steps
- Provides substitution suggestions
- Formats output conversationally

### 4. Database Interface

**File**: `src/data/database.py` (490 lines)

**Key Operations**:

**Recipe Search**:
- `search_recipes(query, max_time, tags, exclude_ids, limit)` → List[Recipe]
- Full-text search on name/description
- Tag filtering (time, difficulty, cuisine)
- Exclusion list for variety enforcement

**Meal Plans**:
- `save_meal_plan(meal_plan)` → plan_id
- `get_meal_plan(plan_id)` → MealPlan
- `swap_meal_in_plan(plan_id, date, new_recipe_id)` → MealPlan (NEW)
- `get_recent_meal_plans(limit)` → List[MealPlan]

**Grocery Lists**:
- `save_grocery_list(grocery_list)` → list_id
- `get_grocery_list(list_id)` → GroceryList

**Meal History**:
- `get_meal_history(weeks_back)` → List[PlannedMeal]
- `add_meal_to_history(date, meal_name, day_of_week)`

**Preferences**:
- `get_preference(key)` → value
- `set_preference(key, value)`
- `get_all_preferences()` → Dict

**Recent Addition** (Oct 13):
- `swap_meal_in_plan()` - Updates existing meal plan with new recipe

### 5. Main Orchestrator

**File**: `src/main.py` (264 lines)

**Purpose**: Ties everything together

```python
class MealPlanningAssistant:
    def __init__(self, db_dir: str, use_agentic: bool = True):
        self.db = DatabaseInterface(db_dir)

        # Choose agent implementation
        if use_agentic and AGENTIC_AVAILABLE:
            self.planning_agent = AgenticPlanningAgent(self.db)
            self.shopping_agent = AgenticShoppingAgent(self.db)
            self.cooking_agent = AgenticCookingAgent(self.db)
        else:
            # Fallback to algorithmic agents
            self.planning_agent = EnhancedPlanningAgent(self.db)
            self.shopping_agent = ShoppingAgent(self.db)
            self.cooking_agent = CookingAgent(self.db)
```

**Key Methods**:
- `plan_week(week_of, num_days)` → Dict
- `create_shopping_list(meal_plan_id)` → Dict
- `get_cooking_guide(recipe_id)` → Dict
- `complete_workflow(week_of)` → Dict (runs all 3 agents)

**Problem**: All 3 agents initialized together, tightly coupled

### 6. Chatbot Interface

**File**: `src/chatbot.py` (434 lines)

**Purpose**: Natural language interface to all agents

**Architecture**:
```python
class MealPlanningChatbot:
    def __init__(self):
        self.client = Anthropic(api_key)
        self.assistant = MealPlanningAssistant(db_dir="data")
        self.conversation_history = []

        # Session context
        self.current_meal_plan_id = None
        self.current_shopping_list_id = None
```

**Tools Exposed to LLM**:
1. `plan_meals` - Generate meal plan
2. `create_shopping_list` - Make grocery list
3. `search_recipes` - Find recipes
4. `get_cooking_guide` - Cooking instructions
5. `get_meal_history` - Past meals
6. `show_current_plan` - Display plan
7. `show_shopping_list` - Display list
8. `swap_meal` - Replace a meal (NEW)

**Tool Execution Loop**:
```python
while response.stop_reason == "tool_use":
    # Execute tools
    # Send results back to LLM
    # Get next response
```

**Problems**:
1. **Session-based context**: `self.current_meal_plan_id` only lives in this instance
2. **Monolithic**: All tools in one chatbot
3. **No persistence**: Context lost when chatbot restarts

**Recent Addition** (Oct 13):
- `swap_meal` tool with intelligent replacement logic
- Updated system prompt to explain when to use swap

---

## Key Workflows

### 1. Plan Meals Workflow

**User**: "Plan my week starting next Monday"

**Flow**:
```
Chatbot → LLM → plan_meals tool
         ↓
MealPlanningAssistant.plan_week()
         ↓
AgenticPlanningAgent.plan_week()
         ↓
LangGraph: analyze_history → search_recipes → select_meals
         ↓
DatabaseInterface.save_meal_plan()
         ↓
Returns: meal_plan_id + 7 meals
```

**LLM Calls**: 3-4 (history analysis, search planning, meal selection, explanation)

**Duration**: ~15-20 seconds

**Output**: 7-day meal plan with reasoning

### 2. Swap Meal Workflow (NEW)

**User**: "I don't want salmon, can we do shellfish instead?"

**Flow**:
```
Chatbot → LLM → swap_meal tool (date="2025-10-22", requirements="shellfish")
         ↓
AgenticPlanningAgent.swap_meal()
         ↓
LLM: Generate search queries for shellfish
         ↓
DatabaseInterface.search_recipes(query="shrimp", "scallops", etc.)
         ↓
LLM: Pick best replacement
         ↓
DatabaseInterface.swap_meal_in_plan()
         ↓
Returns: old_recipe, new_recipe, reason
```

**LLM Calls**: 2 (search planning, selection)

**Duration**: ~8-10 seconds

**Output**: Updated meal plan with reasoning

### 3. Shopping List Workflow

**User**: "Create shopping list"

**Flow**:
```
Chatbot → LLM → create_shopping_list tool
         ↓
MealPlanningAssistant.create_shopping_list(meal_plan_id)
         ↓
AgenticShoppingAgent.create_grocery_list()
         ↓
LangGraph: collect_ingredients → consolidate_with_llm → save_list
         ↓
DatabaseInterface.save_grocery_list()
         ↓
Returns: grocery_list_id + item count
```

**LLM Calls**: 1 (ingredient consolidation)

**Duration**: ~5-8 seconds

**Output**: Organized shopping list by store section

### 4. Cooking Guide Workflow

**User**: "How do I cook tonight's meal?"

**Flow**:
```
Chatbot → LLM → get_cooking_guide tool (recipe_id)
         ↓
MealPlanningAssistant.get_cooking_guide()
         ↓
AgenticCookingAgent.get_cooking_guide()
         ↓
LangGraph: load_recipe → generate_tips → analyze_timing → format
         ↓
Returns: formatted instructions with tips
```

**LLM Calls**: 2 (tips, timing)

**Duration**: ~5-7 seconds

**Output**: Step-by-step instructions with contextual advice

---

## Integration Architecture

### Current: Monolithic Chatbot

```
┌─────────────────────────────────────────┐
│         MealPlanningChatbot             │
│  (single instance, session context)     │
│                                         │
│  current_meal_plan_id                  │
│  current_shopping_list_id              │
│                                         │
│  ┌───────────────────────────────────┐ │
│  │   MealPlanningAssistant           │ │
│  │   (all 3 agents initialized)      │ │
│  │                                   │ │
│  │   planning_agent  ────┐          │ │
│  │   shopping_agent  ────┼──→ db    │ │
│  │   cooking_agent   ────┘          │ │
│  └───────────────────────────────────┘ │
└─────────────────────────────────────────┘
```

**Characteristics**:
- ✅ Simple to use (one conversation)
- ✅ Context flows naturally
- ❌ Can't run agents separately
- ❌ Context tied to session
- ❌ No parallel operations

### What's Needed for Separate Tabs

```
┌──────────────┐  ┌──────────────┐  ┌──────────────┐
│  Planning    │  │  Shopping    │  │  Cooking     │
│     Tab      │  │     Tab      │  │     Tab      │
└──────┬───────┘  └──────┬───────┘  └──────┬───────┘
       │                 │                 │
       ├─────────────────┴─────────────────┤
       │                                   │
┌──────▼───────────────────────────────────▼──────┐
│          Shared Context Manager                 │
│   (database-backed session state)               │
│                                                  │
│   current_meal_plan_id                          │
│   current_shopping_list_id                      │
│   user_preferences                              │
└──────┬───────────────────┬───────────────┬──────┘
       │                   │               │
┌──────▼──────┐  ┌─────────▼──────┐  ┌────▼──────┐
│  Planning   │  │   Shopping     │  │  Cooking  │
│   Agent     │  │     Agent      │  │   Agent   │
└──────┬──────┘  └─────────┬──────┘  └────┬──────┘
       │                   │               │
       └───────────────────┴───────────────┘
                      │
                ┌─────▼──────┐
                │  Database  │
                └────────────┘
```

**Requirements**:
- ✅ Agents run independently
- ✅ Context persisted in database
- ✅ Each tab can read/write shared state
- ✅ Parallel operations possible
- ✅ Tabs can coordinate (e.g., Shopping sees Planning's output)

---

## Strengths of Current System

### 1. Agentic Intelligence ⭐
- LLM reasoning throughout (not just wrapper)
- Agents explain their decisions
- True multi-agent system with LangGraph

### 2. Clean Architecture 🏗️
- Well-separated concerns (agents, database, models)
- Type hints throughout
- Comprehensive docstrings
- Good error handling

### 3. Powerful Features 🚀
- Recipe search with multiple filters
- Intelligent meal swapping (just added!)
- LLM-powered ingredient consolidation
- Preference learning from history
- Variety enforcement

### 4. Backward Compatibility 🔄
- Falls back to algorithmic agents without API key
- Both implementations maintained
- Graceful degradation

### 5. Solid Data Layer 💾
- 492K recipes searchable
- Fast SQLite queries (<100ms)
- Clean data models with serialization
- Good schema design

---

## Pain Points & Refactoring Needs

### 1. Tight Coupling 🔗

**Problem**: All agents initialized together in `main.py`

```python
# main.py - Can't use agents separately
class MealPlanningAssistant:
    def __init__(self, db_dir, use_agentic=True):
        self.planning_agent = AgenticPlanningAgent(self.db)
        self.shopping_agent = AgenticShoppingAgent(self.db)
        self.cooking_agent = AgenticCookingAgent(self.db)
```

**Impact**:
- Can't run Planning agent without initializing Shopping & Cooking
- Each tab would create all 3 agents (wasteful)
- No way to have separate Planning-only interface

### 2. Session-Based Context 📝

**Problem**: Context stored in chatbot instance

```python
# chatbot.py
class MealPlanningChatbot:
    def __init__(self):
        self.current_meal_plan_id = None
        self.current_shopping_list_id = None
```

**Impact**:
- Context lost when chatbot restarts
- Can't share context between tabs
- No way for Shopping tab to see Planning tab's meal plan

### 3. Monolithic Interface 🎭

**Problem**: One chatbot handles all 3 agents

```python
# All 8 tools exposed in single interface
tools = [
    "plan_meals",
    "create_shopping_list",
    "search_recipes",
    "get_cooking_guide",
    "get_meal_history",
    "show_current_plan",
    "show_shopping_list",
    "swap_meal"
]
```

**Impact**:
- Can't create Planning-only chatbot
- All tools always available (confusing scope)
- Can't specialize prompts per agent

### 4. No Service Layer 🌐

**Problem**: No API or service abstraction

**Impact**:
- Can't build web UI easily
- Can't call agents from separate processes
- Would need to duplicate orchestration code

---

## What Needs to Change

### Required for Separate Tabs

1. **Decouple Agent Initialization**
   - Each agent should be independently instantiable
   - Remove `MealPlanningAssistant` wrapper (or make it optional)

2. **Shared Context Manager**
   - Store context in database (not session)
   - Make context accessible across processes
   - Track: current_meal_plan_id, current_shopping_list_id, session_id

3. **Individual Agent Interfaces**
   - `PlanningChatbot` - Only planning tools
   - `ShoppingChatbot` - Only shopping tools
   - `CookingChatbot` - Only cooking tools
   - Each reads/writes shared context

4. **Optional: Service Layer**
   - REST API endpoints for each agent
   - Enables web UI in future
   - Clean separation for deployment

---

## Next Steps

### Immediate (For Separate Tabs)

1. **Design shared context schema**
   - What state needs sharing?
   - How to handle sessions?
   - Database table design

2. **Create individual agent runners**
   - `src/planning_app.py`
   - `src/shopping_app.py`
   - `src/cooking_app.py`

3. **Refactor context management**
   - Extract from chatbot instance
   - Make database-backed
   - Add session support

### Future Enhancements

- Web UI with tabs (Flask + Jinja2)
- Multi-user support
- Advanced preferences
- Meal plan history/favorites
- Recipe recommendations

---

## Summary

We've built a **robust, intelligent meal planning system** that works well. The core functionality is solid:
- ✅ LLM-powered agents with reasoning
- ✅ LangGraph workflows
- ✅ Full plan → shop → cook flow
- ✅ Meal swapping
- ✅ 492K recipes searchable

**The integration needs refactoring** to support separate tabs:
- 🔧 Decouple agent initialization
- 🔧 Database-backed shared context
- 🔧 Individual agent interfaces
- 🔧 Optional service layer

**The good news**: The hard work is done. The agents are intelligent and work well. We just need to change how they're wired together, not rebuild them.

---

*Analysis completed: October 13, 2025*
*Total system: 3,972 lines of well-structured code*
*Status: Working system, ready for refactoring*
