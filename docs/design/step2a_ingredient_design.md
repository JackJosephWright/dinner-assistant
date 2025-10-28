# Step 2a: Ingredient Data Structure Design

**Date:** 2025-10-28
**Status:** Design in Progress - Awaiting Review
**Purpose:** Define structured format for pre-parsed recipe ingredients

---

## Design Proposal

### Core Ingredient Dataclass

```python
@dataclass
class Ingredient:
    """A single ingredient with parsed and enriched data."""

    # ===== ORIGINAL DATA (Always Preserved) =====
    raw: str
    # Example: "2 cups all-purpose flour, sifted"
    # JUSTIFICATION: Always keep original for display and fallback

    # ===== PARSED COMPONENTS =====
    quantity: Optional[float] = None
    # Example: 2.0
    # JUSTIFICATION: Numeric for scaling (multiply by scale_factor)
    # Optional because: "salt to taste" has no quantity

    unit: Optional[str] = None
    # Example: "cups"
    # JUSTIFICATION: String to preserve variety (cups, tablespoons, oz, lb, whole, etc.)
    # Optional because: "3 eggs" has no unit (implied "whole")

    name: str = ""
    # Example: "flour"
    # JUSTIFICATION: Core ingredient identifier (NOT optional - even "salt to taste" → "salt")

    # ===== MODIFIERS & PREPARATION =====
    modifier: Optional[str] = None
    # Example: "all-purpose"
    # JUSTIFICATION: Distinguishes types (all-purpose vs bread flour, fresh vs dried herbs)

    preparation: Optional[str] = None
    # Example: "sifted"
    # JUSTIFICATION: Important for substitutions ("minced garlic" ≠ "whole garlic cloves")

    # ===== ENRICHED METADATA =====
    category: str = "other"
    # Example: "baking"
    # Options: produce, meat, dairy, seafood, baking, pantry, condiments, frozen, beverages, other
    # JUSTIFICATION: For shopping list organization (group by store section)

    allergens: List[str] = field(default_factory=list)
    # Example: ["gluten"]
    # Common: gluten, dairy, eggs, nuts, soy, fish, shellfish, sesame
    # JUSTIFICATION: Instant allergen filtering in chat ("no dairy recipes")

    substitutable: bool = True
    # Example: True
    # JUSTIFICATION: Some ingredients can't be substituted (e.g., "water" in bread)
    #                Helps chat know when to suggest alternatives

    # ===== PARSING METADATA =====
    confidence: float = 1.0
    # Range: 0.0 to 1.0
    # Example: 0.95 for "2 cups flour", 0.3 for "salt and pepper to taste"
    # JUSTIFICATION: Know when to trust parsed data vs fall back to raw string

    parse_method: str = "auto"
    # Options: "auto" (parsed), "manual" (hand-corrected), "fallback" (parsing failed)
    # JUSTIFICATION: Track data quality, identify patterns for improvement
```

---

## Design Decisions with Justifications

### Decision 1: `quantity` as Optional[float]

**Options considered:**
1. `float` (required) - Use 0 or 1 as default
2. `Optional[float]` - Can be None
3. `Union[float, str]` - Support "1/2" as string

**CHOSEN:** `Optional[float]` (option 2)

**Justification:**
- ✅ "Salt to taste" genuinely has no quantity → None is accurate
- ✅ "A pinch of" → None is better than arbitrary 0
- ✅ Math operations (scaling) clean: `if qty is not None: scaled = qty * factor`
- ✅ Easy to detect: "has measurable quantity" vs "to taste"
- ❌ Against option 1: 0 is ambiguous (no quantity? or literally zero?)
- ❌ Against option 3: "1/2" should be parsed to 0.5 for math

**Edge cases:**
```python
"2 cups flour" → quantity=2.0 ✓
"salt to taste" → quantity=None ✓
"1/2 cup butter" → quantity=0.5 ✓ (parser handles fractions)
```

---

### Decision 2: `unit` as Optional[str] (not Enum)

**Options considered:**
1. `Enum` with predefined units (cup, tablespoon, oz, etc.)
2. `Optional[str]` - Free text
3. `Optional[UnitType]` - Custom class with conversions

**CHOSEN:** `Optional[str]` (option 2)

**Justification:**
- ✅ Food.com has 100+ unit variations (tsp, t, teaspoon, tspn)
- ✅ International recipes: ml, grams, litres
- ✅ Uncommon units: "dash", "pinch", "handful"
- ✅ Flexibility for future: keep original, normalize later
- ✅ Optional: "3 eggs" has no unit (None is correct)
- ❌ Against option 1: Too restrictive, would reject valid recipes
- ❌ Against option 3: Over-engineering for MVP

**Future enhancement:** Add `normalized_unit` field later for conversions

**Edge cases:**
```python
"2 cups flour" → unit="cups" ✓
"3 eggs" → unit=None ✓
"2 T butter" → unit="T" ✓ (keep original, can normalize later)
```

---

### Decision 3: `name` as str (NOT Optional)

**Options considered:**
1. `str` (required) - Every ingredient must have a name
2. `Optional[str]` - Can be None

**CHOSEN:** `str` required (option 1), empty string as default

**Justification:**
- ✅ Every ingredient has SOMETHING to call it
- ✅ "salt and pepper to taste" → name="salt and pepper"
- ✅ Forces parser to extract at minimum the ingredient name
- ✅ Makes code simpler (no None checks for basic display)
- ❌ Against option 2: What's an ingredient without a name? Invalid data.

**Fallback strategy:**
```python
# If parsing completely fails
Ingredient(
    raw="??? weird text",
    name="unknown ingredient",  # Better than None
    confidence=0.0
)
```

---

### Decision 4: Separate `modifier` and `preparation`

**Options considered:**
1. Single `details` field - "all-purpose, sifted"
2. Separate `modifier` and `preparation` fields
3. List of tags: `tags=["all-purpose", "sifted"]`

**CHOSEN:** Separate fields (option 2)

**Justification:**
- ✅ Modifier = intrinsic type ("all-purpose flour" is different ingredient than "bread flour")
- ✅ Preparation = how to prep ("sifted" is user action, not ingredient type)
- ✅ Substitution logic: Match on name+modifier, ignore preparation
- ✅ Clear semantics: "what it is" vs "what you do to it"
- ❌ Against option 1: Loses semantic meaning, can't distinguish type from prep
- ❌ Against option 3: Order matters, tags lose structure

**Examples:**
```python
"2 cups all-purpose flour, sifted"
→ name="flour", modifier="all-purpose", preparation="sifted"

"3 cloves garlic, minced"
→ name="garlic", modifier=None, preparation="minced"

"1 lb fresh salmon"
→ name="salmon", modifier="fresh", preparation=None

"1 cup dried cranberries, chopped"
→ name="cranberries", modifier="dried", preparation="chopped"
```

---

### Decision 5: `category` for shopping sections

**Options considered:**
1. No category - organize by recipe
2. Simple categories (10 sections)
3. Hierarchical taxonomy (produce→fruit→berries)

**CHOSEN:** Simple categories (option 2)

**Justification:**
- ✅ Matches physical store layout (where users shop)
- ✅ 10 categories cover 95% of ingredients
- ✅ Easy to map and maintain
- ✅ Directly usable for shopping list organization
- ❌ Against option 1: Shopping list would be chaotic
- ❌ Against option 3: Over-complicated, stores vary too much

**Categories chosen (10):**
```python
CATEGORIES = [
    "produce",      # Fruits, vegetables, herbs
    "meat",         # Beef, pork, poultry
    "seafood",      # Fish, shellfish
    "dairy",        # Milk, cheese, yogurt, butter
    "baking",       # Flour, sugar, baking powder
    "pantry",       # Oils, vinegar, canned goods
    "condiments",   # Sauces, spices, seasonings
    "frozen",       # Frozen vegetables, ice cream
    "beverages",    # Juice, soda, alcohol
    "other"         # Catch-all
]
```

**Why these?** Based on typical grocery store sections

---

### Decision 6: `allergens` as List[str]

**Options considered:**
1. `List[str]` - ["gluten", "dairy"]
2. `Set[str]` - {"gluten", "dairy"}
3. `AllergenFlags` - Enum with bitwise flags
4. `bool` fields - is_gluten, is_dairy, etc.

**CHOSEN:** `List[str]` (option 1)

**Justification:**
- ✅ Simple, readable, serializes to JSON easily
- ✅ Extensible (add new allergens without code changes)
- ✅ Empty list = no allergens (clear semantic)
- ✅ Chat-friendly: `if "dairy" in ing.allergens`
- ❌ Against option 2: Sets don't serialize to JSON cleanly
- ❌ Against option 3: Over-engineering, limited to fixed set
- ❌ Against option 4: Every new allergen = code change

**Allergen list (8 major + common):**
```python
COMMON_ALLERGENS = [
    "gluten",     # Wheat, barley, rye
    "dairy",      # Milk products
    "eggs",
    "peanuts",
    "tree-nuts",  # Almonds, walnuts, etc.
    "soy",
    "fish",
    "shellfish",
    "sesame",
]
```

**Examples:**
```python
"2 cups flour" → allergens=["gluten"]
"3 eggs" → allergens=["eggs"]
"1 cup almond milk" → allergens=["tree-nuts"]
"2 tbsp butter" → allergens=["dairy"]
"1 lb salmon" → allergens=["fish"]
```

---

### Decision 7: `confidence` as float (0.0 to 1.0)

**Options considered:**
1. `float` (0.0 to 1.0) - Continuous confidence score
2. `Enum` - HIGH, MEDIUM, LOW
3. No confidence tracking

**CHOSEN:** `float` (option 1)

**Justification:**
- ✅ Parser libraries return confidence scores (e.g., 0.85)
- ✅ Can threshold: `if conf > 0.8: trust_it`
- ✅ Useful for debugging (find low-confidence parses to improve)
- ✅ Gradual fallback: try structured, then semi-structured, then raw
- ❌ Against option 2: Loses precision (is 0.75 HIGH or MEDIUM?)
- ❌ Against option 3: Can't tell good parses from bad ones

**Thresholds:**
```python
confidence >= 0.9: ✅ High quality, trust fully
confidence >= 0.7: ⚠️ Good, use with fallback available
confidence >= 0.5: ⚠️ Questionable, prefer raw for display
confidence <  0.5: ❌ Low quality, use raw string only
```

---

### Decision 8: `parse_method` tracking

**Options considered:**
1. Track parse_method ("auto", "manual", "fallback")
2. Don't track (confidence is enough)

**CHOSEN:** Track parse_method (option 1)

**Justification:**
- ✅ Debug: Identify which parser worked/failed
- ✅ Quality: Know which recipes need manual review
- ✅ Improvement: Find patterns in fallbacks
- ✅ Trust: "manual" > "auto" > "fallback"
- ❌ Against option 2: Harder to improve parser without this data

**Values:**
```python
"auto"     # Successfully parsed by ingredient-parser library
"manual"   # Hand-corrected or validated by human
"fallback" # Parsing failed, minimal structure created
```

---

## Complete Example

### Input (raw string):
```
"2 cups all-purpose flour, sifted"
```

### Output (Ingredient object):
```python
Ingredient(
    raw="2 cups all-purpose flour, sifted",
    quantity=2.0,
    unit="cups",
    name="flour",
    modifier="all-purpose",
    preparation="sifted",
    category="baking",
    allergens=["gluten"],
    substitutable=True,
    confidence=0.95,
    parse_method="auto"
)
```

### Serialized (JSON):
```json
{
  "raw": "2 cups all-purpose flour, sifted",
  "quantity": 2.0,
  "unit": "cups",
  "name": "flour",
  "modifier": "all-purpose",
  "preparation": "sifted",
  "category": "baking",
  "allergens": ["gluten"],
  "substitutable": true,
  "confidence": 0.95,
  "parse_method": "auto"
}
```

**Size:** ~220 bytes (vs ~35 bytes for raw string)

---

## Edge Cases Handled

### Case 1: "Salt to taste"
```python
Ingredient(
    raw="salt to taste",
    quantity=None,        # No measurable quantity
    unit=None,
    name="salt",
    modifier=None,
    preparation="to taste",
    category="condiments",
    allergens=[],
    substitutable=False,  # Can't omit salt in most recipes
    confidence=0.6,       # Parsing is straightforward but quantity is vague
    parse_method="auto"
)
```

### Case 2: "3 eggs"
```python
Ingredient(
    raw="3 eggs",
    quantity=3,
    unit=None,           # Implied "whole"
    name="eggs",
    modifier=None,
    preparation=None,
    category="dairy",
    allergens=["eggs"],
    substitutable=True,
    confidence=0.98,
    parse_method="auto"
)
```

### Case 3: "1/2 cup butter, softened"
```python
Ingredient(
    raw="1/2 cup butter, softened",
    quantity=0.5,        # Fraction parsed
    unit="cup",
    name="butter",
    modifier=None,
    preparation="softened",
    category="dairy",
    allergens=["dairy"],
    substitutable=True,
    confidence=0.95,
    parse_method="auto"
)
```

### Case 4: Parsing fails
```python
Ingredient(
    raw="some weird ingredient format {{?}}",
    quantity=None,
    unit=None,
    name="weird ingredient",  # Best guess
    modifier=None,
    preparation=None,
    category="other",
    allergens=[],
    substitutable=True,
    confidence=0.1,       # Very low - don't trust
    parse_method="fallback"
)
```

---

## Usage Examples

### Example 1: Shopping List Generation
```python
# Group ingredients by category
by_section = defaultdict(list)
for meal in plan.meals:
    for ing in meal.main_recipe.ingredients_structured:
        by_section[ing.category].append(ing)

# No parsing needed! Already have category
```

### Example 2: Recipe Scaling
```python
def scale_recipe(recipe: Recipe, scale_factor: float) -> Recipe:
    scaled = recipe.copy()
    scaled.ingredients_structured = [
        ing.copy(
            quantity=ing.quantity * scale_factor if ing.quantity else None,
            raw=f"{ing.quantity * scale_factor if ing.quantity else ''} {ing.unit or ''} {ing.name}".strip()
        )
        for ing in recipe.ingredients_structured
    ]
    return scaled

# scale_recipe(salmon_recipe, 3.0) # Serves 2 → Serves 6
```

### Example 3: Allergen Filtering
```python
# User: "Show me dairy-free recipes"
dairy_free = [
    r for r in recipes
    if not any("dairy" in ing.allergens for ing in r.ingredients_structured)
]
```

### Example 4: Substitution Suggestion
```python
# User: "Can I substitute the butter?"
butter = next(ing for ing in recipe.ingredients_structured if ing.name == "butter")

if butter.substitutable:
    # Know it's dairy, know the quantity
    suggest_dairy_free_fat(
        quantity=butter.quantity,
        unit=butter.unit,
        category=butter.category
    )
    # → "Use 1/2 cup coconut oil or olive oil"
```

---

## Questions for Review

### 1. Field Completeness
Are there any fields missing that would be useful for:
- Chat queries?
- Shopping list?
- Recipe scaling?
- Substitutions?

**Consider adding:**
- `is_optional: bool` - Can this ingredient be omitted?
- `typical_brands: List[str]` - "Hellmann's mayo", etc.?
- `storage_location: str` - "pantry", "fridge", "freezer"?

### 2. Allergen Coverage
Is the 9-allergen list sufficient, or should we add more?

**Candidates:**
- sulfites (wine, dried fruit)
- nightshades (tomatoes, peppers) - for some diets
- corn
- citrus

### 3. Category Granularity
Are 10 categories enough? Too many?

**Alternative:** 15 categories (split produce into fruit/vegetables/herbs)?

### 4. Confidence Thresholds
Do the confidence thresholds make sense?
- 0.9+ = trust fully
- 0.7-0.9 = use with caution
- 0.5-0.7 = questionable
- <0.5 = use raw only

### 5. Size Trade-off
220 bytes per ingredient vs 35 bytes raw.

**Per recipe:** 10 ingredients × 220 = 2.2 KB
**Database:** 492K recipes × 2.2 KB = 1.08 GB additional

**Acceptable?**

---

## Next Steps

Once approved:
1. Implement Ingredient dataclass in models.py
2. Add serialization (to_dict/from_dict)
3. Create ingredient database mappings (category, allergens)
4. Move to Step 2b: Create enrichment script

---

**🛑 CHECKPOINT: Please Review**

**Questions:**
1. Do these design decisions make sense?
2. Any fields missing or unnecessary?
3. Are the justifications convincing?
4. Any concerns about size/performance?
5. Ready to proceed with implementation?

**End of Step 2a Design**
