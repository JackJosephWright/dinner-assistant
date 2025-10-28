# Step 4: PlannedMeal Object Design

**Created:** 2025-10-28
**Status:** Design Phase
**Purpose:** Define PlannedMeal structure for embedding full Recipe objects

---

## Overview

The `PlannedMeal` object represents a single meal scheduled for a specific date/time. It **embeds the full Recipe object(s)** rather than just storing recipe IDs. This enables:

- **Offline access** - Full recipe data available without database queries
- **Versioning** - Meal plans capture recipe state at planning time
- **Performance** - No need to re-query database when loading plans
- **Scaling support** - Servings can be adjusted independently per meal

---

## Current Implementation

The existing `PlannedMeal` in `src/data/models.py` (lines 341-373):

```python
@dataclass
class PlannedMeal:
    """A planned meal for a specific date."""
    date: str  # YYYY-MM-DD
    meal_type: str  # "breakfast", "lunch", "dinner", "snack"
    recipe_id: str
    recipe_name: str
    servings: int = 4
    notes: Optional[str] = None
```

**Problem:** Only stores `recipe_id` and `recipe_name`, requires database lookup to get full recipe data.

---

## Design Decision: Embed Full Recipe

### Option 1: Keep Recipe ID Only (Current)
```python
@dataclass
class PlannedMeal:
    recipe_id: str
    recipe_name: str
```

**Pros:**
- Simple, lightweight
- Easy serialization

**Cons:**
- ❌ Requires database query to get recipe details
- ❌ No versioning (recipe changes affect old plans)
- ❌ Can't work offline
- ❌ More complex chat interactions (need to query for details)

### Option 2: Embed Full Recipe Object ✅ CHOSEN

```python
@dataclass
class PlannedMeal:
    recipe: Recipe  # Full Recipe object embedded
    servings: int   # Meal-specific servings
```

**Pros:**
- ✅ All recipe data immediately available
- ✅ Captures recipe state at planning time (versioning)
- ✅ Works offline
- ✅ Simpler chat interactions (no extra queries)
- ✅ Can scale recipe independently per meal

**Cons:**
- Larger serialized size
- Need to handle Recipe serialization/deserialization

**Decision:** Embed full Recipe object for better UX and offline support.

---

## Enhanced PlannedMeal Design

### Core Structure

```python
@dataclass
class PlannedMeal:
    """A planned meal for a specific date with embedded recipe."""

    # When & What Type
    date: str  # YYYY-MM-DD format
    meal_type: str  # "breakfast", "lunch", "dinner", "snack"

    # Embedded Recipe (full object)
    recipe: Recipe

    # Meal-Specific Overrides
    servings: int  # May differ from recipe.servings
    notes: Optional[str] = None  # User notes for this specific meal

    # Multi-Recipe Support (Future)
    # side_recipes: Optional[List[Recipe]] = None  # For multi-dish meals
```

### Key Design Principles

1. **Single Recipe Primary**: Start with one main recipe per meal
2. **Servings Override**: `servings` field overrides `recipe.servings` for this meal
3. **Full Embedding**: Complete Recipe object, including structured ingredients
4. **Serialization Support**: Must serialize/deserialize Recipe objects

---

## Methods

### 1. Get Scaled Recipe

```python
def get_scaled_recipe(self) -> Recipe:
    """
    Get the recipe scaled to this meal's servings.

    Returns:
        New Recipe object with ingredients scaled to meal servings
    """
    if self.servings == self.recipe.servings:
        return self.recipe
    return self.recipe.scale_ingredients(self.servings)
```

**Use Case:** Get recipe with correct quantities for this meal's serving size.

### 2. Get Ingredients for Shopping List

```python
def get_ingredients(self) -> List[Ingredient]:
    """
    Get ingredients for this meal (scaled to servings).

    Returns:
        List of Ingredient objects scaled to meal servings

    Raises:
        ValueError: If recipe is not enriched
    """
    scaled_recipe = self.get_scaled_recipe()
    return scaled_recipe.get_ingredients()
```

**Use Case:** Generate shopping list for this meal.

### 3. Check Allergens

```python
def has_allergen(self, allergen: str) -> bool:
    """
    Check if this meal contains a specific allergen.

    Args:
        allergen: Allergen name to check

    Returns:
        True if meal contains allergen
    """
    return self.recipe.has_allergen(allergen)

def get_all_allergens(self) -> List[str]:
    """Get all allergens in this meal."""
    return self.recipe.get_all_allergens()
```

**Use Case:** Dietary restriction checking.

### 4. Display Methods

```python
def __str__(self) -> str:
    """Human-readable string."""
    return f"{self.meal_type.title()}: {self.recipe.name} ({self.servings} servings)"

def get_summary(self) -> str:
    """
    Get a concise summary of the meal.

    Returns:
        Summary string with key details
    """
    return f"{self.date} - {self.meal_type.title()}: {self.recipe.name} (serves {self.servings})"
```

### 5. Serialization

```python
def to_dict(self) -> Dict:
    """
    Serialize to dictionary.

    Returns:
        Dictionary with all fields, recipe as nested dict
    """
    return {
        "date": self.date,
        "meal_type": self.meal_type,
        "recipe": self.recipe.to_dict(),  # Nested recipe dict
        "servings": self.servings,
        "notes": self.notes,
    }

@classmethod
def from_dict(cls, data: Dict) -> "PlannedMeal":
    """
    Deserialize from dictionary.

    Args:
        data: Dictionary from to_dict()

    Returns:
        PlannedMeal object
    """
    return cls(
        date=data["date"],
        meal_type=data["meal_type"],
        recipe=Recipe.from_dict(data["recipe"]),
        servings=data["servings"],
        notes=data.get("notes"),
    )
```

---

## Usage Examples

### Creating a PlannedMeal

```python
from src.data.database import DatabaseInterface
from src.data.models import PlannedMeal

# Load recipe from database
db = DatabaseInterface('data/recipes_dev.db')
recipe = db.get_recipe('71247')

# Create planned meal
meal = PlannedMeal(
    date="2025-10-29",
    meal_type="dinner",
    recipe=recipe,
    servings=6,  # Adjust for family size
    notes="Make extra for leftovers"
)

print(meal)  # "Dinner: Cherry Streusel Cobbler (6 servings)"
```

### Getting Scaled Ingredients

```python
# Get ingredients scaled to meal servings
ingredients = meal.get_ingredients()

for ing in ingredients:
    print(f"{ing.quantity} {ing.unit} {ing.name}")
```

### Checking Allergens

```python
if meal.has_allergen("dairy"):
    print(f"⚠️ {meal.recipe.name} contains dairy")

allergens = meal.get_all_allergens()
print(f"Allergens: {', '.join(allergens)}")
```

### Serialization Round-Trip

```python
# Save to JSON
meal_dict = meal.to_dict()
json_str = json.dumps(meal_dict)

# Load from JSON
restored_meal = PlannedMeal.from_dict(json.loads(json_str))

assert restored_meal.recipe.name == meal.recipe.name
assert restored_meal.servings == meal.servings
```

---

## Database Storage

PlannedMeal objects are stored as part of MealPlan:

```python
# In DatabaseInterface.save_meal_plan()
cursor.execute("""
    INSERT INTO meal_plans (id, week_of, created_at, meals_json)
    VALUES (?, ?, ?, ?)
""", (
    plan_id,
    week_of,
    created_at,
    json.dumps([meal.to_dict() for meal in meals])  # Serialize PlannedMeals
))
```

When loading:

```python
# In DatabaseInterface.get_meal_plan()
meals_json = row['meals_json']
meals = [PlannedMeal.from_dict(m) for m in json.loads(meals_json)]
```

---

## Multi-Recipe Meals (Future)

For meals with multiple recipes (e.g., main + sides):

```python
@dataclass
class PlannedMeal:
    recipe: Recipe  # Main recipe
    side_recipes: Optional[List[Recipe]] = None  # Side dishes

    def get_all_recipes(self) -> List[Recipe]:
        """Get all recipes for this meal."""
        recipes = [self.recipe]
        if self.side_recipes:
            recipes.extend(self.side_recipes)
        return recipes

    def get_all_ingredients(self) -> List[Ingredient]:
        """Get ingredients from all recipes."""
        all_ingredients = []
        for recipe in self.get_all_recipes():
            all_ingredients.extend(recipe.get_ingredients())
        return all_ingredients
```

**Decision:** Start with single recipe, add multi-recipe support later if needed.

---

## Integration with Existing Code

### DatabaseInterface Changes

The existing `DatabaseInterface` already handles PlannedMeal serialization:

```python
# src/data/database.py:327-328
json.dumps([meal.to_dict() for meal in meal_plan.meals])

# src/data/database.py:358
meals=[PlannedMeal.from_dict(m) for m in json.loads(row["meals_json"])]
```

**Action:** Update PlannedMeal.from_dict() to handle nested Recipe objects.

### Backward Compatibility

Old meal plans may have PlannedMeal with `recipe_id` instead of `recipe`:

```python
@classmethod
def from_dict(cls, data: Dict) -> "PlannedMeal":
    """Deserialize with backward compatibility."""

    # New format: embedded recipe
    if "recipe" in data and isinstance(data["recipe"], dict):
        recipe = Recipe.from_dict(data["recipe"])

    # Old format: recipe_id only (need to load from DB)
    elif "recipe_id" in data:
        # For backward compatibility, create minimal Recipe
        recipe = Recipe(
            id=data["recipe_id"],
            name=data.get("recipe_name", "Unknown Recipe"),
            description="",
            ingredients=[],
            ingredients_raw=[],
            steps=[],
            servings=data.get("servings", 4),
            tags=[],
        )

    return cls(
        date=data["date"],
        meal_type=data["meal_type"],
        recipe=recipe,
        servings=data["servings"],
        notes=data.get("notes"),
    )
```

---

## Testing Strategy

Create `test_planned_meal.py` to verify:

1. ✅ Create PlannedMeal with embedded Recipe
2. ✅ Get scaled recipe with different servings
3. ✅ Get scaled ingredients for shopping list
4. ✅ Allergen detection
5. ✅ Serialization round-trip (to_dict/from_dict)
6. ✅ Display methods (__str__, get_summary)
7. ✅ Backward compatibility with old format

---

## Success Criteria

- [x] PlannedMeal embeds full Recipe object
- [x] get_scaled_recipe() returns Recipe with correct servings
- [x] get_ingredients() returns scaled ingredient list
- [x] Allergen detection works through embedded recipe
- [x] to_dict()/from_dict() handles nested Recipe serialization
- [x] Backward compatible with old PlannedMeal format
- [x] All tests pass

---

## Next Steps

1. **Step 5: Implement PlannedMeal** - Update `src/data/models.py`
2. **Step 6: Design MealPlan** - Define MealPlan structure with embedded PlannedMeals
3. **Step 7: Implement MealPlan** - Update MealPlan class
4. **Update Chat Agents** - Modify agents to use embedded recipes

---

**Status:** Design complete, ready for implementation
**Estimated Implementation:** 30 minutes
**Dependencies:** Recipe (already implemented)
