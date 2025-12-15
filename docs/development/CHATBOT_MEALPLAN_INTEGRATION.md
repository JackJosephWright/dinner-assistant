# Chatbot → MealPlan → Shop/Cook Integration

> **Created:** 2025-12-15
> **Purpose:** Document the data flow from chatbot through MealPlan to Shop/Cook tabs

## Overview

This document explains how the chatbot integrates with the MealPlan object and how this enables the Shop and Cook tabs to work efficiently with a 0-query architecture.

## High-Level Architecture

```
User Input → Chatbot → plan_meals_smart → MealPlan (with embedded Recipes)
                                              ↓
                              ┌───────────────┼───────────────┐
                              ↓               ↓               ↓
                         Plan Tab        Shop Tab        Cook Tab
                        (SSE sync)     (auto-regen)    (0-query)
```

## Key Data Structures

### MealPlan (src/data/models.py)

```python
@dataclass
class MealPlan:
    week_of: str                           # "2025-01-20"
    meals: List[PlannedMeal]               # List with EMBEDDED recipes
    backup_recipes: Dict[str, List[Recipe]] # For instant swaps

    # 0-query methods (all data embedded):
    def get_all_ingredients() -> List[Ingredient]
    def get_all_allergens() -> Set[str]
    def get_meals_for_day(date) -> List[PlannedMeal]
```

### PlannedMeal

```python
@dataclass
class PlannedMeal:
    date: str                    # "2025-01-20"
    meal_type: str               # "dinner"
    recipe: Recipe               # FULL RECIPE OBJECT (not just ID!)
    servings: int
```

## Why Embedded Recipes Are Critical

### Traditional N+1 Query Problem
```
MealPlan with recipe_ids only:
  → Display Cook tab: 1 + N queries
  → Generate Shopping List: 1 + N queries
```

### Our 0-Query Architecture
```
MealPlan with embedded Recipe objects:
  → Display Cook tab: 1 query (MealPlan), then 0
  → Generate Shopping List: 1 query, then plan.get_all_ingredients()
```

## Data Flow

### 1. Plan Creation

```
User: "Plan meals for the week"
           ↓
chatbot.chat() → Claude API → tool: plan_meals_smart
           ↓
execute_tool("plan_meals_smart"):
  1. db.search_recipes(query="dinner", limit=100)
  2. Filter by allergens
  3. _select_recipes_with_llm() picks 7 varied recipes
  4. Create PlannedMeal objects with EMBEDDED Recipe
  5. Create MealPlan
  6. db.save_meal_plan(plan)
  7. chatbot.last_meal_plan = plan  ← cached in memory
           ↓
IMMEDIATE: Return response, broadcast meal_plan_changed SSE
BACKGROUND: create_shopping_list() → broadcast shopping_list_changed
```

### 2. Shop Tab

```
/shop route:
  1. Get meal_plan_id from session
  2. Query latest grocery_list by week_of
  3. Render (list already consolidated by LLM)

SSE listener:
  - On shopping_list_changed → location.reload()
```

### 3. Cook Tab

```
/cook route:
  1. Load MealPlan (includes embedded recipes)
  2. Embed recipes_json in template
  3. JavaScript: embeddedRecipes[date] → instant display

No API calls needed for recipe display!
```

### 4. Meal Swap

```
User: "Swap Thursday for vegetarian"
           ↓
swap_meal_fast:
  1. Check last_meal_plan.backup_recipes["dinner"]
  2. Filter for "vegetarian" tag
  3. Update in-memory plan
  4. db.swap_meal_in_plan()
           ↓
IMMEDIATE: Response, meal_plan_changed SSE
BACKGROUND: Regenerate shopping list, shopping_list_changed SSE
```

## SSE Events

| Event | Trigger | Effect |
|-------|---------|--------|
| `meal_plan_changed` | Plan created/meal swapped | Plan tab updates |
| `shopping_list_changed` | Shopping list (re)generated | Shop tab reloads |

## Key Files

| File | Purpose |
|------|---------|
| `src/chatbot.py:556-813` | Tool definitions |
| `src/chatbot.py:834-962` | plan_meals_smart execution |
| `src/data/models.py:463-631` | MealPlan class |
| `src/web/app.py:368-438` | shop/cook routes |
| `src/web/app.py:295-306` | SSE broadcast |

## Known Gap: Date-Specific Planning

**Current limitation:**
- "Plan 5 chicken meals" ✓ (category-based)
- "Monday tilapia, Tuesday pasta" ✗ (date-specific)

**Issue:** `plan_meals_smart` does a single broad search, LLM picks for variety. Can't guarantee specific recipes on specific dates.

**Proposed fix:** Add `date_requirements` parameter to `plan_meals_smart`:
```python
plan_meals_smart(
    date_requirements={
        "2025-01-20": "tilapia",      # specific search
        "2025-01-21": "veggie burger",
        "2025-01-22": None            # surprise me
    }
)
```

See plan file for full implementation details.
