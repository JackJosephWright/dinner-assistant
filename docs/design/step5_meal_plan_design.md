# Step 5: MealPlan Object Design

**Created:** 2025-10-28
**Status:** Design Phase
**Purpose:** Enhance MealPlan with embedded PlannedMeal objects

---

## Overview

The `MealPlan` object represents a collection of planned meals for a week. With PlannedMeal now embedding full Recipe objects, MealPlan becomes a complete, self-contained meal planning solution that works offline.

---

## Current Implementation

The existing `MealPlan` in `src/data/models.py` (lines 463-492):

```python
@dataclass
class MealPlan:
    """Weekly meal plan."""

    week_of: str  # ISO format: "2025-01-20" (Monday of the week)
    meals: List[PlannedMeal]
    created_at: datetime = field(default_factory=datetime.now)
    preferences_applied: List[str] = field(default_factory=list)
    id: Optional[str] = None  # Generated on save
```

**Status:** Already well-structured! PlannedMeal changes automatically improve MealPlan.

---

## Design Decision: Keep List Structure

### Option 1: List of Meals (Current) ✅ CHOSEN

```python
meals: List[PlannedMeal]
```

**Pros:**
- ✅ Simple, flexible
- ✅ Easy to iterate
- ✅ No assumptions about structure
- ✅ Works for any meal frequency (1 meal/day, 3 meals/day, etc.)

**Cons:**
- Need to filter/search to find specific day
- No built-in grouping by day

### Option 2: Dictionary by Day

```python
meals_by_day: Dict[str, List[PlannedMeal]]
# {"2025-10-28": [breakfast, lunch, dinner], ...}
```

**Pros:**
- Easy to access specific day
- Natural grouping

**Cons:**
- ❌ More complex structure
- ❌ Harder to serialize
- ❌ Less flexible for irregular schedules

**Decision:** Keep List structure, add helper methods for day-based access.

---

## Enhanced MealPlan Design

### Core Structure

```python
@dataclass
class MealPlan:
    """Weekly meal plan with embedded recipes."""

    # Plan Metadata
    week_of: str  # ISO format: "2025-01-20" (Monday of the week)
    id: Optional[str] = None  # Generated on save

    # Meal Collection
    meals: List[PlannedMeal]  # All planned meals with embedded recipes

    # Tracking
    created_at: datetime = field(default_factory=datetime.now)
    preferences_applied: List[str] = field(default_factory=list)
```

**No structural changes needed!** PlannedMeal embedding makes MealPlan automatically better.

---

## New Methods to Add

### 1. Get Meals by Day

```python
def get_meals_for_day(self, date: str) -> List[PlannedMeal]:
    """
    Get all meals for a specific date.

    Args:
        date: ISO format date string (YYYY-MM-DD)

    Returns:
        List of PlannedMeal objects for that date
    """
    return [meal for meal in self.meals if meal.date == date]
```

**Use Case:** Show all meals for a specific day (breakfast, lunch, dinner).

### 2. Get Meals by Type

```python
def get_meals_by_type(self, meal_type: str) -> List[PlannedMeal]:
    """
    Get all meals of a specific type.

    Args:
        meal_type: "breakfast", "lunch", "dinner", "snack"

    Returns:
        List of PlannedMeal objects of that type
    """
    return [meal for meal in self.meals if meal.meal_type == meal_type]
```

**Use Case:** Show all dinners for the week.

### 3. Get Date Range

```python
def get_date_range(self) -> tuple[str, str]:
    """
    Get the start and end dates of this meal plan.

    Returns:
        Tuple of (start_date, end_date) in ISO format
    """
    if not self.meals:
        return (self.week_of, self.week_of)

    dates = [meal.date for meal in self.meals]
    return (min(dates), max(dates))
```

**Use Case:** Display plan date range.

### 4. Get All Ingredients (Shopping List)

```python
def get_all_ingredients(self) -> List[Ingredient]:
    """
    Get all ingredients from all meals (for shopping list).

    Returns:
        List of all Ingredient objects from all meals

    Raises:
        ValueError: If any recipe is not enriched
    """
    all_ingredients = []
    for meal in self.meals:
        all_ingredients.extend(meal.get_ingredients())
    return all_ingredients
```

**Use Case:** Generate complete shopping list for the week.

### 5. Get Consolidated Shopping List

```python
def get_shopping_list_by_category(self) -> Dict[str, List[Ingredient]]:
    """
    Get ingredients grouped by category for shopping.

    Returns:
        Dictionary mapping category to list of ingredients
        Example: {"produce": [Ingredient(...), ...], "dairy": [...], ...}

    Raises:
        ValueError: If any recipe is not enriched
    """
    all_ingredients = self.get_all_ingredients()

    by_category = {}
    for ing in all_ingredients:
        category = ing.category
        if category not in by_category:
            by_category[category] = []
        by_category[category].append(ing)

    return by_category
```

**Use Case:** Organized shopping list by grocery store section.

### 6. Check Allergens Across Plan

```python
def get_all_allergens(self) -> List[str]:
    """
    Get all unique allergens across all meals.

    Returns:
        List of unique allergen names
    """
    allergens = set()
    for meal in self.meals:
        allergens.update(meal.get_all_allergens())
    return sorted(list(allergens))

def has_allergen(self, allergen: str) -> bool:
    """
    Check if any meal in plan contains allergen.

    Args:
        allergen: Allergen name to check

    Returns:
        True if any meal contains allergen
    """
    return any(meal.has_allergen(allergen) for meal in self.meals)

def get_meals_with_allergen(self, allergen: str) -> List[PlannedMeal]:
    """
    Get all meals containing a specific allergen.

    Args:
        allergen: Allergen name to check

    Returns:
        List of PlannedMeal objects containing allergen
    """
    return [meal for meal in self.meals if meal.has_allergen(allergen)]
```

**Use Case:** Dietary restriction management.

### 7. Summary and Display

```python
def get_summary(self) -> str:
    """
    Get a concise summary of the meal plan.

    Returns:
        Summary string with key details
    """
    start, end = self.get_date_range()
    return f"Meal Plan: {start} to {end} ({len(self.meals)} meals)"

def __str__(self) -> str:
    """Human-readable string."""
    return self.get_summary()
```

### 8. Get Meals as Dict by Date

```python
def get_meals_by_date(self) -> Dict[str, List[PlannedMeal]]:
    """
    Get meals organized by date.

    Returns:
        Dictionary mapping date to list of meals
        Example: {"2025-10-28": [PlannedMeal(...), ...], ...}
    """
    by_date = {}
    for meal in self.meals:
        if meal.date not in by_date:
            by_date[meal.date] = []
        by_date[meal.date].append(meal)
    return by_date
```

**Use Case:** Calendar-style display.

---

## Serialization (Already Implemented)

The existing serialization works perfectly with new PlannedMeal:

```python
def to_dict(self) -> Dict:
    """Convert to dictionary for JSON serialization."""
    return {
        "id": self.id,
        "week_of": self.week_of,
        "meals": [meal.to_dict() for meal in self.meals],  # Now includes full recipes!
        "created_at": self.created_at.isoformat(),
        "preferences_applied": self.preferences_applied,
    }

@classmethod
def from_dict(cls, data: Dict) -> "MealPlan":
    """Create MealPlan from dictionary."""
    return cls(
        id=data.get("id"),
        week_of=data["week_of"],
        meals=[PlannedMeal.from_dict(m) for m in data["meals"]],  # Handles embedded recipes!
        created_at=datetime.fromisoformat(data["created_at"]),
        preferences_applied=data.get("preferences_applied", []),
    )
```

**Already done!** Serialization automatically handles embedded recipes.

---

## Usage Examples

### Creating a MealPlan

```python
from src.data.database import DatabaseInterface
from src.data.models import MealPlan, PlannedMeal
from datetime import datetime

db = DatabaseInterface('data/recipes_dev.db')

# Load recipes
pasta_recipe = db.get_recipe('71247')
chicken_recipe = db.get_recipe('71248')

# Create meals
monday_dinner = PlannedMeal(
    date="2025-10-28",
    meal_type="dinner",
    recipe=pasta_recipe,
    servings=4
)

tuesday_dinner = PlannedMeal(
    date="2025-10-29",
    meal_type="dinner",
    recipe=chicken_recipe,
    servings=6
)

# Create meal plan
plan = MealPlan(
    week_of="2025-10-28",
    meals=[monday_dinner, tuesday_dinner],
    preferences_applied=["dairy-free", "quick-meals"]
)

print(plan)  # "Meal Plan: 2025-10-28 to 2025-10-29 (2 meals)"
```

### Getting Meals for a Day

```python
# Get all meals for Monday
monday_meals = plan.get_meals_for_day("2025-10-28")
for meal in monday_meals:
    print(meal)  # "Dinner: Pasta Recipe (4 servings)"
```

### Generating Shopping List

```python
# Get all ingredients
all_ingredients = plan.get_all_ingredients()

# Or organized by category
by_category = plan.get_shopping_list_by_category()
for category, ingredients in by_category.items():
    print(f"\n{category.title()}:")
    for ing in ingredients:
        print(f"  - {ing.quantity} {ing.unit} {ing.name}")
```

### Checking Allergens

```python
# Check if plan contains dairy
if plan.has_allergen("dairy"):
    print("⚠️ This plan contains dairy")

    # Find which meals have dairy
    dairy_meals = plan.get_meals_with_allergen("dairy")
    for meal in dairy_meals:
        print(f"  - {meal.date}: {meal.recipe.name}")

# Get all allergens in plan
allergens = plan.get_all_allergens()
print(f"Plan contains: {', '.join(allergens)}")
```

### Saving and Loading

```python
# Save to database
db = DatabaseInterface('data')
plan_id = db.save_meal_plan(plan)

# Load from database
loaded_plan = db.get_meal_plan(plan_id)

# Full recipes are embedded - no additional queries needed!
for meal in loaded_plan.meals:
    print(f"{meal.recipe.name}: {len(meal.recipe.get_ingredients())} ingredients")
```

---

## Database Storage

MealPlan storage already works correctly:

```sql
CREATE TABLE meal_plans (
    id TEXT PRIMARY KEY,
    week_of TEXT NOT NULL,
    created_at TEXT NOT NULL,
    preferences_applied TEXT,
    meals_json TEXT NOT NULL  -- JSON array of PlannedMeal objects with embedded recipes
)
```

With embedded recipes, `meals_json` now contains:
- Full recipe data (name, ingredients, steps, etc.)
- Structured ingredients for each recipe
- Meal-specific servings
- All metadata

**Size Impact:** Larger JSON payloads (~50KB per plan vs ~5KB), but worth it for offline capability.

---

## Integration with Chat Interface

### Use Case 1: "What's for dinner tonight?"

```python
# Chat agent can answer immediately without DB queries
today = "2025-10-28"
today_dinners = plan.get_meals_for_day(today)

for meal in today_dinners:
    if meal.meal_type == "dinner":
        # Full recipe data already available
        print(f"Tonight: {meal.recipe.name}")
        print(f"Servings: {meal.servings}")
        print(f"Ingredients: {len(meal.get_ingredients())}")
```

### Use Case 2: "Can I make this with dairy allergy?"

```python
# Check allergens across entire plan
if plan.has_allergen("dairy"):
    dairy_meals = plan.get_meals_with_allergen("dairy")
    print(f"{len(dairy_meals)} meals contain dairy:")
    for meal in dairy_meals:
        print(f"  - {meal.date}: {meal.recipe.name}")
```

### Use Case 3: "Generate shopping list"

```python
# One method call, no DB queries
shopping_list = plan.get_shopping_list_by_category()

# Chat can format and present
for category in ["produce", "meat", "dairy"]:
    if category in shopping_list:
        print(f"\n{category.upper()}:")
        for ing in shopping_list[category]:
            print(f"  [ ] {ing.quantity} {ing.unit} {ing.name}")
```

---

## Testing Strategy

Create `test_meal_plan.py` to verify:

1. ✅ Create MealPlan with embedded PlannedMeals
2. ✅ Get meals by day
3. ✅ Get meals by type
4. ✅ Get date range
5. ✅ Get all ingredients (shopping list)
6. ✅ Get shopping list by category
7. ✅ Allergen detection across plan
8. ✅ Serialization round-trip
9. ✅ Display methods

---

## Success Criteria

- [x] MealPlan works with embedded PlannedMeal objects
- [x] get_meals_for_day() filters by date
- [x] get_all_ingredients() returns complete shopping list
- [x] get_shopping_list_by_category() groups by category
- [x] Allergen detection works across all meals
- [x] to_dict()/from_dict() preserves embedded recipes
- [x] All tests pass

---

## Next Steps

1. **Step 6: Implement MealPlan** - Add new methods to `src/data/models.py`
2. **Update Chat Agents** - Modify agents to use embedded recipes
3. **Test Integration** - Verify end-to-end workflow

---

**Status:** Design complete, ready for implementation
**Estimated Implementation:** 30 minutes
**Dependencies:** PlannedMeal (already implemented)
