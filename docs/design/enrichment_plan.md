# Dataset Enrichment Plan

**Goal:** Pre-parse and enrich all recipe ingredients for optimal chat/shopping/scaling performance

---

## Refined Step-by-Step Plan

### Step 2a: Design Ingredient Data Structure (30 min)
**Deliverable:** Ingredient dataclass definition

**What I'll create:**
```python
@dataclass
class Ingredient:
    raw: str                          # Original: "2 cups all-purpose flour"
    quantity: Optional[float]         # 2.0
    unit: Optional[str]               # "cups"
    name: str                         # "flour"
    modifier: Optional[str]           # "all-purpose"
    category: str                     # "baking" (for shopping sections)
    allergens: List[str]              # ["gluten"]
    substitutable: bool               # True
    confidence: float                 # 0.95 (parser confidence)
```

**Checkpoint:** Review structure, discuss fields

---

### Step 2b: Create Enrichment Script (1-1.5 hours)
**Deliverable:** `scripts/enrich_recipe_ingredients.py`

**What it does:**
1. Uses `ingredient-parser-py` library (or similar)
2. Parses each ingredient string
3. Looks up category from mapping dict
4. Identifies allergens from database
5. Stores enriched data back to recipes.db

**Test on 10 sample recipes first**

**Checkpoint:** Review script, test on samples, verify output

---

### Step 2c: Test on Sample Dataset (30 min)
**Deliverable:** Enrichment results for 100 diverse recipes

**What to verify:**
- Parsing accuracy (>95% clean parses)
- Category assignments correct
- Allergen detection working
- Edge cases handled (e.g., "salt to taste", "1/2 cup")

**Checkpoint:** Review sample results, adjust parser if needed

---

### Step 2d: Run Full Enrichment (30-60 min runtime)
**Deliverable:** recipes.db with `ingredients_structured` column populated

**Process:**
```bash
python scripts/enrich_recipe_ingredients.py --full

# Progress bar
# Fallback handling for failed parses
# Summary stats at end
```

**Checkpoint:** Review stats (parse success rate, common failures)

---

### Step 2e: Design Enhanced Recipe Object (45 min)
**Deliverable:** Updated Recipe class design with structured ingredients

**Changes:**
```python
@dataclass
class Recipe:
    # ... existing fields ...

    # NEW: Structured ingredients (enriched)
    ingredients_structured: List[Ingredient]

    # NEW: Parsed nutrition
    nutrition: Optional[Nutrition]

    # Helper methods
    def get_ingredient_by_name(self, name: str) -> Optional[Ingredient]
    def has_allergen(self, allergen: str) -> bool
    def scale(self, scale_factor: float) -> Recipe
```

**Checkpoint:** Review design, approve before implementation

---

### Step 3: Implement Enhanced Recipe (1-2 hours)
**Deliverable:** Updated models.py with:
- Ingredient dataclass
- Nutrition dataclass
- Enhanced Recipe class
- All serialization working
- Tests passing

**Checkpoint:** Test all functionality, verify serialization

---

## Key Design Decisions

### 1. **Ingredient Parsing Library**
**Options:**
- `ingredient-parser-py` (pip package, good accuracy)
- `ingredient-parser` (Node.js, would need wrapper)
- Custom regex-based (simpler but less accurate)

**Recommendation:** Start with `ingredient-parser-py`, fallback to simple parser if needed

---

### 2. **Category Mapping**
**Source:** Extend existing shopping_tools.py category_mappings

**Current categories:**
- produce
- meat
- dairy
- pantry
- frozen
- beverages
- baking
- condiments
- other

**Action:** Expand to ~1000 common ingredients

---

### 3. **Allergen Database**
**Common allergens to detect:**
- gluten (wheat, barley, rye)
- dairy (milk, cheese, butter, cream)
- eggs
- nuts (peanuts, tree nuts)
- soy
- fish
- shellfish
- sesame

**Source:** Create mapping dict: ingredient name → allergen list

---

### 4. **Confidence Scoring**
**When to trust structured data:**
- confidence >= 0.8: Use structured
- confidence < 0.8: Fallback to raw string

**Examples:**
- "2 cups flour" → confidence: 0.95 ✅
- "salt and pepper to taste" → confidence: 0.3 ⚠️ (use raw)

---

### 5. **Storage Strategy**
**Add to recipes.db:**
```sql
ALTER TABLE recipes ADD COLUMN ingredients_structured TEXT;
-- Store as JSON array
```

**Why not separate table:**
- Keeps recipe data together
- Simpler serialization
- Faster loading (one query vs joins)

---

## Timeline

**Total added to original plan: ~4-5 hours**

- Step 2a (Design Ingredient): 30 min
- Step 2b (Create script): 1-1.5 hours
- Step 2c (Test samples): 30 min
- Step 2d (Full enrichment): 30-60 min (mostly automated)
- Step 2e (Design Recipe): 45 min

**Worth it because:**
- Saves hours in shopping/scaling implementation
- Enables powerful chat features
- Makes everything downstream simpler

---

## Success Criteria

After enrichment complete:
✅ 95%+ recipes have structured ingredients
✅ Parse confidence tracked
✅ Shopping categories assigned
✅ Common allergens identified
✅ Database size reasonable (<4 GB)
✅ All data reversible (raw strings preserved)

---

## Rollback Plan

If enrichment fails or has issues:
1. Raw ingredients always preserved
2. Can drop `ingredients_structured` column
3. Code falls back to raw parsing
4. No data loss

---

**Ready to start Step 2a: Design Ingredient Structure?**
