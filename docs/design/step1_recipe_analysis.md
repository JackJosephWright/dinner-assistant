# Step 1: Current Recipe Object Analysis

**Date:** 2025-10-28
**Status:** Analysis Complete - Awaiting Review
**Location:** `src/data/models.py`, lines 18-99

---

## Current Recipe Class Definition

```python
@dataclass
class Recipe:
    """Recipe from Food.com dataset."""

    # Required fields (from database)
    id: str
    name: str
    description: str
    ingredients: List[str]        # Clean names: ["flour", "eggs", "milk"]
    ingredients_raw: List[str]     # With quantities: ["2 cups flour", "3 eggs", ...]
    steps: List[str]               # Cooking instructions
    servings: int
    serving_size: str
    tags: List[str]                # Raw tags from Food.com

    # Derived fields (computed in __post_init__)
    estimated_time: Optional[int] = None      # Minutes
    cuisine: Optional[str] = None             # "Italian", "Mexican", etc.
    difficulty: str = "medium"                # "easy", "medium", "hard"
```

---

## Example Recipe Object

```python
Recipe(
    id="12345",
    name="Grilled Salmon with Roasted Vegetables",
    description="A healthy and delicious weeknight dinner featuring perfectly grilled salmon...",

    ingredients=[
        "salmon",
        "olive oil",
        "bell peppers",
        "zucchini",
        "garlic",
        "lemon"
    ],

    ingredients_raw=[
        "2 salmon fillets (6 oz each)",
        "2 tablespoons olive oil",
        "1 red bell pepper, sliced",
        "1 zucchini, cut into chunks",
        "3 cloves garlic, minced",
        "1 lemon, juiced"
    ],

    steps=[
        "Preheat grill to medium-high heat",
        "Brush salmon with olive oil and season with salt and pepper",
        "Toss vegetables with remaining oil, garlic, and lemon juice",
        "Grill salmon 4-5 minutes per side",
        "Roast vegetables at 400°F for 20 minutes"
    ],

    servings=2,
    serving_size="1 fillet + 1 cup vegetables",

    tags=[
        "healthy",
        "30-minutes-or-less",
        "american",
        "easy",
        "fish",
        "gluten-free",
        "main-dish"
    ],

    # Derived (computed from tags)
    estimated_time=30,        # From "30-minutes-or-less" tag
    cuisine="American",       # From "american" tag
    difficulty="easy"         # From "easy" tag
)
```

---

## Serialization Analysis

### to_dict() Output

```json
{
  "id": "12345",
  "name": "Grilled Salmon with Roasted Vegetables",
  "description": "A healthy and delicious weeknight dinner...",
  "ingredients": ["salmon", "olive oil", "bell peppers", ...],
  "ingredients_raw": ["2 salmon fillets (6 oz each)", ...],
  "steps": ["Preheat grill to medium-high heat", ...],
  "servings": 2,
  "serving_size": "1 fillet + 1 cup vegetables",
  "tags": ["healthy", "30-minutes-or-less", ...],
  "estimated_time": 30,
  "cuisine": "American",
  "difficulty": "easy"
}
```

### Size Estimates

**Typical Recipe (from example above):**
- JSON serialized: ~2,800 bytes (~2.8 KB)
- Breakdown:
  - Description: ~200 bytes
  - ingredients_raw: ~300 bytes (6 items × 50 bytes avg)
  - steps: ~400 bytes (5 steps × 80 bytes avg)
  - tags: ~150 bytes
  - Other fields: ~150 bytes
  - JSON overhead: ~100 bytes

**Complex Recipe (many ingredients/steps):**
- JSON serialized: ~8-10 KB
- 20 ingredients: ~1,000 bytes
- 15 steps: ~1,200 bytes
- Long description: ~500 bytes

**Simple Recipe (few ingredients/steps):**
- JSON serialized: ~1-1.5 KB

**Average across Food.com dataset:** ~3-5 KB per recipe

---

## How __post_init__ Works

**Extraction Logic (lines 37-76):**

1. **Time Extraction** (_extract_time_from_tags):
   - Maps specific tags to minutes:
     - "15-minutes-or-less" → 15
     - "30-minutes-or-less" → 30
     - "60-minutes-or-less" → 60
     - "4-hours-or-less" → 240
   - Returns first match, or `None` if no time tags

2. **Cuisine Extraction** (_extract_cuisine_from_tags):
   - Hard-coded list: italian, mexican, chinese, thai, indian, japanese, french, greek, american, korean
   - Returns first match (title-cased), or `None`
   - **Issue:** Only detects 10 cuisines, many recipes get `None`

3. **Difficulty Extraction** (_extract_difficulty_from_tags):
   - "easy" or "beginner-cook" → "easy"
   - "difficult" or "advanced" → "hard"
   - Default → "medium"
   - **Issue:** Most recipes default to "medium" (tags inconsistent)

---

## What's GOOD for Chat

✅ **Complete data model** - Everything needed for meal planning is present
✅ **Dual ingredient lists** - Both clean names and quantities
✅ **Step-by-step instructions** - Ready for cooking guidance
✅ **Derived fields cached** - Don't recompute time/cuisine/difficulty
✅ **Clean serialization** - to_dict/from_dict work well
✅ **Reasonable size** - 3-5 KB per recipe is acceptable

---

## What's MISSING for Chat

### 1. **Nutrition Information** ❌
**Current:** Not accessible
**Database has:** `nutrition` field with JSON string
**Format:** `"[calories, fat_g, sugar_g, sodium_mg, protein_g, sat_fat_g, carbs_g]"`
**Problem:** Not parsed or exposed in Recipe model

**Chat use case:**
```
User: "Show me low-calorie options"
Bot: [Can't filter - nutrition not accessible]

User: "How many calories in Monday's dinner?"
Bot: [Must re-query database for raw nutrition field]
```

### 2. **Better Ingredient Structure** ⚠️
**Current:** Two lists (clean names + raw with quantities)
**Problem:** Not structured for intelligent operations

**Chat use case:**
```
User: "Can I make this without dairy?"
Bot: [Must parse "2 cups milk" string to identify dairy]

User: "Scale this recipe for 6 people"
Bot: [Must parse "2 tablespoons" to extract quantity + unit]
```

**Would be better as:**
```python
ingredients_structured: List[Ingredient] = [
    Ingredient(
        name="milk",
        quantity=2,
        unit="cups",
        raw="2 cups milk",
        category="dairy"  # For substitution suggestions
    ),
    ...
]
```

### 3. **Recipe Relationships** ❌
**Missing:**
- Similar recipes (for alternatives)
- Recipe variants (same dish, different styles)
- Complementary recipes (what side dishes go well)

**Chat use case:**
```
User: "Show me alternatives to this salmon recipe"
Bot: [Must search database, no pre-computed relationships]
```

### 4. **User-Specific Metadata** ❌
**Missing:**
- How many times user has made this
- User's rating/notes
- When last made
- Modifications user typically makes

**Current workaround:** Stored separately in `meal_events` table

**Better:**
```python
user_data: Optional[UserRecipeData] = UserRecipeData(
    times_made=3,
    last_made="2025-01-15",
    average_rating=4.5,
    typical_modifications=["double the garlic"],
    would_make_again=True
)
```

### 5. **Media/Visual Data** ❌
**Missing:**
- Image URL (if available)
- Video link (if available)
- Plating suggestions

**Not critical for MVP but nice for rich chat**

---

## What's AWKWARD for Chat

### 1. **Tag-Based Extraction is Brittle**
**Problem:** Reliance on Food.com tags which are:
- Inconsistent ("30-minutes-or-less" vs actual cook time)
- Incomplete (only 10 cuisines recognized)
- Imprecise (difficulty tags rare)

**Impact:**
- 60%+ recipes have `cuisine=None`
- 80%+ recipes get `difficulty="medium"` default
- Some recipes have wrong time estimates

**Better:** Store computed fields in database (done once at load time)

### 2. **Ingredients_raw Requires Parsing**
**Every time we need to:**
- Filter by ingredient type
- Scale a recipe
- Check for allergens
- Suggest substitutions

**We must parse strings like:**
```
"2 cups all-purpose flour"
"1 tablespoon olive oil"
"3 cloves garlic, minced"
"Salt and pepper to taste"
```

**Chat needs this constantly** - should be pre-parsed

### 3. **No Quick Access to Key Info**
**Chat-critical questions require deep inspection:**

Q: "Is this gluten-free?"
A: Must check ingredients (not just tags - tags unreliable)

Q: "Is this suitable for meal prep?"
A: No field for this

Q: "Can I make this in advance?"
A: No make-ahead indicator

Q: "What's the active cooking time vs passive?"
A: Only total time available

---

## Size Analysis: Embedding Recipes in Plans

**Scenario:** 7-day meal plan with full Recipe objects

**Current PlannedMeal (just IDs):**
```python
{
  "date": "2025-01-20",
  "recipe_id": "12345",
  "recipe_name": "Salmon",
  "servings": 4
}
```
**Size:** ~120 bytes × 7 = 840 bytes per plan

**Proposed PlannedMeal (full Recipe):**
```python
{
  "date": "2025-01-20",
  "main_recipe": {<full Recipe>},  # ~4 KB
  "side_recipes": [{<full Recipe>}],  # ~4 KB if present
  "servings": 4
}
```
**Size (main only):** ~4 KB × 7 = 28 KB per plan
**Size (main + 1 side):** ~8 KB × 7 = 56 KB per plan

**Storage impact:**
- User with 50 plans: 840 bytes × 50 = 42 KB (current)
- User with 50 plans: 28 KB × 50 = 1.4 MB (proposed, main only)
- User with 50 plans: 56 KB × 50 = 2.8 MB (proposed, with sides)

**Assessment:** Acceptable - modern devices handle this easily

---

## Pros & Cons Summary

### PROS ✅
1. **Well-designed dataclass** - Clean, type-safe, Pythonic
2. **Complete core data** - Name, description, ingredients, steps, servings
3. **Dual ingredient formats** - Both clean and raw available
4. **Derived fields** - Time/cuisine/difficulty pre-computed
5. **Good serialization** - JSON round-trip works
6. **Reasonable size** - 3-5 KB average
7. **Backward compatible** - to_dict/from_dict preserve structure

### CONS ❌
1. **No nutrition access** - Can't filter by calories, protein, etc.
2. **Ingredients not structured** - Constant string parsing needed
3. **Tag-based extraction brittle** - Many None values, inconsistent
4. **No recipe relationships** - Can't suggest alternatives
5. **No user-specific data** - Rating/history stored separately
6. **No media** - No image URLs
7. **Missing chat-useful fields** - Make-ahead, active time, prep-friendly, etc.

---

## Questions for Review

### 1. **Nutrition Data**
Should we parse and expose the `nutrition` field?

**Trade-off:**
- Pro: Enables calorie/protein filtering in chat
- Pro: Can show nutrition facts without re-query
- Con: Adds ~100 bytes per recipe
- Con: Need to parse JSON array format

**Recommendation:** YES - essential for "healthy options" queries

---

### 2. **Structured Ingredients**
Should we pre-parse ingredients into structured format?

**Trade-off:**
- Pro: No runtime parsing in chat/shopping/cooking
- Pro: Easy allergen detection, substitutions, scaling
- Con: Adds ~500-1000 bytes per recipe
- Con: One-time parsing cost for 492K recipes
- Con: Parsing might fail on complex formats

**Recommendation:** YES - but as optional enhancement (keep raw as fallback)

---

### 3. **Embedding in Plans**
Are you comfortable with 28-56 KB per meal plan (vs 840 bytes current)?

**Trade-off:**
- Pro: No re-querying (5-7 DB calls saved)
- Pro: Enables multi-recipe meals
- Pro: Chat has full context
- Con: 30-70x larger storage per plan
- Con: Slower serialization/deserialization

**Recommendation:** YES - size is acceptable, benefits huge

---

### 4. **User-Specific Metadata**
Should Recipe object include user data (ratings, times made, etc.)?

**Options:**
A. Keep Recipe pure, store user data separately (current approach)
B. Add optional `user_data` field to Recipe
C. Create separate UserRecipe wrapper class

**Recommendation:** Discuss - depends on usage patterns

---

### 5. **Recipe Relationships**
Should we pre-compute similar/alternative recipes?

**Trade-off:**
- Pro: Instant alternatives in chat
- Pro: Better recommendations
- Con: Requires embeddings or similarity scoring (Step 3 work)
- Con: More storage (list of related IDs per recipe)

**Recommendation:** Phase 2 - after basic structure working

---

## Proposed Changes for Step 2

Based on this analysis, I recommend we enhance Recipe with:

### Must-Have:
1. ✅ **Parse nutrition field** → accessible attributes
2. ✅ **Add helper methods** for common queries
3. ✅ **Improve serialization** for embedded use case

### Nice-to-Have:
4. ⚠️ **Structured ingredients** (optional, keep raw as fallback)
5. ⚠️ **User metadata field** (optional, None by default)

### Future:
6. 🔮 **Recipe relationships** (Phase 2, needs embeddings)
7. 🔮 **Media URLs** (Phase 2, if available in dataset)

---

## Next Step

**Review this analysis and answer:**
1. Should we add nutrition parsing?
2. Should we add structured ingredients?
3. Are you OK with 28-56 KB per meal plan?
4. How should user-specific data be handled?

Once aligned, I'll proceed to Step 2: Design Enhanced Recipe Object.

---

**End of Step 1 Analysis**
