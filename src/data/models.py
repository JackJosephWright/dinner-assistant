"""
Data models for the Meal Planning Assistant.

These models define the core entities used throughout the system:
- Recipe: Food.com dataset recipes
- MealPlan: Weekly meal planning
- GroceryList: Shopping list generation
- MealEvent: Rich meal tracking for learning
- UserProfile: User preferences and onboarding data
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import List, Optional, Dict
import json


@dataclass
class Ingredient:
    """Structured ingredient data from recipe enrichment.

    This represents a parsed ingredient with quantity, unit, and metadata.
    Created by the enrichment script (scripts/enrich_recipe_ingredients.py).
    """
    raw: str  # Original ingredient string
    quantity: Optional[float] = None  # Numeric quantity (e.g., 2.0)
    unit: Optional[str] = None  # Unit of measurement (e.g., "cup", "tablespoon")
    name: str = ""  # Ingredient name (e.g., "flour", "butter")
    modifier: Optional[str] = None  # Modifier (e.g., "all-purpose", "unsalted")
    preparation: Optional[str] = None  # Preparation note (e.g., "chopped", "sifted")
    category: str = "other"  # Shopping category (e.g., "baking", "produce", "meat")
    allergens: List[str] = field(default_factory=list)  # Allergens (e.g., ["gluten", "dairy"])
    substitutable: bool = True  # Whether ingredient can be substituted
    confidence: float = 1.0  # Parser confidence (0.0-1.0)
    parse_method: str = "auto"  # How it was parsed ("auto", "manual", "fallback")

    def __str__(self) -> str:
        """Human-readable ingredient string."""
        if self.quantity and self.unit:
            return f"{self.quantity} {self.unit} {self.name}"
        elif self.quantity:
            return f"{self.quantity} {self.name}"
        else:
            return self.name

    def scale(self, factor: float) -> 'Ingredient':
        """Scale ingredient quantity by factor.

        Args:
            factor: Scaling factor (e.g., 2.0 for doubling, 0.5 for halving)

        Returns:
            New Ingredient with scaled quantity

        Note:
            Returns self unchanged if quantity is None (e.g., "salt to taste")
        """
        if self.quantity is None:
            return self  # Can't scale "to taste" ingredients

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
    """Nutrition information per serving.

    Note: Currently a placeholder. Nutrition data parsing not yet implemented.
    """
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
    """Recipe from Food.com dataset with optional enriched ingredient data."""

    id: str
    name: str
    description: str
    ingredients: List[str]  # Clean ingredient names (for search)
    ingredients_raw: List[str]  # Original with quantities
    steps: List[str]
    servings: int
    serving_size: str
    tags: List[str]

    # Enriched data (optional, only for enriched recipes)
    ingredients_structured: Optional[List[Ingredient]] = None  # Parsed ingredient objects
    nutrition: Optional[NutritionInfo] = None  # Nutrition data (placeholder)

    # Derived fields
    estimated_time: Optional[int] = None  # Minutes, from tags
    cuisine: Optional[str] = None  # From tags
    difficulty: str = "medium"  # "easy", "medium", "hard"

    def __post_init__(self):
        """Extract derived fields from tags."""
        if self.estimated_time is None:
            self.estimated_time = self._extract_time_from_tags()
        if self.cuisine is None:
            self.cuisine = self._extract_cuisine_from_tags()
        if self.difficulty == "medium":
            self.difficulty = self._extract_difficulty_from_tags()

    def _extract_time_from_tags(self) -> Optional[int]:
        """Extract estimated cooking time from tags."""
        time_tags = {
            "15-minutes-or-less": 15,
            "30-minutes-or-less": 30,
            "60-minutes-or-less": 60,
            "4-hours-or-less": 240,
        }
        for tag in self.tags:
            if tag in time_tags:
                return time_tags[tag]
        return None

    def _extract_cuisine_from_tags(self) -> Optional[str]:
        """Extract cuisine type from tags."""
        cuisine_tags = [
            "italian", "mexican", "chinese", "thai", "indian",
            "japanese", "french", "greek", "american", "korean"
        ]
        for tag in self.tags:
            if tag in cuisine_tags:
                return tag.title()
        return None

    def _extract_difficulty_from_tags(self) -> str:
        """Extract difficulty level from tags."""
        if "easy" in self.tags or "beginner-cook" in self.tags:
            return "easy"
        elif "difficult" in self.tags or "advanced" in self.tags:
            return "hard"
        return "medium"

    def has_structured_ingredients(self) -> bool:
        """Check if recipe has been enriched with structured ingredient data.

        Returns:
            True if recipe has structured ingredients, False otherwise
        """
        return (
            self.ingredients_structured is not None
            and len(self.ingredients_structured) > 0
        )

    def get_ingredients(self) -> List[Ingredient]:
        """Get structured ingredients (enriched recipes only).

        Returns:
            List of Ingredient objects

        Raises:
            ValueError: If recipe has not been enriched

        Note:
            For development phase, only works with enriched recipes.
            Fallback parsing can be added later if needed.
        """
        if not self.has_structured_ingredients():
            raise ValueError(
                f"Recipe '{self.name}' (ID: {self.id}) has not been enriched with structured ingredients. "
                f"Only {5000} recipes out of {492630} are currently enriched."
            )
        return self.ingredients_structured

    def has_allergen(self, allergen: str) -> bool:
        """Check if recipe contains a specific allergen.

        Args:
            allergen: Allergen to check (e.g., "gluten", "dairy", "eggs")

        Returns:
            True if allergen present, False otherwise

        Raises:
            ValueError: If recipe has not been enriched
        """
        if not self.has_structured_ingredients():
            raise ValueError(
                f"Recipe '{self.name}' requires structured ingredients for allergen checking"
            )

        allergen_lower = allergen.lower()
        for ing in self.ingredients_structured:
            if allergen_lower in [a.lower() for a in ing.allergens]:
                return True
        return False

    def get_all_allergens(self) -> List[str]:
        """Get all unique allergens in recipe.

        Returns:
            Sorted list of allergen names

        Raises:
            ValueError: If recipe has not been enriched
        """
        if not self.has_structured_ingredients():
            raise ValueError(
                f"Recipe '{self.name}' requires structured ingredients for allergen detection"
            )

        all_allergens = set()
        for ing in self.ingredients_structured:
            all_allergens.update(ing.allergens)

        return sorted(list(all_allergens))

    def scale_ingredients(self, target_servings: int) -> 'Recipe':
        """Create a new recipe with scaled ingredient quantities.

        Args:
            target_servings: Desired number of servings

        Returns:
            New Recipe object with scaled quantities (original unchanged)

        Raises:
            ValueError: If recipe has not been enriched

        Note:
            Returns immutable copy - original recipe is not modified
        """
        if not self.has_structured_ingredients():
            raise ValueError(
                f"Recipe '{self.name}' requires structured ingredients for scaling"
            )

        factor = target_servings / self.servings
        scaled_ingredients = [ing.scale(factor) for ing in self.ingredients_structured]

        # Create new recipe (don't modify original)
        return Recipe(
            id=self.id,
            name=f"{self.name} ({target_servings} servings)",
            description=self.description,
            ingredients=self.ingredients,  # Keep original clean names
            ingredients_raw=self.ingredients_raw,  # Keep original raw
            steps=self.steps,
            servings=target_servings,
            serving_size=self.serving_size,
            tags=self.tags,
            ingredients_structured=scaled_ingredients,
            nutrition=self.nutrition,
            estimated_time=self.estimated_time,
            cuisine=self.cuisine,
            difficulty=self.difficulty,
        )

    def to_dict(self) -> Dict:
        """Convert to dictionary for JSON serialization."""
        data = {
            "id": self.id,
            "name": self.name,
            "description": self.description,
            "ingredients": self.ingredients,
            "ingredients_raw": self.ingredients_raw,
            "steps": self.steps,
            "servings": self.servings,
            "serving_size": self.serving_size,
            "tags": self.tags,
            "estimated_time": self.estimated_time,
            "cuisine": self.cuisine,
            "difficulty": self.difficulty,
        }

        # Add enriched data if present
        if self.ingredients_structured:
            data["ingredients_structured"] = [
                ing.__dict__ for ing in self.ingredients_structured
            ]

        if self.nutrition:
            data["nutrition"] = self.nutrition.__dict__

        return data

    @classmethod
    def from_dict(cls, data: Dict) -> "Recipe":
        """Create Recipe from dictionary.

        Args:
            data: Dictionary representation of Recipe

        Returns:
            Recipe object with structured ingredients parsed if present
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

        # Create recipe with parsed enriched data
        recipe_data = {**data}
        recipe_data["ingredients_structured"] = ingredients_structured
        recipe_data["nutrition"] = nutrition

        return cls(**recipe_data)


@dataclass
class PlannedMeal:
    """A planned meal for a specific date with embedded recipe."""

    date: str  # ISO format: "2025-01-20"
    meal_type: str  # "breakfast", "lunch", "dinner", "snack"
    recipe: "Recipe"  # Full Recipe object embedded
    servings: int  # May differ from recipe.servings
    notes: Optional[str] = None

    def get_scaled_recipe(self) -> "Recipe":
        """
        Get the recipe scaled to this meal's servings.

        Returns:
            New Recipe object with ingredients scaled to meal servings
        """
        if self.servings == self.recipe.servings:
            return self.recipe
        return self.recipe.scale_ingredients(self.servings)

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
        """
        Get all allergens in this meal.

        Returns:
            List of unique allergen names
        """
        return self.recipe.get_all_allergens()

    def get_summary(self) -> str:
        """
        Get a concise summary of the meal.

        Returns:
            Summary string with key details
        """
        return f"{self.date} - {self.meal_type.title()}: {self.recipe.name} (serves {self.servings})"

    def __str__(self) -> str:
        """Human-readable string."""
        return f"{self.meal_type.title()}: {self.recipe.name} ({self.servings} servings)"

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
        Deserialize from dictionary with backward compatibility.

        Args:
            data: Dictionary from to_dict()

        Returns:
            PlannedMeal object
        """
        # New format: embedded recipe
        if "recipe" in data and isinstance(data["recipe"], dict):
            recipe = Recipe.from_dict(data["recipe"])

        # Old format: recipe_id only (backward compatibility)
        elif "recipe_id" in data:
            # Create minimal Recipe for backward compatibility
            recipe = Recipe(
                id=data["recipe_id"],
                name=data.get("recipe_name", "Unknown Recipe"),
                description="",
                ingredients=[],
                ingredients_raw=[],
                steps=[],
                servings=data.get("servings", 4),
                serving_size="",
                tags=[],
            )
        else:
            raise ValueError("PlannedMeal data must contain either 'recipe' or 'recipe_id'")

        return cls(
            date=data["date"],
            meal_type=data["meal_type"],
            recipe=recipe,
            servings=data["servings"],
            notes=data.get("notes"),
        )


@dataclass
class MealPlan:
    """Weekly meal plan with embedded recipes."""

    week_of: str  # ISO format: "2025-01-20" (Monday of the week)
    meals: List[PlannedMeal]
    created_at: datetime = field(default_factory=datetime.now)
    preferences_applied: List[str] = field(default_factory=list)
    id: Optional[str] = None  # Generated on save

    # Backup recipes for instant meal swaps
    # Key = search category (e.g., "chicken", "pasta")
    # Value = List of recipes that matched but weren't selected
    backup_recipes: Dict[str, List['Recipe']] = field(default_factory=dict)

    def get_meals_for_day(self, date: str) -> List[PlannedMeal]:
        """
        Get all meals for a specific date.

        Args:
            date: ISO format date string (YYYY-MM-DD)

        Returns:
            List of PlannedMeal objects for that date
        """
        return [meal for meal in self.meals if meal.date == date]

    def get_meals_by_type(self, meal_type: str) -> List[PlannedMeal]:
        """
        Get all meals of a specific type.

        Args:
            meal_type: "breakfast", "lunch", "dinner", "snack"

        Returns:
            List of PlannedMeal objects of that type
        """
        return [meal for meal in self.meals if meal.meal_type == meal_type]

    def get_date_range(self) -> tuple:
        """
        Get the start and end dates of this meal plan.

        Returns:
            Tuple of (start_date, end_date) in ISO format
        """
        if not self.meals:
            return (self.week_of, self.week_of)

        dates = [meal.date for meal in self.meals]
        return (min(dates), max(dates))

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

    def to_dict(self) -> Dict:
        """Convert to dictionary for JSON serialization."""
        return {
            "id": self.id,
            "week_of": self.week_of,
            "meals": [meal.to_dict() for meal in self.meals],
            "created_at": self.created_at.isoformat(),
            "preferences_applied": self.preferences_applied,
        }

    @classmethod
    def from_dict(cls, data: Dict) -> "MealPlan":
        """Create MealPlan from dictionary."""
        return cls(
            id=data.get("id"),
            week_of=data["week_of"],
            meals=[PlannedMeal.from_dict(m) for m in data["meals"]],
            created_at=datetime.fromisoformat(data["created_at"]),
            preferences_applied=data.get("preferences_applied", []),
        )


@dataclass
class GroceryItem:
    """Single item on a grocery list."""

    name: str  # "Ground beef"
    quantity: str  # "2 lbs"
    category: str  # "meat", "produce", "dairy", etc.
    recipe_sources: List[str]  # Recipe names that need this ingredient
    notes: Optional[str] = None

    def to_dict(self) -> Dict:
        """Convert to dictionary for JSON serialization."""
        return {
            "name": self.name,
            "quantity": self.quantity,
            "category": self.category,
            "recipe_sources": self.recipe_sources,
            "notes": self.notes,
        }

    @classmethod
    def from_dict(cls, data: Dict) -> "GroceryItem":
        """Create GroceryItem from dictionary."""
        return cls(**data)


@dataclass
class GroceryList:
    """Shopping list for a week of meals."""

    week_of: str  # ISO format: "2025-01-20"
    items: List[GroceryItem]
    estimated_total: Optional[float] = None
    store_sections: Dict[str, List[GroceryItem]] = field(default_factory=dict)
    extra_items: List[GroceryItem] = field(default_factory=list)  # User-added items (not from recipes)
    created_at: datetime = field(default_factory=datetime.now)
    id: Optional[str] = None

    def __post_init__(self):
        """Organize items by store section if not already done."""
        if not self.store_sections and self.items:
            self._organize_by_section()

    def _organize_by_section(self):
        """Group items by category/store section."""
        for item in self.items:
            if item.category not in self.store_sections:
                self.store_sections[item.category] = []
            self.store_sections[item.category].append(item)

    def to_dict(self) -> Dict:
        """Convert to dictionary for JSON serialization."""
        return {
            "id": self.id,
            "week_of": self.week_of,
            "items": [item.to_dict() for item in self.items],
            "estimated_total": self.estimated_total,
            "store_sections": {
                section: [item.to_dict() for item in items]
                for section, items in self.store_sections.items()
            },
            "extra_items": [item.to_dict() for item in self.extra_items],
            "created_at": self.created_at.isoformat(),
        }

    @classmethod
    def from_dict(cls, data: Dict) -> "GroceryList":
        """Create GroceryList from dictionary."""
        items = [GroceryItem.from_dict(i) for i in data["items"]]
        store_sections = {
            section: [GroceryItem.from_dict(i) for i in items_data]
            for section, items_data in data.get("store_sections", {}).items()
        }
        extra_items = [GroceryItem.from_dict(i) for i in data.get("extra_items", [])]

        return cls(
            id=data.get("id"),
            week_of=data["week_of"],
            items=items,
            estimated_total=data.get("estimated_total"),
            store_sections=store_sections,
            extra_items=extra_items,
            created_at=datetime.fromisoformat(data["created_at"]),
        )


@dataclass
class MealEvent:
    """Rich tracking of a meal for learning and analytics."""

    # When
    date: str  # ISO format: "2025-10-20"
    day_of_week: str
    meal_type: str = "dinner"

    # What (Recipe)
    recipe_id: str = ""
    recipe_name: str = ""
    recipe_cuisine: Optional[str] = None
    recipe_difficulty: Optional[str] = None

    # How (Execution)
    servings_planned: Optional[int] = None
    servings_actual: Optional[int] = None
    ingredients_snapshot: List[str] = field(default_factory=list)
    modifications: Dict[str, any] = field(default_factory=dict)
    substitutions: Dict[str, str] = field(default_factory=dict)

    # Feedback
    user_rating: Optional[int] = None  # 1-5 stars
    cooking_time_actual: Optional[int] = None
    notes: Optional[str] = None
    would_make_again: Optional[bool] = None

    # Metadata
    meal_plan_id: Optional[str] = None
    created_at: datetime = field(default_factory=datetime.now)
    id: Optional[int] = None

    def to_dict(self) -> Dict:
        """Convert to dictionary for JSON serialization."""
        return {
            "id": self.id,
            "date": self.date,
            "day_of_week": self.day_of_week,
            "meal_type": self.meal_type,
            "recipe_id": self.recipe_id,
            "recipe_name": self.recipe_name,
            "recipe_cuisine": self.recipe_cuisine,
            "recipe_difficulty": self.recipe_difficulty,
            "servings_planned": self.servings_planned,
            "servings_actual": self.servings_actual,
            "ingredients_snapshot": self.ingredients_snapshot,
            "modifications": self.modifications,
            "substitutions": self.substitutions,
            "user_rating": self.user_rating,
            "cooking_time_actual": self.cooking_time_actual,
            "notes": self.notes,
            "would_make_again": self.would_make_again,
            "meal_plan_id": self.meal_plan_id,
            "created_at": self.created_at.isoformat(),
        }

    @classmethod
    def from_dict(cls, data: Dict) -> "MealEvent":
        """Create MealEvent from dictionary."""
        return cls(
            id=data.get("id"),
            date=data["date"],
            day_of_week=data["day_of_week"],
            meal_type=data.get("meal_type", "dinner"),
            recipe_id=data.get("recipe_id", ""),
            recipe_name=data.get("recipe_name", ""),
            recipe_cuisine=data.get("recipe_cuisine"),
            recipe_difficulty=data.get("recipe_difficulty"),
            servings_planned=data.get("servings_planned"),
            servings_actual=data.get("servings_actual"),
            ingredients_snapshot=data.get("ingredients_snapshot", []),
            modifications=data.get("modifications", {}),
            substitutions=data.get("substitutions", {}),
            user_rating=data.get("user_rating"),
            cooking_time_actual=data.get("cooking_time_actual"),
            notes=data.get("notes"),
            would_make_again=data.get("would_make_again"),
            meal_plan_id=data.get("meal_plan_id"),
            created_at=datetime.fromisoformat(data["created_at"]),
        )


@dataclass
class UserProfile:
    """User preferences from onboarding and settings."""

    # Household
    household_size: int = 4
    cooking_for: Dict[str, int] = field(default_factory=lambda: {"adults": 2, "kids": 2})

    # Dietary
    dietary_restrictions: List[str] = field(default_factory=list)
    allergens: List[str] = field(default_factory=list)

    # Preferences
    favorite_cuisines: List[str] = field(default_factory=list)
    disliked_ingredients: List[str] = field(default_factory=list)
    preferred_proteins: List[str] = field(default_factory=list)
    spice_tolerance: str = "medium"  # "mild", "medium", "spicy"

    # Constraints
    max_weeknight_cooking_time: int = 45
    max_weekend_cooking_time: int = 90
    budget_per_week: Optional[float] = None

    # Goals
    variety_preference: str = "high"  # "low", "medium", "high"
    health_focus: Optional[str] = None  # "balanced", "low-carb", "vegetarian", etc.

    # Metadata
    onboarding_completed: bool = False
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)
    id: int = 1  # Single row

    def to_dict(self) -> Dict:
        """Convert to dictionary for JSON serialization."""
        return {
            "id": self.id,
            "household_size": self.household_size,
            "cooking_for": self.cooking_for,
            "dietary_restrictions": self.dietary_restrictions,
            "allergens": self.allergens,
            "favorite_cuisines": self.favorite_cuisines,
            "disliked_ingredients": self.disliked_ingredients,
            "preferred_proteins": self.preferred_proteins,
            "spice_tolerance": self.spice_tolerance,
            "max_weeknight_cooking_time": self.max_weeknight_cooking_time,
            "max_weekend_cooking_time": self.max_weekend_cooking_time,
            "budget_per_week": self.budget_per_week,
            "variety_preference": self.variety_preference,
            "health_focus": self.health_focus,
            "onboarding_completed": self.onboarding_completed,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
        }

    @classmethod
    def from_dict(cls, data: Dict) -> "UserProfile":
        """Create UserProfile from dictionary."""
        return cls(
            id=data.get("id", 1),
            household_size=data.get("household_size", 4),
            cooking_for=data.get("cooking_for", {"adults": 2, "kids": 2}),
            dietary_restrictions=data.get("dietary_restrictions", []),
            allergens=data.get("allergens", []),
            favorite_cuisines=data.get("favorite_cuisines", []),
            disliked_ingredients=data.get("disliked_ingredients", []),
            preferred_proteins=data.get("preferred_proteins", []),
            spice_tolerance=data.get("spice_tolerance", "medium"),
            max_weeknight_cooking_time=data.get("max_weeknight_cooking_time", 45),
            max_weekend_cooking_time=data.get("max_weekend_cooking_time", 90),
            budget_per_week=data.get("budget_per_week"),
            variety_preference=data.get("variety_preference", "high"),
            health_focus=data.get("health_focus"),
            onboarding_completed=data.get("onboarding_completed", False),
            created_at=datetime.fromisoformat(data.get("created_at", datetime.now().isoformat())),
            updated_at=datetime.fromisoformat(data.get("updated_at", datetime.now().isoformat())),
        )
