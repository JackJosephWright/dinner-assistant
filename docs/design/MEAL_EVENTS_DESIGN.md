# Meal Events System Design

**Purpose**: Rich data capture for intelligent meal planning, shopping, and cooking

**Date**: October 13, 2025

---

## Overview

Replace simple meal history with rich event tracking that captures:
- Full recipe information (id, name, ingredients)
- User modifications and preferences
- Ratings and feedback
- Actual servings and portions used
- Cooking notes and substitutions

This enables all three agents (Planning, Shopping, Cooking) to learn from actual user behavior.

---

## Database Schema

### 1. meal_events Table

**Purpose**: Rich capture of every meal planned/cooked

```sql
CREATE TABLE meal_events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,

    -- When
    date TEXT NOT NULL,                    -- "2025-10-20"
    day_of_week TEXT NOT NULL,             -- "Monday"
    meal_type TEXT DEFAULT 'dinner',       -- "dinner", "lunch", "breakfast"

    -- What (Recipe)
    recipe_id TEXT NOT NULL,               -- Link to recipes.db
    recipe_name TEXT NOT NULL,
    recipe_cuisine TEXT,                   -- "Italian", "Mexican", etc.
    recipe_difficulty TEXT,                -- "easy", "medium", "hard"

    -- How (Execution)
    servings_planned INTEGER,              -- What recipe called for
    servings_actual INTEGER,               -- What user actually made
    ingredients_snapshot TEXT,             -- JSON: ingredients used
    modifications TEXT,                    -- JSON: what user changed
    substitutions TEXT,                    -- JSON: ingredient swaps

    -- Feedback
    user_rating INTEGER,                   -- 1-5 stars
    cooking_time_actual INTEGER,           -- Actual minutes spent
    notes TEXT,                            -- Free-form notes
    would_make_again BOOLEAN,              -- Yes/No

    -- Metadata
    meal_plan_id TEXT,                     -- Link to meal plan if from one
    created_at TEXT NOT NULL,              -- Timestamp

    FOREIGN KEY (meal_plan_id) REFERENCES meal_plans(id)
);

CREATE INDEX idx_meal_events_date ON meal_events(date);
CREATE INDEX idx_meal_events_recipe ON meal_events(recipe_id);
CREATE INDEX idx_meal_events_plan ON meal_events(meal_plan_id);
```

**Example Record**:
```json
{
  "id": 42,
  "date": "2025-10-20",
  "day_of_week": "Monday",
  "meal_type": "dinner",
  "recipe_id": "12345",
  "recipe_name": "Honey Ginger Chicken Stir-Fry",
  "recipe_cuisine": "Asian",
  "recipe_difficulty": "easy",
  "servings_planned": 4,
  "servings_actual": 6,
  "ingredients_snapshot": [
    "2 lbs chicken breast",
    "3 tbsp honey",
    "2 tbsp fresh ginger",
    "2 cups bok choy"
  ],
  "modifications": {
    "doubled_garlic": true,
    "added_vegetables": ["bok choy", "snap peas"]
  },
  "substitutions": {
    "soy_sauce": "tamari (gluten-free)"
  },
  "user_rating": 5,
  "cooking_time_actual": 35,
  "notes": "Kids loved this! Will make again next week.",
  "would_make_again": true,
  "meal_plan_id": "mp_2025-10-20_123456",
  "created_at": "2025-10-20T18:30:00"
}
```

### 2. user_profile Table

**Purpose**: Store onboarding preferences and constraints

```sql
CREATE TABLE user_profile (
    id INTEGER PRIMARY KEY DEFAULT 1,     -- Single row

    -- Household
    household_size INTEGER DEFAULT 4,
    cooking_for TEXT,                     -- JSON: ["adults": 2, "kids": 2]

    -- Dietary
    dietary_restrictions TEXT,            -- JSON: ["dairy-free", "gluten-free"]
    allergens TEXT,                       -- JSON: ["peanuts", "shellfish"]

    -- Preferences
    favorite_cuisines TEXT,               -- JSON: ["italian", "mexican", "thai"]
    disliked_ingredients TEXT,            -- JSON: ["olives", "anchovies"]
    preferred_proteins TEXT,              -- JSON: ["chicken", "fish", "tofu"]
    spice_tolerance TEXT DEFAULT 'medium', -- "mild", "medium", "spicy"

    -- Constraints
    max_weeknight_cooking_time INTEGER DEFAULT 45,  -- Minutes
    max_weekend_cooking_time INTEGER DEFAULT 90,
    budget_per_week REAL,                 -- Optional budget constraint

    -- Goals
    variety_preference TEXT DEFAULT 'high',  -- "low", "medium", "high"
    health_focus TEXT,                    -- "balanced", "low-carb", "vegetarian", etc.

    -- Metadata
    onboarding_completed BOOLEAN DEFAULT FALSE,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,

    CHECK (id = 1)  -- Enforce single row
);
```

**Example Record**:
```json
{
  "id": 1,
  "household_size": 4,
  "cooking_for": {"adults": 2, "kids": 2},
  "dietary_restrictions": ["dairy-free"],
  "allergens": ["peanuts"],
  "favorite_cuisines": ["italian", "mexican", "thai", "american"],
  "disliked_ingredients": ["olives", "anchovies", "cilantro"],
  "preferred_proteins": ["chicken", "salmon", "ground beef"],
  "spice_tolerance": "medium",
  "max_weeknight_cooking_time": 45,
  "max_weekend_cooking_time": 90,
  "budget_per_week": null,
  "variety_preference": "high",
  "health_focus": "balanced",
  "onboarding_completed": true,
  "created_at": "2025-10-13T10:00:00",
  "updated_at": "2025-10-13T10:00:00"
}
```

---

## Data Capture Workflow

### Planning Agent → Meal Events

**When**: User confirms a meal plan

```python
# After plan is saved
for meal in meal_plan.meals:
    db.add_meal_event(
        date=meal.date,
        recipe_id=meal.recipe_id,
        recipe_name=meal.recipe_name,
        servings_planned=meal.servings,
        meal_plan_id=meal_plan.id,
        status="planned"  # Not cooked yet
    )
```

### Cooking Agent → Meal Events

**When**: User gets cooking guide (indicates they're cooking it)

```python
# Update existing event or create new one
db.update_meal_event(
    date=today,
    recipe_id=recipe_id,
    cooking_time_actual=35,
    servings_actual=6,
    modifications={"doubled_garlic": True},
    status="cooked"
)
```

### User Feedback → Meal Events

**After cooking** (via chatbot):

```
Bot: "How was the Honey Ginger Chicken?"
User: "Amazing! Kids loved it. I doubled the garlic."

Bot records:
- user_rating: 5
- would_make_again: true
- notes: "Kids loved it"
- modifications: {"doubled_garlic": true}
```

---

## Agent Intelligence from Meal Events

### Planning Agent

**Query meal_events for**:

1. **Favorite Recipes**
```sql
SELECT recipe_id, recipe_name, AVG(user_rating) as avg_rating, COUNT(*) as times_cooked
FROM meal_events
WHERE user_rating IS NOT NULL
GROUP BY recipe_id
ORDER BY avg_rating DESC, times_cooked DESC
LIMIT 20
```

2. **Recent Meals (Variety Enforcement)**
```sql
SELECT recipe_id, recipe_name, date
FROM meal_events
WHERE date >= date('now', '-14 days')
ORDER BY date DESC
```

3. **Cuisine Preferences**
```sql
SELECT recipe_cuisine, COUNT(*) as frequency, AVG(user_rating) as avg_rating
FROM meal_events
WHERE recipe_cuisine IS NOT NULL
GROUP BY recipe_cuisine
ORDER BY frequency DESC, avg_rating DESC
```

**LLM Prompt Enhancement**:
```
Analyze user's meal events:
- Top rated recipes: Honey Ginger Chicken (5★, cooked 3x)
- Favorite cuisines: Asian (12x, 4.8★), Italian (10x, 4.5★)
- Recent pattern: Hasn't had Mexican in 3 weeks
- Preferences: Always scales to 6 servings, doubles garlic

Suggest meals that match these patterns.
```

### Shopping Agent

**Query meal_events for**:

1. **Common Ingredients**
```sql
-- Parse ingredients_snapshot JSON
SELECT ingredient, COUNT(*) as frequency
FROM meal_events, json_each(ingredients_snapshot)
WHERE json_each.value LIKE '%ingredient%'
GROUP BY ingredient
ORDER BY frequency DESC
```

2. **Typical Quantities**
```
User buys:
- Chicken: Usually 2 lbs (from events)
- Bok choy: Usually 2 cups (from events)
- Garlic: Always doubles from recipe (from modifications)
```

**LLM Prompt Enhancement**:
```
User's shopping patterns from meal_events:
- Always buys fresh ginger (appears in 15/20 Asian meals)
- Prefers organic chicken (from notes)
- Usually scales recipes 1.5x (servings_actual vs planned)

Generate shopping list accounting for these patterns.
```

### Cooking Agent

**Query meal_events for**:

1. **Past Modifications**
```sql
SELECT modifications, notes
FROM meal_events
WHERE recipe_id = ?
ORDER BY date DESC
LIMIT 5
```

2. **Successful Substitutions**
```sql
SELECT substitutions, user_rating
FROM meal_events
WHERE substitutions IS NOT NULL
  AND user_rating >= 4
```

**LLM Prompt Enhancement**:
```
User's history with this recipe:
- Cooked 2x before, rated 5★ both times
- Last time: Doubled garlic, added bok choy
- Note: "Kids loved the extra veggies"
- Substituted tamari for soy sauce (gluten-free)

Suggest these modifications again and provide cooking guidance.
```

---

## Onboarding Flow

### Step 1: Welcome

```
🍽️ Welcome to Meal Planning Assistant!

I'm your personal cooking companion. Let's get you set up with a few quick questions
so I can plan meals that work perfectly for you.

This will take about 2 minutes. Ready?
```

### Step 2: Household

```
Q1: How many people are you cooking for?

Examples:
- "4 people (2 adults, 2 kids)"
- "Just me"
- "2 adults"

Your answer: ___
```

**Captures**: `household_size`, `cooking_for`

### Step 3: Dietary Restrictions

```
Q2: Any dietary restrictions or allergies I should know about?

Examples:
- "Dairy-free and nut allergies"
- "Vegetarian"
- "None"

Your answer: ___
```

**Captures**: `dietary_restrictions`, `allergens`

### Step 4: Cuisine Preferences

```
Q3: What cuisines do you enjoy?

Pick any that appeal to you:
☐ Italian  ☐ Mexican  ☐ Asian (Chinese/Thai/Japanese)
☐ American ☐ Mediterranean ☐ Indian

Or just tell me: ___
```

**Captures**: `favorite_cuisines`

### Step 5: Cooking Time

```
Q4: How much time do you have for cooking on weeknights?

A) 15-30 minutes (quick meals)
B) 30-45 minutes (moderate)
C) 45-60 minutes (I enjoy cooking)
D) 60+ minutes (I love spending time in the kitchen)

Your answer: ___
```

**Captures**: `max_weeknight_cooking_time`, `max_weekend_cooking_time`

### Step 6: Dislikes (Optional)

```
Q5: Any ingredients you really dislike? (optional)

Examples: "olives, anchovies, cilantro"

Your answer: ___
```

**Captures**: `disliked_ingredients`

### Step 7: Spice Tolerance (Optional)

```
Q6: How do you feel about spicy food?

A) Mild - I prefer mild flavors
B) Medium - Some heat is good
C) Spicy - Bring on the heat!

Your answer: ___
```

**Captures**: `spice_tolerance`

### Step 8: Summary & Confirmation

```
Perfect! Here's your profile:

👥 Cooking for: 4 people (2 adults, 2 kids)
🚫 Dietary: Dairy-free, no peanuts
🌍 Favorite cuisines: Italian, Mexican, Thai, American
⏱️ Weeknight cooking: 45 minutes max
👎 Dislikes: Olives, anchovies
🌶️ Spice: Medium heat

Does this look right? (yes/no/edit)
```

**On confirmation**:
- Save to `user_profile` table
- Set `onboarding_completed = true`
- Ready to plan first meal!

---

## Migration Strategy

### For Existing Users

1. **Check onboarding status**
```python
profile = db.get_user_profile()
if not profile or not profile.onboarding_completed:
    # Run onboarding flow
    run_onboarding()
```

2. **Optional: Import old history**
```python
# Later: Transform old meal_history into meal_events
for old_meal in old_history:
    # Create minimal event (no ratings/notes)
    db.add_meal_event(
        date=old_meal.date,
        recipe_id=None,  # Unknown
        recipe_name=old_meal.meal_name,
        source="imported_history"
    )
```

### For New Users

1. **Start with onboarding**
2. **Every meal planned → creates meal_event (status: "planned")**
3. **Every meal cooked → updates meal_event (status: "cooked")**
4. **Optional feedback → enriches meal_event (rating, notes)**

---

## Benefits Summary

### Planning Agent
- ✅ Knows favorite recipes (ratings)
- ✅ Understands cuisine preferences (frequency + ratings)
- ✅ Enforces variety (recent meal_events)
- ✅ Respects constraints (user_profile)

### Shopping Agent
- ✅ Learns common ingredients (ingredients_snapshot)
- ✅ Knows typical quantities (servings_actual)
- ✅ Suggests based on patterns (frequency analysis)
- ✅ Remembers modifications (always doubles garlic)

### Cooking Agent
- ✅ Suggests past modifications (modifications column)
- ✅ Remembers successful substitutions (substitutions column)
- ✅ Provides realistic timing (cooking_time_actual)
- ✅ Tailors to skill level (user_profile + past success)

---

## API Design

### Database Methods

```python
# User Profile
def get_user_profile() -> Optional[UserProfile]
def save_user_profile(profile: UserProfile) -> bool
def is_onboarded() -> bool

# Meal Events
def add_meal_event(event: MealEvent) -> int
def update_meal_event(event_id: int, updates: Dict) -> bool
def get_meal_events(weeks_back: int = 8) -> List[MealEvent]
def get_favorite_recipes(limit: int = 20) -> List[Dict]
def get_recent_meals(days_back: int = 14) -> List[MealEvent]

# Analytics
def get_cuisine_preferences() -> Dict[str, float]
def get_ingredient_frequency() -> Dict[str, int]
def get_avg_cooking_time() -> Dict[str, int]
```

---

## Next Steps

1. ✅ Design complete
2. ⏳ Implement database schema updates
3. ⏳ Create data models (MealEvent, UserProfile)
4. ⏳ Build onboarding chatbot
5. ⏳ Update agents to write meal_events
6. ⏳ Update agents to read meal_events for learning
7. ⏳ Migration script to reset database

---

*Design Document v1.0*
*Date: October 13, 2025*
*Status: Ready for Implementation*
