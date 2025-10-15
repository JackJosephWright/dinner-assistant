# Performance Optimization Guide

## Current Performance Analysis

Based on log analysis, here are the timing breakdowns and bottlenecks:

### Meal Planning (45-60 seconds total)
1. **History Analysis** (~3s) - 1 LLM call
   - Analyzes 8 weeks of meal history
   - 1024 max tokens

2. **Recipe Search** (~5s) - 1 LLM call + 7 database queries
   - LLM generates 5-7 search keywords
   - Each keyword triggers `db.search_recipes()` (limit=15)
   - Database queries run **sequentially**

3. **Meal Selection** (~7s) - 1 LLM call
   - Sends 50 recipe candidates to LLM
   - 2048 max tokens

4. **Explanation** (~8s) - 2 LLM calls
   - Generates friendly explanation text
   - 1024 max tokens each

### Shopping List Generation (20-25 seconds)
1. **Ingredient Collection** (<1s) - Database queries
   - Fetches 7 recipes
   - Extracts ~64 raw ingredients

2. **LLM Consolidation** (~20s) - **MAIN BOTTLENECK**
   - Single LLM call processes all 64 ingredients
   - Groups, deduplicates, formats

### Meal Swapping (8-12 seconds)
1. **Search Query Generation** (~4s) - 1 LLM call
2. **Recipe Search** (~1s) - 3-5 database queries
3. **Selection** (~4s) - 1 LLM call

---

## Identified Bottlenecks

### 🔴 Critical Bottlenecks

1. **Shopping List LLM Call** (20s)
   - Single massive LLM call for 64 ingredients
   - No progress feedback during call
   - Blocks everything

2. **Sequential Database Queries** (3-5s)
   - Recipe searches run one at a time (line 316-349 in agentic_planning_agent.py)
   - 5-7 queries × 0.5s each = wasted time

3. **Multiple Shopping List Generations**
   - Logs show **5 identical shopping lists created in parallel** (09:28:09 - 09:28:37)
   - Same meal plan processed 5 times simultaneously
   - This is a UI/API bug causing redundant work

### 🟡 Medium Issues

4. **No Streaming LLM Responses**
   - User sees nothing until LLM completes
   - Could stream explanations/responses

5. **explain_plan() Always Runs** (8s)
   - Called even if user doesn't need it
   - Could be optional/cached

6. **Redundant Recipe Fetching**
   - `explain_plan()` fetches recipes one by one (line 498)
   - Could batch fetch

---

## Optimization Strategies

### Quick Wins (1-2 hours implementation)

#### 1. Parallelize Database Queries ⚡
**Impact:** 3-5s savings on planning

```python
# In _search_recipes_node (line 316)
import concurrent.futures

# Current: Sequential
for line in search_plan.split("\n"):
    recipes = self.db.search_recipes(query=keyword, max_time=max_time, limit=15)

# Optimized: Parallel
keywords = [extract_keyword(line) for line in search_plan.split("\n")]

with concurrent.futures.ThreadPoolExecutor(max_workers=5) as executor:
    futures = {
        executor.submit(self.db.search_recipes, query=kw, max_time=max_time, limit=15): kw
        for kw in keywords
    }
    for future in concurrent.futures.as_completed(futures):
        recipes = future.result()
        # Process recipes...
```

#### 2. Fix Duplicate Shopping List Bug ⚡⚡⚡
**Impact:** 60-80s savings (prevents 4 redundant calls)

The issue is in `src/web/app.py` - multiple tabs/clicks trigger parallel requests.

```python
# Add request deduplication
shopping_list_locks = {}  # meal_plan_id -> Lock

@app.route('/api/shop', methods=['POST'])
def api_create_shopping_list():
    meal_plan_id = data.get('meal_plan_id') or session.get('meal_plan_id')

    # Check if already exists
    existing_lists = assistant.db.get_recent_shopping_lists(meal_plan_id)
    if existing_lists and not scaling_instructions:
        return jsonify(existing_lists[0])  # Return cached

    # Add lock to prevent duplicate processing
    lock = shopping_list_locks.setdefault(meal_plan_id, threading.Lock())
    if not lock.acquire(blocking=False):
        return jsonify({"success": False, "error": "Already generating"}), 409

    try:
        result = assistant.create_shopping_list(meal_plan_id, scaling_instructions)
        return jsonify(result)
    finally:
        lock.release()
```

#### 3. Cache Shopping Lists
**Impact:** 20s savings on repeated requests

```python
# In database.py, add:
def get_shopping_list_by_meal_plan(self, meal_plan_id: str) -> Optional[GroceryList]:
    """Get most recent shopping list for a meal plan."""
    with sqlite3.connect(self.user_db) as conn:
        # Query for existing list created in last hour
        # Return if found
```

#### 4. Make explain_plan() Optional
**Impact:** 8s savings when not needed

```python
# In app.py line 275
if result["success"] and request.json.get('include_explanation', True):
    explanation = assistant.planning_agent.explain_plan(result['meal_plan_id'])
```

### Medium Wins (3-5 hours implementation)

#### 5. Implement Prompt Caching
**Impact:** 50-70% faster LLM calls (after first call)

Claude supports prompt caching for repeated content.

```python
# In agentic_shopping_agent.py
response = self.client.messages.create(
    model=self.model,
    max_tokens=4096,
    system=[
        {
            "type": "text",
            "text": "You are a meal planning assistant...",
            "cache_control": {"type": "ephemeral"}  # ← Cache system prompt
        }
    ],
    messages=[{"role": "user", "content": ingredients_text}]
)
```

**Savings:**
- First call: 20s (same)
- Subsequent calls: 6-8s (cache hit)

#### 6. Batch Recipe Fetching
**Impact:** 1-2s savings

```python
# In explain_plan() line 498
# Instead of: for meal in plan.meals: recipe = self.db.get_recipe(meal.recipe_id)

# Batch fetch:
recipe_ids = [meal.recipe_id for meal in plan.meals]
recipes = self.db.batch_get_recipes(recipe_ids)  # Single query with WHERE id IN (...)
```

#### 7. Add Progress Streaming
**Impact:** Better UX, no time savings

Already partially implemented, but fix the Flask context error:

```python
# In app.py line 109, fix:
def generate():
    with app.app_context():  # ← Add this
        progress_queue = get_progress_queue(session_id)
        # ... rest of code
```

### Advanced Optimizations (1-2 days)

#### 8. Add Redis Caching Layer
**Impact:** 15-20s savings on repeated plans

Cache LLM responses by input hash:
- Same ingredients → same shopping list
- Same user preferences → similar meal selections

#### 9. Implement Streaming LLM Responses
**Impact:** Perceived latency reduction (user sees progress)

```python
# Use Anthropic's streaming API
with self.client.messages.stream(
    model=self.model,
    max_tokens=1024,
    messages=[{"role": "user", "content": prompt}]
) as stream:
    for text in stream.text_stream:
        yield text  # Send to frontend
```

#### 10. Pre-generate Common Plans
**Impact:** Instant results for common queries

Background job that generates plans for:
- "5 day weeknight dinners"
- "7 day family meals"
- Popular cuisine combinations

---

## Recommended Implementation Order

### Phase 1: Immediate (Today)
1. ✅ Fix duplicate shopping list bug (#2)
2. ✅ Add shopping list caching (#3)
3. ✅ Make explain_plan() optional (#4)

**Expected savings:** 30-40s per workflow

### Phase 2: This Week
4. ✅ Parallelize database queries (#1)
5. ✅ Batch recipe fetching (#6)
6. ✅ Fix progress streaming error (#7)

**Expected savings:** Additional 5-7s

### Phase 3: Next Sprint
7. ✅ Implement prompt caching (#5)
8. ✅ Add Redis caching (#8)

**Expected savings:** 50-60% on repeated operations

---

## Performance Targets

| Operation | Current | After Phase 1 | After Phase 2 | After Phase 3 |
|-----------|---------|---------------|---------------|---------------|
| Meal Planning | 45-60s | 35-45s | 30-40s | 15-20s (cached) |
| Shopping List | 20-25s | 2-5s (cached) | 2-5s | 1-2s (cached) |
| Meal Swap | 8-12s | 8-12s | 6-10s | 3-5s (cached) |

---

## Monitoring & Profiling

Add timing decorators:

```python
import time
import functools

def timeit(func):
    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        start = time.time()
        result = func(*args, **kwargs)
        duration = time.time() - start
        logger.info(f"{func.__name__} took {duration:.2f}s")
        return result
    return wrapper

# Apply to all agent methods
@timeit
def plan_week(self, week_of, num_days=7):
    ...
```

---

## Database Optimization

Current `search_recipes()` query:

```python
sql = "SELECT * FROM recipes WHERE 1=1"
# + LIKE queries on name/description
```

**Optimizations:**
1. Add full-text search index (FTS5)
2. Pre-filter by estimated_time using indexed column
3. Limit result columns (don't SELECT *)

```python
# Add FTS index
CREATE VIRTUAL TABLE recipes_fts USING fts5(name, description, content=recipes);

# Query using FTS
SELECT recipes.* FROM recipes_fts
JOIN recipes ON recipes_fts.rowid = recipes.id
WHERE recipes_fts MATCH ? AND estimated_time <= ?
LIMIT 15
```

**Expected speedup:** 50-70% faster searches (from ~500ms to ~150ms)

---

## Next Steps

1. Profile current performance with timing decorators
2. Implement Phase 1 optimizations
3. Measure improvement
4. Decide on Phase 2 based on results
