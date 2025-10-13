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
class Recipe:
    """Recipe from Food.com dataset."""

    id: str
    name: str
    description: str
    ingredients: List[str]  # Clean ingredient names
    ingredients_raw: List[str]  # Original with quantities
    steps: List[str]
    servings: int
    serving_size: str
    tags: List[str]

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

    def to_dict(self) -> Dict:
        """Convert to dictionary for JSON serialization."""
        return {
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

    @classmethod
    def from_dict(cls, data: Dict) -> "Recipe":
        """Create Recipe from dictionary."""
        return cls(**data)


@dataclass
class PlannedMeal:
    """A single meal in a meal plan."""

    date: str  # ISO format: "2025-01-20"
    meal_type: str  # "dinner", "lunch", etc.
    recipe_id: str
    recipe_name: str
    servings: int
    notes: Optional[str] = None

    def to_dict(self) -> Dict:
        """Convert to dictionary for JSON serialization."""
        return {
            "date": self.date,
            "meal_type": self.meal_type,
            "recipe_id": self.recipe_id,
            "recipe_name": self.recipe_name,
            "servings": self.servings,
            "notes": self.notes,
        }

    @classmethod
    def from_dict(cls, data: Dict) -> "PlannedMeal":
        """Create PlannedMeal from dictionary."""
        return cls(**data)


@dataclass
class MealPlan:
    """Weekly meal plan."""

    week_of: str  # ISO format: "2025-01-20" (Monday of the week)
    meals: List[PlannedMeal]
    created_at: datetime = field(default_factory=datetime.now)
    preferences_applied: List[str] = field(default_factory=list)
    id: Optional[str] = None  # Generated on save

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

        return cls(
            id=data.get("id"),
            week_of=data["week_of"],
            items=items,
            estimated_total=data.get("estimated_total"),
            store_sections=store_sections,
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
