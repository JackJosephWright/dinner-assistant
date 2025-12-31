# Dinner Assistant - System Design

## Architecture Overview

```
┌─────────────────────────────────────────────────────────────────────┐
│                           User Interface                             │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐            │
│  │   Plan   │  │   Shop   │  │   Cook   │  │   Chat   │            │
│  │   Tab    │  │   Tab    │  │   Tab    │  │ Interface│            │
│  └────┬─────┘  └────┬─────┘  └────┬─────┘  └────┬─────┘            │
└───────┼─────────────┼─────────────┼─────────────┼───────────────────┘
        │             │             │             │
        └─────────────┴─────────────┴─────────────┘
                              │
                    ┌─────────▼─────────┐
                    │   Flask Server    │
                    │  (src/web/app.py) │
                    │    35 routes      │
                    └─────────┬─────────┘
                              │
        ┌─────────────────────┼─────────────────────┐
        │                     │                     │
┌───────▼───────┐   ┌─────────▼─────────┐   ┌──────▼──────┐
│   Chatbot     │   │   MealPlanning    │   │    SSE      │
│ (chatbot.py)  │   │    Assistant      │   │ Broadcast   │
│  Tool-based   │   │   (main.py)       │   │  System     │
└───────┬───────┘   └─────────┬─────────┘   └─────────────┘
        │                     │
        │           ┌─────────┼─────────┐
        │           │         │         │
        │    ┌──────▼───┐ ┌───▼────┐ ┌──▼─────┐
        │    │ Planning │ │Shopping│ │Cooking │
        │    │  Agent   │ │ Agent  │ │ Agent  │
        │    │(LangGraph)│ │        │ │        │
        │    └──────┬───┘ └───┬────┘ └──┬─────┘
        │           │         │         │
        └───────────┴─────────┴─────────┘
                              │
                    ┌─────────▼─────────┐
                    │  DatabaseInterface │
                    │ (data/database.py) │
                    └─────────┬─────────┘
                              │
              ┌───────────────┼───────────────┐
              │               │               │
       ┌──────▼──────┐ ┌──────▼──────┐ ┌──────▼──────┐
       │ recipes.db  │ │user_data.db │ │  Snapshots  │
       │  (5K/492K)  │ │  (users,    │ │   (JSON)    │
       │   recipes   │ │  history)   │ │    SOT      │
       └─────────────┘ └─────────────┘ └─────────────┘
```

## Core Invariants

### 1. Snapshot-Centric State Model

The `meal_plan_snapshots` table is the **source of truth** for all meal plan state.

```
Snapshot Structure:
{
  "id": "mp_2025-01-06_1704567890",
  "user_id": 1,
  "week_of": "2025-01-06",
  "planned_meals": [
    {
      "date": "2025-01-06",
      "recipe": { /* full recipe object embedded */ },
      "variant": { /* optional: modification patches */ }
    }
  ],
  "grocery_list": { /* consolidated shopping list */ },
  "backup_recipes": [ /* 20 alternatives for instant swap */ ],
  "created_at": "2025-01-01T12:00:00",
  "updated_at": "2025-01-01T12:05:00"
}
```

**Why snapshots:**
- Single query loads entire meal plan state
- Embedded recipes eliminate N+1 queries
- Enables instant swap modal (backup recipes pre-loaded)
- Reproducible state for debugging

### 2. Zero-Query UX After Load

| Operation | Queries | Latency |
|-----------|---------|---------|
| Initial page load | 1 | ~50ms |
| View recipe details | 0 | <1ms |
| Open swap modal | 0 | <1ms |
| Check allergens | 0 | <1ms |

All subsequent operations work on embedded data - no database round-trips.

### 3. Base Recipes Are Immutable

Recipes in `recipes.db` are **never mutated**. All modifications are tracked as variants:

```python
# Bad: Direct mutation (forbidden)
recipe.ingredients[0].quantity = "2 cups"

# Good: Variant with patches
variant = {
    "base_recipe_id": 12345,
    "patches": [
        {"op": "replace", "path": "/ingredients/0/quantity", "value": "2 cups"}
    ],
    "compiled_recipe": { /* result of applying patches */ }
}
```

**Why immutability:**
- Original recipe always recoverable
- Patches are auditable
- Multiple users can have different variants
- LLM suggestions don't corrupt source data

### 4. LLM Boundaries

LLMs are used at specific, controlled points:

| Stage | Model | Purpose | Fallback |
|-------|-------|---------|----------|
| Recipe Selection | Claude Sonnet | Rank candidates for meal plan | Random selection |
| Swap Matching | Claude Haiku | Find semantically similar recipes | Keyword match |
| Cooking Guidance | Claude Sonnet | Generate step-by-step instructions | Raw recipe steps |
| Chat Interface | Claude Sonnet | Natural language interaction | Error message |

**LLM boundaries enforced by:**
- LLMs receive candidate pools, not raw database access
- LLMs return selections/patches, never execute mutations directly
- All LLM outputs validated before persistence

## Data Flow

### Meal Plan Creation

```
User: "Plan 5 Italian dinners"
         │
         ▼
┌─────────────────────────────┐
│ 1. Parse Request            │
│    - num_days: 5            │
│    - cuisine: "italian"     │
│    - allergens: []          │
└──────────────┬──────────────┘
               │
               ▼
┌─────────────────────────────┐
│ 2. Build Candidate Pools    │
│    - 50 recipes per day     │
│    - Pre-filtered by        │
│      cuisine, time, etc.    │
└──────────────┬──────────────┘
               │
               ▼
┌─────────────────────────────┐
│ 3. LLM Selection (Sonnet)   │
│    - Receives 250 candidates│
│    - Returns 5 selections   │
│    - Includes reasoning     │
└──────────────┬──────────────┘
               │
               ▼
┌─────────────────────────────┐
│ 4. Validate & Persist       │
│    - Check selections valid │
│    - Create snapshot        │
│    - Cache backup recipes   │
└──────────────┬──────────────┘
               │
               ▼
┌─────────────────────────────┐
│ 5. Broadcast State Change   │
│    - SSE: meal_plan_changed │
│    - All tabs update        │
└─────────────────────────────┘
```

### Meal Swap Flow

```
User clicks "Swap" on Tuesday's meal
         │
         ▼
┌─────────────────────────────┐
│ 1. Load Backup Recipes      │
│    (Already in snapshot -   │
│     zero queries)           │
└──────────────┬──────────────┘
               │
               ▼
┌─────────────────────────────┐
│ 2. Display Swap Modal       │
│    - 20 pre-loaded options  │
│    - Instant render         │
└──────────────┬──────────────┘
               │
               ▼
User selects "Chicken Parmesan"
               │
               ▼
┌─────────────────────────────┐
│ 3. Update Snapshot          │
│    - Replace meal in array  │
│    - Single DB write        │
└──────────────┬──────────────┘
               │
               ▼
┌─────────────────────────────┐
│ 4. Regenerate Shopping List │
│    (Background thread)      │
└──────────────┬──────────────┘
               │
               ▼
┌─────────────────────────────┐
│ 5. Broadcast Changes        │
│    - meal_plan_changed      │
│    - shopping_list_changed  │
└─────────────────────────────┘
```

## Key Components

### Flask Server (`src/web/app.py`)

| Routes | Purpose |
|--------|---------|
| `/plan`, `/shop`, `/cook` | Page rendering with embedded data |
| `/api/plan`, `/api/swap-meal-fast` | Meal plan mutations |
| `/api/chat` | Natural language interface |
| `/api/state-stream` | SSE for cross-tab sync |
| `/api/progress-stream` | SSE for operation progress |

### Chatbot (`src/chatbot.py` + `src/chatbot_modules/`)

```
src/chatbot.py (359 lines)
    └── MealPlanningChatbot class
        ├── Tool dispatch
        ├── Conversation history
        └── State management

src/chatbot_modules/
    ├── pool_builder.py      # Candidate pool construction
    ├── recipe_selector.py   # LLM-based selection
    ├── swap_matcher.py      # Semantic swap matching
    ├── tools_config.py      # Tool schemas + system prompt
    ├── tool_registry.py     # Tool name → handler mapping
    └── tool_handlers.py     # 17 tool implementations
```

### Agents (`src/agents/`)

| Agent | Framework | Purpose |
|-------|-----------|---------|
| `agentic_planning_agent.py` | LangGraph | Multi-step meal planning |
| `agentic_shopping_agent.py` | Direct | Shopping list generation |
| `agentic_cooking_agent.py` | Direct | Cooking guidance |

### Database (`src/data/`)

| File | Purpose |
|------|---------|
| `database.py` | DatabaseInterface with all queries |
| `models.py` | Recipe, MealPlan, PlannedMeal, GroceryList dataclasses |

## Non-Goals

These are **explicit non-goals** - not "future features":

### 1. Real-Time Collaborative Editing
Single-user system by design. SSE sync is for same-user cross-tab, not multi-user.

### 2. Recipe Generation by LLM
LLMs **suggest** from existing recipes or **patch** existing recipes. They never generate new recipe content. This ensures:
- Reproducibility (same recipe ID = same content)
- Testability (can verify against known recipes)
- Auditability (changes tracked as patches)

### 3. Nutrition Accuracy Guarantees
Nutrition data is display-only, sourced from recipe metadata. Not validated for medical accuracy. Users with dietary medical needs should consult professionals.

### 4. Offline-First PWA
Architecture assumes server connectivity. Local storage is for performance caching, not offline operation.

### 5. Multi-Database Support
SQLite only. No abstraction layer for PostgreSQL/MySQL. Simplicity over flexibility.

## Failure Modes

| Failure | Detection | Recovery |
|---------|-----------|----------|
| API key missing | Startup check | Graceful degradation to non-agentic mode |
| Empty candidate pool | Pool size check | Retry with relaxed constraints |
| LLM timeout | 30s timeout | Return cached/fallback response |
| Invalid LLM response | JSON schema validation | Reject, keep current state |
| SSE disconnect | Client heartbeat | Auto-reconnect with exponential backoff |
| Snapshot corruption | JSON parse error | Load from legacy tables (deprecated) |

## Performance Characteristics

| Metric | Target | Actual |
|--------|--------|--------|
| Plan page load | <200ms | ~50ms |
| Meal plan creation | <30s | 15-25s |
| Swap modal open | <50ms | <10ms |
| Shopping list regen | <10s | 3-5s |
| Recipe search | <500ms | ~200ms |

## Security Considerations

1. **Authentication**: Session-based with password hashing (werkzeug)
2. **API Key**: Server-side only, never exposed to client
3. **Input Validation**: All user inputs sanitized before DB queries
4. **LLM Injection**: User messages prefixed with context, not trusted as instructions

## File Reference

| File | Lines | Purpose |
|------|-------|---------|
| `src/web/app.py` | 2,162 | Flask server, routes, SSE |
| `src/chatbot.py` | 359 | Chat interface orchestration |
| `src/chatbot_modules/tool_handlers.py` | 30,819 | Tool implementations |
| `src/data/database.py` | 2,085 | Database interface |
| `src/data/models.py` | 1,265 | Data classes |
| `src/agents/agentic_planning_agent.py` | 31,649 | LangGraph planning |

## Appendix: Database Schema

### Primary Tables

```sql
-- Source of truth for meal plans
CREATE TABLE meal_plan_snapshots (
    id TEXT PRIMARY KEY,           -- "mp_2025-01-06_1704567890"
    user_id INTEGER NOT NULL,
    week_of TEXT NOT NULL,         -- "2025-01-06"
    version INTEGER DEFAULT 1,
    snapshot_json TEXT NOT NULL,   -- Full state as JSON
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

-- Recipe database (read-only in production)
CREATE TABLE recipes (
    id INTEGER PRIMARY KEY,
    name TEXT NOT NULL,
    description TEXT,
    ingredients TEXT,              -- JSON array
    ingredients_structured TEXT,   -- Parsed ingredients
    steps TEXT,                    -- JSON array
    estimated_time INTEGER,
    cuisine TEXT,
    tags TEXT,                     -- JSON array
    difficulty TEXT
);

-- User authentication
CREATE TABLE users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    username TEXT UNIQUE NOT NULL,
    password_hash TEXT NOT NULL,
    created_at TEXT NOT NULL
);
```

### Legacy Tables (Deprecated)

These tables exist for historical compatibility but are no longer the source of truth:

- `meal_plans` - Superseded by snapshots
- `grocery_lists` - Embedded in snapshots
- `meal_history` - Event log, not primary state

---

*Last updated: 2025-12-31*
*Document version: 1.0*
