# Step 2e: Enhanced Recipe Object Design

**Date:** 2025-10-28
**Status:** In Progress
**Decision:** Design Recipe object to utilize structured ingredients

---

## Current State

After enrichment, we now have:
- ✅ 5,000 recipes with `ingredients_structured` in database
- ✅ Structured data includes: quantity, unit, name, category, allergens, etc.
- ✅ Original `ingredients_raw` preserved as fallback

---

## Design Goals

### 1. Transparent Access
Recipe object should work whether ingredients are enriched or not:
```python
recipe = db.get_recipe("12345")

# Works regardless of enrichment status
for ingredient in recipe.get_ingredients():
    print(f"{ingredient.quantity} {ingredient.unit} {ingredient.name}")
```

### 2. Performance
Avoid parsing at runtime when structured data exists:
```python
# Bad: Parse every time
ingredients = [parse(raw) for raw in recipe.ingredients_raw]

# Good: Use pre-parsed when available
ingredients = recipe.ingredients_structured or [parse(raw) for raw in recipe.ingredients_raw]
```

### 3. Rich Operations
Enable operations that require structured data:
```python
# Shopping list generation
recipe.get_shopping_ingredients_by_category()
# Returns: {"produce": [...], "meat": [...], "dairy": [...]}

# Allergen filtering
recipe.has_allergen("gluten")
# Returns: True/False

# Recipe scaling
recipe.scale_ingredients(servings=4)
# Returns: new Recipe with scaled quantities
```

---

## Enhanced Recipe Class Design

```python
from dataclasses import dataclass, field
from typing import List, Optional, Dict
from enum import Enum

@dataclass
class Ingredient:
    """Structured ingredient data."""
    raw: str
    quantity: Optional[float] = None
    unit: Optional[str] = None
    name: str = ""
    modifier: Optional[str] = None
    preparation: Optional[str] = None
    category: str = "other"
    allergens: List[str] = field(default_factory=list)
    substitutable: bool = True
    confidence: float = 1.0
    parse_method: str = "auto"

    def __str__(self) -> str:
        """Human-readable string."""
        if self.quantity and self.unit:
            return f"{self.quantity} {self.unit} {self.name}"
        elif self.quantity:
            return f"{self.quantity} {self.name}"
        else:
            return self.name

    def scale(self, factor: float) -> 'Ingredient':
        """Scale ingredient quantity by factor."""
        if self.quantity is None:
            return self  # Can't scale "salt to taste"

        return Ingredient(
            raw=f"{self.quantity * factor} {self.unit or ''} {self.name}",
            quantity=self.quantity * factor,
            unit=self.unit,
            name=self.name,
            modifier=self.modifier,
            preparation=self.preparation,
            category=self.category,
            allergens=self.allergens.copy(),
            substitutable=self.substitutable,
            confidence=self.confidence,
            parse_method=self.parse_method
        )


@dataclass
class NutritionInfo:
    """Nutrition information per serving."""
    calories: Optional[int] = None
    protein_g: Optional[float] = None
    fat_g: Optional[float] = None
    carbs_g: Optional[float] = None
    fiber_g: Optional[float] = None
    sugar_g: Optional[float] = None
    sodium_mg: Optional[int] = None

    def __str__(self) -> str:
        """Human-readable nutrition summary."""
        parts = []
        if self.calories:
            parts.append(f"{self.calories} cal")
        if self.protein_g:
            parts.append(f"{self.protein_g}g protein")
        if self.carbs_g:
            parts.append(f"{self.carbs_g}g carbs")
        return ", ".join(parts) if parts else "Nutrition info unavailable"


@dataclass
class Recipe:
    """Enhanced recipe with structured ingredients and nutrition."""

    # Core identification
    id: str
    name: str
    description: str

    # Ingredients (dual format)
    ingredients_raw: List[str]  # Original strings with quantities
    ingredients_structured: Optional[List[Ingredient]] = None  # Parsed data

    # Cooking instructions
    steps: List[str] = field(default_factory=list)

    # Serving information
    servings: int = 4
    serving_size: str = "1 serving"

    # Metadata
    tags: List[str] = field(default_factory=list)
    estimated_time: Optional[int] = None  # minutes
    cuisine: Optional[str] = None
    difficulty: str = "medium"  # easy, medium, hard

    # Enhanced data
    nutrition: Optional[NutritionInfo] = None

    # Database metadata
    created_at: Optional[str] = None
    source_url: Optional[str] = None

    def has_structured_ingredients(self) -> bool:
        """Check if recipe has been enriched with structured data."""
        return self.ingredients_structured is not None and len(self.ingredients_structured) > 0

    def get_ingredients(self, prefer_structured: bool = True) -> List[Ingredient]:
        """
        Get ingredients, preferring structured if available.

        Args:
            prefer_structured: If True, return structured; if False, always parse raw

        Returns:
            List of Ingredient objects
        """
        if prefer_structured and self.has_structured_ingredients():
            return self.ingredients_structured

        # Fallback: parse raw ingredients on-the-fly
        from scripts.enrich_recipe_ingredients import SimpleIngredientParser
        parser = SimpleIngredientParser()
        return [parser.parse(raw) for raw in self.ingredients_raw]

    def get_shopping_ingredients_by_category(self) -> Dict[str, List[Ingredient]]:
        """
        Group ingredients by shopping category.

        Returns:
            Dict mapping category → list of ingredients
        """
        ingredients = self.get_ingredients()
        by_category = {}

        for ing in ingredients:
            category = ing.category
            if category not in by_category:
                by_category[category] = []
            by_category[category].append(ing)

        return by_category

    def has_allergen(self, allergen: str) -> bool:
        """
        Check if recipe contains a specific allergen.

        Args:
            allergen: e.g., "gluten", "dairy", "eggs"

        Returns:
            True if allergen present, False otherwise
        """
        if not self.has_structured_ingredients():
            # Can't reliably check without structured data
            return False

        allergen_lower = allergen.lower()
        for ing in self.ingredients_structured:
            if allergen_lower in [a.lower() for a in ing.allergens]:
                return True

        return False

    def get_all_allergens(self) -> List[str]:
        """
        Get all unique allergens in recipe.

        Returns:
            List of allergen names
        """
        if not self.has_structured_ingredients():
            return []

        all_allergens = set()
        for ing in self.ingredients_structured:
            all_allergens.update(ing.allergens)

        return sorted(list(all_allergens))

    def scale_ingredients(self, target_servings: int) -> 'Recipe':
        """
        Create a new recipe with scaled ingredient quantities.

        Args:
            target_servings: Desired number of servings

        Returns:
            New Recipe object with scaled quantities
        """
        if not self.has_structured_ingredients():
            # Can't scale without structured data
            return self

        factor = target_servings / self.servings

        scaled_ingredients = [ing.scale(factor) for ing in self.ingredients_structured]

        # Create new recipe (don't modify original)
        return Recipe(
            id=self.id,
            name=f"{self.name} ({target_servings} servings)",
            description=self.description,
            ingredients_raw=self.ingredients_raw,  # Keep original
            ingredients_structured=scaled_ingredients,
            steps=self.steps,
            servings=target_servings,
            serving_size=self.serving_size,
            tags=self.tags,
            estimated_time=self.estimated_time,
            cuisine=self.cuisine,
            difficulty=self.difficulty,
            nutrition=self.nutrition,
            created_at=self.created_at,
            source_url=self.source_url
        )

    def to_dict(self) -> Dict:
        """
        Convert to dictionary for JSON serialization.

        Returns:
            Dict representation
        """
        data = {
            "id": self.id,
            "name": self.name,
            "description": self.description,
            "ingredients_raw": self.ingredients_raw,
            "steps": self.steps,
            "servings": self.servings,
            "serving_size": self.serving_size,
            "tags": self.tags,
            "estimated_time": self.estimated_time,
            "cuisine": self.cuisine,
            "difficulty": self.difficulty,
            "created_at": self.created_at,
            "source_url": self.source_url
        }

        if self.ingredients_structured:
            data["ingredients_structured"] = [
                ing.__dict__ for ing in self.ingredients_structured
            ]

        if self.nutrition:
            data["nutrition"] = self.nutrition.__dict__

        return data

    @classmethod
    def from_dict(cls, data: Dict) -> 'Recipe':
        """
        Create Recipe from dictionary.

        Args:
            data: Dictionary representation

        Returns:
            Recipe object
        """
        # Parse ingredients_structured if present
        ingredients_structured = None
        if "ingredients_structured" in data and data["ingredients_structured"]:
            ingredients_structured = [
                Ingredient(**ing_data) for ing_data in data["ingredients_structured"]
            ]

        # Parse nutrition if present
        nutrition = None
        if "nutrition" in data and data["nutrition"]:
            nutrition = NutritionInfo(**data["nutrition"])

        return cls(
            id=data["id"],
            name=data["name"],
            description=data["description"],
            ingredients_raw=data["ingredients_raw"],
            ingredients_structured=ingredients_structured,
            steps=data.get("steps", []),
            servings=data.get("servings", 4),
            serving_size=data.get("serving_size", "1 serving"),
            tags=data.get("tags", []),
            estimated_time=data.get("estimated_time"),
            cuisine=data.get("cuisine"),
            difficulty=data.get("difficulty", "medium"),
            nutrition=nutrition,
            created_at=data.get("created_at"),
            source_url=data.get("source_url")
        )

    def __str__(self) -> str:
        """Human-readable recipe summary."""
        return f"{self.name} ({self.servings} servings, {self.estimated_time or '?'} min)"
```

---

## Key Design Decisions

### Decision 1: Optional `ingredients_structured`
**Rationale:** Not all recipes may be enriched (only 5,000 out of 492K currently)

**Fallback strategy:**
- Check `has_structured_ingredients()` before using
- If not available, parse raw on-the-fly (slower but works)
- Never break if enrichment missing

### Decision 2: Dual Ingredient Storage
**Keep both:**
- `ingredients_raw`: Original strings (always present, human-readable)
- `ingredients_structured`: Parsed objects (optional, machine-readable)

**Benefits:**
- Can always fall back to raw
- Structured enables advanced features
- No data loss

### Decision 3: Lazy Parsing Fallback
**If structured not available:**
```python
def get_ingredients(self):
    if self.ingredients_structured:
        return self.ingredients_structured
    else:
        return [parse(raw) for raw in self.ingredients_raw]  # Slow but works
```

**Trade-off:** Slower for non-enriched recipes, but functionality preserved

### Decision 4: Immutable Scaling
**Pattern:**
```python
scaled_recipe = recipe.scale_ingredients(8)  # Returns NEW recipe
# Original recipe unchanged
```

**Rationale:**
- Avoid accidental mutation
- Clearer intent
- Easier to reason about

### Decision 5: Nutrition as Optional NutritionInfo
**Structure:**
```python
nutrition: Optional[NutritionInfo] = None
```

**Rationale:**
- Not all recipes have nutrition data in database
- Separate class keeps Recipe clean
- Can add later without breaking changes

---

## Usage Examples

### Example 1: Load and Display
```python
# Load recipe
recipe = db.get_recipe("12345")

print(recipe.name)
print(f"Servings: {recipe.servings}")
print(f"Time: {recipe.estimated_time} minutes")

# Display ingredients
print("\nIngredients:")
for ing in recipe.get_ingredients():
    print(f"  • {ing}")

# Check allergens
if recipe.has_allergen("gluten"):
    print("⚠️ Contains gluten")
```

### Example 2: Shopping List Generation
```python
# Get ingredients grouped by category
by_category = recipe.get_shopping_ingredients_by_category()

print("Shopping List:")
for category, ingredients in by_category.items():
    print(f"\n{category.upper()}:")
    for ing in ingredients:
        print(f"  □ {ing}")
```

### Example 3: Recipe Scaling
```python
# Original serves 4
recipe = db.get_recipe("12345")
print(f"Original: {recipe.servings} servings")

# Scale to 8 servings
scaled = recipe.scale_ingredients(target_servings=8)
print(f"Scaled: {scaled.servings} servings")

# Compare ingredients
print("\nOriginal flour:")
print(recipe.get_ingredients()[0])  # "2 cups flour"

print("\nScaled flour:")
print(scaled.get_ingredients()[0])  # "4 cups flour"
```

### Example 4: Allergen Filtering
```python
# Filter recipes for dietary needs
recipes = db.search_recipes("pasta")

gluten_free = [
    r for r in recipes
    if not r.has_allergen("gluten")
]

dairy_free = [
    r for r in recipes
    if not r.has_allergen("dairy")
]
```

### Example 5: Serialization (for Embedding)
```python
# Convert to dict for storage in MealPlan
recipe_dict = recipe.to_dict()

# Store in meal plan
meal_plan = {
    "monday_dinner": {
        "recipe": recipe_dict,  # Full recipe embedded
        "date": "2025-10-28",
        "meal_type": "dinner"
    }
}

# Later: Load back
recipe = Recipe.from_dict(meal_plan["monday_dinner"]["recipe"])
```

---

## Database Schema (No Changes Needed!)

Current schema already supports this design:

```sql
-- recipes table
CREATE TABLE recipes (
    id TEXT PRIMARY KEY,
    name TEXT,
    description TEXT,
    ingredients TEXT,           -- Clean ingredient names (for search)
    ingredients_raw TEXT,       -- JSON array: ["2 cups flour", ...]
    ingredients_structured TEXT, -- JSON array: [{quantity: 2, unit: "cup", ...}, ...]
    steps TEXT,                 -- JSON array
    servings INTEGER,
    serving_size TEXT,
    tags TEXT,                  -- JSON array
    estimated_time INTEGER,
    cuisine TEXT,
    difficulty TEXT,
    nutrition TEXT,             -- JSON object (currently null, can populate later)
    created_at TEXT,
    source_url TEXT
);
```

**Key point:** All new fields already exist in database:
- ✅ `ingredients_structured` - Populated for 5,000 recipes
- ✅ `nutrition` - Column exists (currently null, can parse later)

---

## Size Analysis

### Recipe Object Size

**Without structured ingredients:**
```python
recipe = Recipe(
    id="12345",
    name="Pasta Carbonara",
    ingredients_raw=["8 oz pasta", "2 eggs", ...],  # 6 items
    steps=["Boil water", ...],  # 8 steps
    # ... other fields
)

# Estimated: 2-3 KB
```

**With structured ingredients:**
```python
recipe = Recipe(
    # ... same as above ...
    ingredients_structured=[
        Ingredient(raw="8 oz pasta", quantity=8.0, unit="oz", ...),
        Ingredient(raw="2 eggs", quantity=2.0, unit=None, ...),
        # ... 6 items
    ]
)

# Estimated: 3-5 KB (adds ~1-2 KB)
```

**Acceptable for embedding in meal plans!**

---

## Migration Strategy

### Phase 1: Update models.py (This step)
- Add Ingredient class
- Add NutritionInfo class
- Update Recipe class with new methods
- Keep backward compatibility

### Phase 2: Update DatabaseInterface (Next step)
- Modify `get_recipe()` to load structured ingredients
- Parse JSON from `ingredients_structured` column
- Parse JSON from `nutrition` column (if present)

### Phase 3: Update Agents (Later step)
- Shopping agent: use `get_shopping_ingredients_by_category()`
- Planning agent: use `has_allergen()` for filtering
- Scaling: use `scale_ingredients()` when needed

### Phase 4: Update Tests
- Test `has_structured_ingredients()`
- Test `get_ingredients()` with/without structured
- Test `scale_ingredients()`
- Test allergen filtering

---

## Benefits of This Design

### 1. Backward Compatible
✅ Works with non-enriched recipes (falls back to parsing)
✅ Doesn't break existing code
✅ No database migration needed

### 2. Performance Optimized
✅ Use pre-parsed data when available (fast)
✅ Only parse on-the-fly when necessary (slow but works)
✅ No redundant parsing

### 3. Feature Rich
✅ Shopping list generation by category
✅ Allergen detection
✅ Recipe scaling
✅ Nutrition info (when available)

### 4. Clean API
✅ Simple method names
✅ Type hints throughout
✅ Clear fallback behavior
✅ Immutable operations

### 5. Future Proof
✅ Can add more Ingredient fields later
✅ Can populate nutrition data later
✅ Can add more helper methods
✅ Doesn't constrain future changes

---

## Testing Strategy

### Unit Tests to Write

```python
def test_has_structured_ingredients():
    """Test enrichment detection."""
    recipe_enriched = Recipe(..., ingredients_structured=[...])
    assert recipe_enriched.has_structured_ingredients()

    recipe_raw = Recipe(..., ingredients_structured=None)
    assert not recipe_raw.has_structured_ingredients()

def test_get_ingredients_with_structured():
    """Test getting ingredients from enriched recipe."""
    recipe = Recipe(
        ingredients_structured=[
            Ingredient(quantity=2, unit="cup", name="flour")
        ]
    )
    ingredients = recipe.get_ingredients()
    assert len(ingredients) == 1
    assert ingredients[0].name == "flour"

def test_get_ingredients_fallback():
    """Test parsing fallback for non-enriched recipe."""
    recipe = Recipe(
        ingredients_raw=["2 cups flour"],
        ingredients_structured=None
    )
    ingredients = recipe.get_ingredients()
    assert len(ingredients) == 1
    # Should have parsed raw string

def test_scale_ingredients():
    """Test recipe scaling."""
    recipe = Recipe(
        servings=4,
        ingredients_structured=[
            Ingredient(quantity=2, unit="cup", name="flour")
        ]
    )
    scaled = recipe.scale_ingredients(8)
    assert scaled.servings == 8
    assert scaled.ingredients_structured[0].quantity == 4.0

def test_has_allergen():
    """Test allergen detection."""
    recipe = Recipe(
        ingredients_structured=[
            Ingredient(name="flour", allergens=["gluten"])
        ]
    )
    assert recipe.has_allergen("gluten")
    assert not recipe.has_allergen("dairy")

def test_get_shopping_ingredients_by_category():
    """Test category grouping."""
    recipe = Recipe(
        ingredients_structured=[
            Ingredient(name="flour", category="baking"),
            Ingredient(name="butter", category="dairy"),
            Ingredient(name="onion", category="produce")
        ]
    )
    by_category = recipe.get_shopping_ingredients_by_category()
    assert "baking" in by_category
    assert "dairy" in by_category
    assert "produce" in by_category
    assert len(by_category["baking"]) == 1

def test_serialization():
    """Test to_dict/from_dict round-trip."""
    original = Recipe(
        id="123",
        name="Test Recipe",
        ingredients_raw=["2 cups flour"],
        ingredients_structured=[
            Ingredient(quantity=2, unit="cup", name="flour")
        ]
    )

    # Serialize
    data = original.to_dict()

    # Deserialize
    restored = Recipe.from_dict(data)

    assert restored.id == original.id
    assert restored.name == original.name
    assert len(restored.ingredients_structured) == 1
```

---

## Open Questions

### Q1: Should we parse nutrition on load?
**Current:** `nutrition` stored as JSON string in DB, loaded as NutritionInfo object

**Options:**
- A. Parse on load (adds overhead)
- B. Lazy parse on access (more complex)
- C. Keep as dict (less type safety)

**Recommendation:** Parse on load (A) - overhead minimal, cleaner API

### Q2: Should scaling be immutable?
**Current:** Yes, returns new Recipe

**Alternative:** Mutate in place

**Recommendation:** Keep immutable - safer, more predictable

### Q3: Should we cache parsed ingredients?
**Current:** Parse raw ingredients on every `get_ingredients()` call if not enriched

**Alternative:** Cache parsed result

**Recommendation:** Not needed - prefer enriching more recipes over caching

---

## Next Steps

**Step 3: Implement Enhanced Recipe**
1. Update `src/data/models.py` with new classes
2. Test with existing enriched recipes (5,000)
3. Verify backward compatibility
4. Write unit tests

**Then Step 4: Design PlannedMeal**
- Use new Recipe object
- Embed full recipe (not just ID)
- Support multiple recipes (main + sides)

---

**End of Step 2e Enhanced Recipe Design**
