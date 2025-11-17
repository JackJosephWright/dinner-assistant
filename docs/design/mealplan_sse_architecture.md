# MealPlan-Centric Architecture with SSE State Synchronization

**Last Updated:** 2025-11-15
**Status:** Living Document - Describes current architecture and patterns

---

## Table of Contents
1. [Overview](#overview)
2. [MealPlan Object Architecture](#mealplan-object-architecture)
3. [SSE Update Architecture](#sse-update-architecture)
4. [Tab-Specific Patterns](#tab-specific-patterns)
5. [Centralized Patterns](#centralized-patterns)
6. [Current Issues](#current-issues)
7. [Documentation Gaps](#documentation-gaps)

---

## Overview

The Dinner Assistant web application is built around a central **`MealPlan`** object that serves as the single source of truth for meal planning state. State changes to this object trigger **Server-Sent Events (SSE)** that synchronize all open browser tabs in real-time.

**Key Architecture Principles:**
- **MealPlan as Single Source of Truth**: All tabs derive their data from the current MealPlan
- **SSE for State Synchronization**: Changes broadcast to all tabs via SSE streams
- **Embedded Data (0-Query Architecture)**: MealPlan contains full Recipe objects, no additional DB queries needed
- **Session-Based State**: Flask sessions track current `meal_plan_id`

---

## MealPlan Object Architecture

### 1. Data Model Structure

**MealPlan** object (defined in `src/data/models.py:463-637`):
```python
@dataclass
class MealPlan:
    id: str                              # Unique identifier
    week_of: str                         # ISO format start date (e.g., "2025-11-04")
    meals: List[PlannedMeal]            # List of PlannedMeal objects
    created_at: datetime                 # Timestamp
    preferences_applied: List[str]       # Applied preferences
    backup_recipes: Dict[str, List[Recipe]]  # For instant meal swaps
```

**PlannedMeal** object (embedded in MealPlan):
```python
@dataclass
class PlannedMeal:
    date: str              # ISO format: "2025-01-20"
    meal_type: str         # "breakfast", "lunch", "dinner", "snack"
    recipe: Recipe         # Full Recipe object embedded (Phase 2 enhancement)
    servings: int          # May differ from recipe.servings
    notes: Optional[str]   # Optional notes
```

**Recipe** object (embedded in PlannedMeal):
- Contains full recipe data: ingredients, steps, nutrition, etc.
- Structured ingredients available for 5,000 enriched recipes
- No additional database queries needed once MealPlan is loaded

### 2. Storage and Persistence

**Session Storage:**
- Flask session variable: `session['meal_plan_id']` (string)
- Persists across page reloads within same browser session
- Clears when browser closes

**Database Storage:**
- Database: `user_data.db` (SQLite)
- Table: `meal_plans`
- Retrieval: `assistant.db.get_meal_plan(plan_id)`
- Location: `src/data/database.py:350-375`

**Session Restoration:**
- Function: `restore_session_from_db()` (defined in `src/web/app.py:275-305`)
- Called at start of each route: `/plan`, `/shop`, `/cook`
- Automatically restores `meal_plan_id` from most recent plan if session is empty
- Ensures continuity when user refreshes or reopens browser

### 3. Lifecycle

```
1. Creation
   ↓
   User: "Plan meals for the week"
   ↓
   Backend: Planning agent creates MealPlan object
   ↓
   Database: MealPlan saved to user_data.db
   ↓
   Session: meal_plan_id stored in Flask session

2. Modification
   ↓
   User: Swaps a meal
   ↓
   Backend: MealPlan updated with new recipe
   ↓
   Database: Updated MealPlan saved
   ↓
   SSE: broadcast_state_change('meal_plan_changed', {...})
   ↓
   All Tabs: Receive event and refresh their views

3. Retrieval
   ↓
   Route handler: restore_session_from_db()
   ↓
   Database: meal_plan = assistant.db.get_meal_plan(session['meal_plan_id'])
   ↓
   Template: Render with MealPlan data
```

---

## SSE Update Architecture

### 1. Core Infrastructure

**State Change Queues** (`src/web/app.py:129`):
```python
state_change_queues = {}  # tab_id -> queue
state_change_lock = threading.Lock()
```

**Broadcasting Function** (`src/web/app.py:218-230`):
```python
def broadcast_state_change(event_type: str, data: dict):
    """Broadcast a state change event to all listening tabs."""
    with state_change_lock:
        for tab_id, tab_queue in list(state_change_queues.items()):
            try:
                tab_queue.put({
                    "type": event_type,
                    "data": data,
                    "timestamp": datetime.now().isoformat()
                })
            except Exception as e:
                logger.error(f"Error broadcasting to tab {tab_id}: {e}")
```

**SSE Stream Endpoint** (`src/web/app.py:169-215`):
```python
@app.route('/api/state-stream')
def state_stream():
    """Server-Sent Events endpoint for state change notifications."""
    tab_id = request.args.get('tab_id', f'tab_{uuid.uuid4()}')
    tab_queue = get_or_create_queue(tab_id)

    def generate():
        try:
            while True:
                # Send keepalive every 30 seconds
                # Pull events from queue and send to client
                ...

    return Response(generate(), mimetype='text/event-stream')
```

### 2. Event Types

#### Event 1: `meal_plan_changed`

**Triggered when:**
- New meal plan created (`/api/plan` - line 484)
- Meal swapped in plan (`/api/swap-meal` - line 522)
- Chat creates/modifies plan (`/api/chat` - line 812)

**Payload:**
```json
{
    "type": "meal_plan_changed",
    "data": {
        "meal_plan_id": "abc123",
        "week_of": "2025-11-10",
        "date_changed": "2025-11-12"  // Optional: specific date that changed
    },
    "timestamp": "2025-11-15T10:30:00"
}
```

#### Event 2: `shopping_list_changed`

**Triggered when:**
- Shopping list regenerated after meal swap (background thread - line 540)
- New shopping list created (`/api/shop` - line 613)
- Chat creates/modifies shopping list (lines 832, 849)

**Payload:**
```json
{
    "type": "shopping_list_changed",
    "data": {
        "shopping_list_id": "xyz789",
        "meal_plan_id": "abc123"
    },
    "timestamp": "2025-11-15T10:30:05"
}
```

### 3. Update Flow

**Complete Flow (documented in `docs/development/SESSION_2025_11_07.md:112-131`):**

```
User Action (e.g., swap meal in Plan tab)
    ↓
Backend: Update MealPlan in database
    ↓
Backend: Save to session['meal_plan_id']
    ↓
Backend: broadcast_state_change('meal_plan_changed', {...})
    ↓
✨ IMMEDIATE: All tabs receive meal_plan_changed event
    ↓
Plan Tab: Calls updateMealPlanDisplay() → AJAX fetch /api/plan/current → Update DOM
Shop Tab: Logs message, waits for shopping_list_changed
Cook Tab: Currently reloads page (window.location.reload())
    ↓
[Background Thread - Parallel Execution]
    ↓
Backend: Regenerate shopping list using LLM
    ↓
Backend: broadcast_state_change('shopping_list_changed', {...})
    ↓
Shop Tab: Receives event → window.location.reload()
```

**Performance Impact:**
- Parallel execution provides **5-10 second faster** Plan tab response
- User sees Plan tab update immediately, shopping list updates in background
- No blocking while shopping list regenerates

### 4. Frontend SSE Listener Pattern

**Standard Pattern (from Shop tab - `src/web/templates/shop.html:369-401`):**

```javascript
let stateEventSource = null;
let tabId = 'tab_' + Date.now() + '_' + Math.random().toString(36).substr(2, 9);

function startStateStream() {
    // Close existing stream if any
    if (stateEventSource) {
        stateEventSource.close();
    }

    // Create new SSE connection for state changes
    stateEventSource = new EventSource(`/api/state-stream?tab_id=${tabId}`);

    stateEventSource.onmessage = (event) => {
        const update = JSON.parse(event.data);

        if (update.type === 'meal_plan_changed') {
            // Handle meal plan change
            console.log('Meal plan changed...');
        } else if (update.type === 'shopping_list_changed') {
            // Handle shopping list change
            console.log('Shopping list changed, reloading...');
            window.location.reload();
        }
        // Ignore keepalive messages
    };

    stateEventSource.onerror = (error) => {
        console.error('State stream error:', error);
        stateEventSource.close();
        stateEventSource = null;
    };
}

// Start SSE listener when page loads
startStateStream();
```

---

## Tab-Specific Patterns

### Plan Tab

**Route:** `/plan` (`src/web/app.py:315-365`)

**Server-Side Pattern:**
```python
@app.route('/plan')
def plan_page():
    # Step 1: Restore session
    restore_session_from_db()

    # Step 2: Fetch meal plan if exists
    current_plan = None
    if 'meal_plan_id' in session:
        meal_plan = assistant.db.get_meal_plan(session['meal_plan_id'])
        if meal_plan:
            # Step 3: Flatten recipe fields for frontend
            enriched_meals = []
            for meal in meal_plan.meals:
                meal_dict = meal.to_dict()
                # Flatten recipe fields for template access
                if meal.recipe:
                    meal_dict['recipe_id'] = meal.recipe.id
                    meal_dict['recipe_name'] = meal.recipe.name
                    meal_dict['description'] = meal.recipe.description
                    meal_dict['estimated_time'] = meal.recipe.estimated_time
                    meal_dict['cuisine'] = meal.recipe.cuisine
                    meal_dict['difficulty'] = meal.recipe.difficulty
                # Transform date
                meal_dict['meal_date'] = meal.date_obj.strftime('%A, %B %d')
                enriched_meals.append(meal_dict)

            # Step 4: Wrap in plan object
            current_plan = {
                'id': meal_plan.id,
                'week_of': meal_plan.week_of,
                'meals': enriched_meals,
            }

    return render_template('plan.html', current_plan=current_plan, ...)
```

**Client-Side SSE Pattern:**
```javascript
// SSE Listener (plan.html:878-897)
stateEventSource.onmessage = (event) => {
    const update = JSON.parse(event.data);

    if (update.type === 'meal_plan_changed') {
        updateMealPlanDisplay();  // AJAX refresh, no page reload
    }
    // Ignore shopping_list_changed
};

// Update Function (plan.html:1062-1121)
async function updateMealPlanDisplay() {
    const response = await fetch('/api/plan/current');
    const result = await response.json();

    if (result.success && result.plan) {
        // Update DOM with new meal data
        // No page reload - smooth update
    }
}
```

**Data Structure Passed to Template:**
```javascript
current_plan = {
    'id': 'plan_123',
    'week_of': '2025-11-10',
    'meals': [
        {
            'date': '2025-11-10',
            'meal_date': 'Monday, November 10',  // Formatted date
            'meal_type': 'dinner',
            'recipe_id': 532245,
            'recipe_name': 'Chicken Teriyaki',
            'description': '...',
            'estimated_time': 30,
            'cuisine': 'Japanese',
            'difficulty': 'medium',
            'servings': 4,
            'notes': None,
            'recipe': {...}  // Full nested recipe dict
        },
        ...
    ]
}
```

### Shop Tab

**Route:** `/shop` (`src/web/app.py:368-389`)

**Server-Side Pattern:**
```python
@app.route('/shop')
def shop_page():
    # Step 1: Restore session
    restore_session_from_db()

    # Step 2: Load shopping list (NOT meal plan directly)
    shopping_list = None
    if 'shopping_list_id' in session:
        shopping_list = assistant.db.get_shopping_list(session['shopping_list_id'])

    # Step 3: Pass meal_plan_id for reference only
    return render_template(
        'shop.html',
        shopping_list=shopping_list,
        meal_plan_id=session.get('meal_plan_id'),
        ...
    )
```

**Client-Side SSE Pattern:**
```javascript
// SSE Listener (shop.html:381-394)
stateEventSource.onmessage = (event) => {
    const update = JSON.parse(event.data);

    if (update.type === 'meal_plan_changed') {
        console.log('Meal plan changed - shopping list will auto-regenerate...');
        // Do nothing - backend auto-regenerates shopping list in background
    } else if (update.type === 'shopping_list_changed') {
        console.log('Shopping list changed, reloading...');
        window.location.reload();  // Full page reload
    }
};
```

**Key Difference:** Shop tab doesn't directly access MealPlan - it displays the **derived shopping list** generated from the MealPlan.

### Cook Tab

**Route:** `/cook` (`src/web/app.py:392-427`)

**Current Server-Side Pattern (INCONSISTENT):**
```python
@app.route('/cook')
def cook_page():
    # Step 1: Restore session
    restore_session_from_db()

    # Step 2: Fetch meal plan if exists
    current_meals = None
    if 'meal_plan_id' in session:
        meal_plan = assistant.db.get_meal_plan(session['meal_plan_id'])
        if meal_plan:
            # Step 3: Flatten recipe fields (SAME as Plan tab)
            enriched_meals = []
            for meal in meal_plan.meals:
                meal_dict = meal.to_dict()
                if meal.recipe:
                    meal_dict['recipe_id'] = meal.recipe.id
                    meal_dict['recipe_name'] = meal.recipe.name
                    # ... same flattening as Plan tab
                meal_dict['meal_date'] = meal_dict.pop('date', None)  # Different date format!
                enriched_meals.append(meal_dict)

            current_meals = enriched_meals  # NOT wrapped in plan dict!

    return render_template('cook.html', current_meals=current_meals, ...)
```

**Current Client-Side SSE Pattern (INEFFICIENT):**
```javascript
// SSE Listener (cook.html:348-351)
stateEventSource.onmessage = (event) => {
    const update = JSON.parse(event.data);

    if (update.type === 'meal_plan_changed') {
        console.log('Meal plan changed, reloading cook page...');
        window.location.reload();  // Full page reload (not optimal!)
    }
    // Ignore shopping_list_changed
};
```

**Data Structure Passed to Template (INCONSISTENT):**
```javascript
// Cook tab receives just the array:
current_meals = [
    {
        'date': '2025-11-10',  // Raw date, not formatted!
        'meal_date': None,     // Different from Plan tab!
        'recipe_id': 532245,
        'recipe_name': 'Chicken Teriyaki',
        // ... same flattened fields
    },
    ...
]

// vs Plan tab which receives wrapped object:
current_plan = {
    'id': 'plan_123',
    'week_of': '2025-11-10',
    'meals': [...]
}
```

---

## Centralized Patterns

### 1. Session Management Pattern

**`restore_session_from_db()` Function** (`src/web/app.py:275-305`):

```python
def restore_session_from_db():
    """
    Restore session from database if needed.

    This ensures continuity when:
    - User refreshes the page
    - Flask session expires
    - User opens app in new browser tab
    """
    # Skip if we already have a meal plan in session
    if 'meal_plan_id' in session:
        return

    # Try to load most recent meal plan from database
    try:
        # Get most recent plan (ordered by created_at DESC)
        recent_plans = assistant.db.get_all_meal_plans()
        if recent_plans:
            most_recent = recent_plans[0]  # First = most recent
            session['meal_plan_id'] = most_recent.id
            logger.info(f"Restored session with meal plan: {most_recent.id}")

            # Also restore shopping list if exists
            shopping_lists = assistant.db.get_shopping_lists_for_plan(most_recent.id)
            if shopping_lists:
                session['shopping_list_id'] = shopping_lists[0].id
    except Exception as e:
        logger.error(f"Error restoring session: {e}")
```

**Usage Pattern (REQUIRED for all routes):**
```python
@app.route('/any-route')
def any_route():
    # ALWAYS call this first!
    restore_session_from_db()

    # Now session['meal_plan_id'] is guaranteed to exist (if any plans exist)
    if 'meal_plan_id' in session:
        meal_plan = assistant.db.get_meal_plan(session['meal_plan_id'])
        # ... rest of route logic
```

### 2. Data Transformation Pattern

**The Flattening Pattern (for Frontend Compatibility):**

All routes that pass MealPlan data to templates SHOULD use this pattern:

```python
# Step 1: Get MealPlan object from database
meal_plan = assistant.db.get_meal_plan(session['meal_plan_id'])

# Step 2: Flatten recipe fields for template access
enriched_meals = []
for meal in meal_plan.meals:
    meal_dict = meal.to_dict()

    # Flatten recipe fields from nested structure
    if meal.recipe:
        meal_dict['recipe_id'] = meal.recipe.id
        meal_dict['recipe_name'] = meal.recipe.name
        meal_dict['description'] = meal.recipe.description
        meal_dict['estimated_time'] = meal.recipe.estimated_time
        meal_dict['cuisine'] = meal.recipe.cuisine
        meal_dict['difficulty'] = meal.recipe.difficulty

    # Rename 'date' to 'meal_date' for clarity
    meal_dict['meal_date'] = meal_dict.pop('date', None)

    enriched_meals.append(meal_dict)

# Step 3: Wrap in plan object with metadata
current_plan = {
    'id': meal_plan.id,
    'week_of': meal_plan.week_of,
    'meals': enriched_meals,
}
```

**Why this pattern?**
- Templates can access `meal.recipe_name` instead of `meal.recipe.name`
- Jinja2 templates work better with flat dictionaries
- Consistent field names across all tabs
- Includes plan metadata (id, week_of) for reference

### 3. API Pattern for Dynamic Updates

**Centralized Endpoint:** `/api/plan/current` (`src/web/app.py:986-1026`)

```python
@app.route('/api/plan/current', methods=['GET'])
def api_get_current_plan():
    """Get current meal plan with enriched data."""
    try:
        meal_plan_id = session.get('meal_plan_id')
        if not meal_plan_id:
            return jsonify({"success": False, "error": "No active meal plan"}), 404

        meal_plan = assistant.db.get_meal_plan(meal_plan_id)
        if not meal_plan:
            return jsonify({"success": False, "error": "Meal plan not found"}), 404

        # Use same flattening pattern as routes
        enriched_meals = []
        for meal in meal_plan.meals:
            meal_dict = meal.to_dict()
            # Flatten recipe fields
            if meal.recipe:
                meal_dict['recipe_id'] = meal.recipe.id
                meal_dict['recipe_name'] = meal.recipe.name
                meal_dict['description'] = meal.recipe.description
                meal_dict['estimated_time'] = meal.recipe.estimated_time
                meal_dict['cuisine'] = meal.recipe.cuisine
                meal_dict['difficulty'] = meal.recipe.difficulty
            # Rename 'date' to 'meal_date'
            meal_dict['meal_date'] = meal_dict.pop('date', None)
            enriched_meals.append(meal_dict)

        return jsonify({
            "success": True,
            "plan": {
                'id': meal_plan.id,
                'week_of': meal_plan.week_of,
                'meals': enriched_meals,
            }
        })

    except Exception as e:
        logger.error(f"Error getting current plan: {e}", exc_info=True)
        return jsonify({"success": False, "error": str(e)}), 500
```

**Usage (from frontend):**
```javascript
async function updateMealPlanDisplay() {
    try {
        const response = await fetch('/api/plan/current');
        const result = await response.json();

        if (result.success && result.plan) {
            // Update DOM with result.plan.meals
        }
    } catch (error) {
        console.error('Error fetching plan:', error);
    }
}
```

---

## Current Issues

### 1. Cook Tab Inconsistencies

**Problem 1: Inconsistent Data Structure**
- **Plan route** passes: `current_plan = {'id': ..., 'week_of': ..., 'meals': [...]}`
- **Cook route** passes: `current_meals = [...]` (just the meals array)
- **Impact:** Cook tab cannot access plan metadata (week_of, id)

**Problem 2: Inefficient SSE Response**
- **Plan tab:** Calls `updateMealPlanDisplay()` → AJAX fetch → updates DOM (smooth)
- **Cook tab:** Calls `window.location.reload()` → full page refresh (loses scroll position)
- **Impact:** Worse user experience, loses state

**Problem 3: Inconsistent Date Formatting**
- **Plan route:** `meal_dict['meal_date'] = date_obj.strftime('%A, %B %d')` → "Monday, November 10"
- **Cook route:** `meal_dict['meal_date'] = meal_dict.pop('date', None)` → "2025-11-10"
- **Impact:** Different display formats between tabs

**Problem 4: No Dynamic Update Capability**
- Cook tab has no equivalent to Plan tab's `updateMealPlanDisplay()` function
- Cannot update without full page reload
- **Impact:** Less efficient, worse UX

### 2. Documentation Gaps

**What's Missing:**
1. No formal ADR (Architecture Decision Record) for SSE design
2. No documentation of `restore_session_from_db()` pattern
3. No guidelines on when to use page reload vs AJAX updates
4. No session lifecycle documentation
5. No error handling patterns for SSE
6. No retry logic documentation

**Existing Documentation:**
- `docs/development/SESSION_2025_11_07.md` - Session notes (what was built)
- Code comments in implementation
- CLAUDE.md Phase 3 section (brief overview)

**Missing Documentation:**
- Formal design specification
- Best practices guide
- SSE architecture ADR
- Session management guide

---

## Recommendations

### 1. Fix Cook Tab to Match Plan Tab Pattern

**Server-Side:**
```python
@app.route('/cook')
def cook_page():
    restore_session_from_db()

    current_plan = None  # Changed from current_meals
    if 'meal_plan_id' in session:
        meal_plan = assistant.db.get_meal_plan(session['meal_plan_id'])
        if meal_plan:
            enriched_meals = []
            for meal in meal_plan.meals:
                meal_dict = meal.to_dict()
                # Same flattening as Plan tab
                if meal.recipe:
                    meal_dict['recipe_id'] = meal.recipe.id
                    meal_dict['recipe_name'] = meal.recipe.name
                    # ... rest of fields
                # Use same date formatting as Plan tab
                meal_dict['meal_date'] = date_obj.strftime('%A, %B %d')
                enriched_meals.append(meal_dict)

            # Wrap in plan object (same as Plan tab)
            current_plan = {
                'id': meal_plan.id,
                'week_of': meal_plan.week_of,
                'meals': enriched_meals,
            }

    return render_template('cook.html', current_plan=current_plan, ...)
```

**Client-Side:**
```javascript
// Add dynamic update function
async function updateMealDisplay() {
    const response = await fetch('/api/plan/current');
    const result = await response.json();

    if (result.success && result.plan) {
        // Update "This Week's Meals" section dynamically
        updateMealCards(result.plan.meals);
    }
}

// SSE listener calls update function (not page reload)
stateEventSource.onmessage = (event) => {
    const update = JSON.parse(event.data);

    if (update.type === 'meal_plan_changed') {
        console.log('Meal plan changed, updating meal list...');
        updateMealDisplay();  // Dynamic update, no reload
    }
};
```

### 2. Create Missing Documentation

**Priority 1 (High):**
1. `docs/design/sse_architecture.md` - This document (now created!)
2. `docs/patterns/session_management.md` - Document `restore_session_from_db()` pattern
3. Update `docs/design/decisions.md` - Add SSE ADR

**Priority 2 (Medium):**
4. `docs/patterns/sse_listeners.md` - Guidelines for implementing SSE listeners
5. `docs/patterns/meal_plan_lifecycle.md` - When to load/save MealPlan objects

**Priority 3 (Low):**
6. Error handling patterns for SSE
7. Retry logic documentation

### 3. Standardize All Routes

Ensure all routes that use MealPlan follow the same pattern:
1. Call `restore_session_from_db()` first
2. Use same flattening pattern for recipe fields
3. Wrap in `current_plan` object (not just meals array)
4. Use consistent date formatting
5. Use consistent template variable names

---

## References

### Key Files
- **Data Models:** `src/data/models.py:463-637` (MealPlan), `src/data/models.py:340-460` (PlannedMeal)
- **Database:** `src/data/database.py:350-375` (get_meal_plan)
- **Session Management:** `src/web/app.py:275-305` (restore_session_from_db)
- **SSE Infrastructure:** `src/web/app.py:129-230` (state queues and broadcasting)
- **Plan Route:** `src/web/app.py:315-365`
- **Shop Route:** `src/web/app.py:368-389`
- **Cook Route:** `src/web/app.py:392-427`
- **API Endpoint:** `src/web/app.py:986-1026` (/api/plan/current)
- **Plan Tab SSE:** `src/web/templates/plan.html:878-897`
- **Shop Tab SSE:** `src/web/templates/shop.html:381-394`
- **Cook Tab SSE:** `src/web/templates/cook.html:348-351`

### Documentation
- **Session Notes:** `docs/development/SESSION_2025_11_07.md`
- **Phase 3 Overview:** `CLAUDE.md` (lines 124-181)
- **Architecture Discussion:** `docs/ARCHITECTURE_DISCUSSION.md`

---

**Document Status:** This is a living document that describes the current architecture. Update as patterns evolve.
