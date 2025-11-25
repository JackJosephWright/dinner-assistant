"""
Database interface for the Meal Planning Assistant.

Manages two SQLite databases:
- recipes.db: Food.com dataset (read-only)
- user_data.db: Meal plans, preferences, history
"""

import sqlite3
import json
import logging
from typing import List, Optional, Dict, Any
from datetime import datetime
from pathlib import Path

from .models import Recipe, MealPlan, PlannedMeal, GroceryList, GroceryItem, MealEvent, UserProfile, Ingredient

logger = logging.getLogger(__name__)


class DatabaseInterface:
    """Interface for interacting with SQLite databases."""

    def __init__(self, db_dir: str = "data"):
        """
        Initialize database interface.

        Args:
            db_dir: Directory containing database files
        """
        self.db_dir = Path(db_dir)
        self.db_dir.mkdir(exist_ok=True)

        self.recipes_db = self.db_dir / "recipes.db"
        self.user_db = self.db_dir / "user_data.db"

        self._init_user_database()

    def _init_user_database(self):
        """Initialize user data database schema."""
        with sqlite3.connect(self.user_db) as conn:
            cursor = conn.cursor()

            # Meal plans table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS meal_plans (
                    id TEXT PRIMARY KEY,
                    week_of TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    preferences_applied TEXT,
                    meals_json TEXT NOT NULL
                )
            """)

            # Meal history table (parsed from CSV)
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS meal_history (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    date TEXT NOT NULL,
                    meal_name TEXT NOT NULL,
                    day_of_week TEXT,
                    meal_type TEXT DEFAULT 'dinner'
                )
            """)

            # Grocery lists table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS grocery_lists (
                    id TEXT PRIMARY KEY,
                    week_of TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    estimated_total REAL,
                    items_json TEXT NOT NULL,
                    extra_items_json TEXT
                )
            """)

            # Migration: Add extra_items_json if it doesn't exist
            try:
                cursor.execute("ALTER TABLE grocery_lists ADD COLUMN extra_items_json TEXT")
            except sqlite3.OperationalError:
                pass  # Column already exists

            # User preferences table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS user_preferences (
                    key TEXT PRIMARY KEY,
                    value TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                )
            """)

            # Shopping extras table (persistent user items)
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS shopping_extras (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    week_of TEXT NOT NULL,
                    name TEXT NOT NULL,
                    quantity TEXT,
                    category TEXT,
                    is_checked BOOLEAN DEFAULT 0,
                    created_at TEXT NOT NULL
                )
            """)

            # Meal events table (rich tracking)
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS meal_events (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,

                    date TEXT NOT NULL,
                    day_of_week TEXT NOT NULL,
                    meal_type TEXT DEFAULT 'dinner',

                    recipe_id TEXT NOT NULL,
                    recipe_name TEXT NOT NULL,
                    recipe_cuisine TEXT,
                    recipe_difficulty TEXT,

                    servings_planned INTEGER,
                    servings_actual INTEGER,
                    ingredients_snapshot TEXT,
                    modifications TEXT,
                    substitutions TEXT,

                    user_rating INTEGER,
                    cooking_time_actual INTEGER,
                    notes TEXT,
                    would_make_again BOOLEAN,

                    meal_plan_id TEXT,
                    created_at TEXT NOT NULL,

                    FOREIGN KEY (meal_plan_id) REFERENCES meal_plans(id)
                )
            """)

            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_meal_events_date
                ON meal_events(date)
            """)

            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_meal_events_recipe
                ON meal_events(recipe_id)
            """)

            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_meal_events_plan
                ON meal_events(meal_plan_id)
            """)

            # Unique index for UPSERT pattern: one meal per (date, meal_type)
            cursor.execute("""
                CREATE UNIQUE INDEX IF NOT EXISTS idx_meal_events_date_type
                ON meal_events(date, meal_type)
            """)

            # User profile table (single row for onboarding)
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS user_profile (
                    id INTEGER PRIMARY KEY DEFAULT 1,

                    household_size INTEGER DEFAULT 4,
                    cooking_for TEXT,

                    dietary_restrictions TEXT,
                    allergens TEXT,

                    favorite_cuisines TEXT,
                    disliked_ingredients TEXT,
                    preferred_proteins TEXT,
                    spice_tolerance TEXT DEFAULT 'medium',

                    max_weeknight_cooking_time INTEGER DEFAULT 45,
                    max_weekend_cooking_time INTEGER DEFAULT 90,
                    budget_per_week REAL,

                    variety_preference TEXT DEFAULT 'high',
                    health_focus TEXT,

                    onboarding_completed BOOLEAN DEFAULT FALSE,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,

                    CHECK (id = 1)
                )
            """)

            # Cooking guides cache (stores LLM-generated cooking guides)
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS cooking_guides (
                    recipe_id TEXT NOT NULL,
                    model_version TEXT NOT NULL,
                    guide_json TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    PRIMARY KEY (recipe_id, model_version)
                )
            """)

            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_cooking_guides_recipe
                ON cooking_guides(recipe_id)
            """)

            # Meal plan snapshots table (unified meal plan + grocery list storage)
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS meal_plan_snapshots (
                    id TEXT PRIMARY KEY,
                    user_id INTEGER NOT NULL,
                    week_of TEXT NOT NULL,
                    version INTEGER DEFAULT 1,
                    snapshot_json TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                )
            """)

            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_snapshots_user_week
                ON meal_plan_snapshots (user_id, week_of)
            """)

            # Users table for authentication
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS users (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    username TEXT UNIQUE NOT NULL,
                    password_hash TEXT NOT NULL,
                    created_at TEXT NOT NULL
                )
            """)

            conn.commit()
            logger.info("User database initialized")

    # ==================== Recipe Operations ====================

    def search_recipes(
        self,
        query: Optional[str] = None,
        max_time: Optional[int] = None,
        tags: Optional[List[str]] = None,
        exclude_ids: Optional[List[str]] = None,
        limit: int = 20,
    ) -> List[Recipe]:
        """
        Search recipes in the Food.com database.

        Args:
            query: Keywords to search in name/description
            max_time: Maximum cooking time in minutes
            tags: Required tags
            exclude_ids: Recipe IDs to exclude
            limit: Maximum number of results

        Returns:
            List of matching Recipe objects
        """
        with sqlite3.connect(self.recipes_db) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()

            sql = "SELECT * FROM recipes WHERE 1=1"
            params = []

            # Search query
            if query:
                sql += " AND (name LIKE ? OR description LIKE ?)"
                search_term = f"%{query}%"
                params.extend([search_term, search_term])

            # Time filter
            if max_time:
                time_tags = [
                    "15-minutes-or-less",
                    "30-minutes-or-less",
                    "60-minutes-or-less",
                    "4-hours-or-less",
                ]
                time_condition = " OR ".join([f"tags LIKE ?" for _ in time_tags])
                sql += f" AND ({time_condition})"
                params.extend([f"%{tag}%" for tag in time_tags])

            # Required tags
            if tags:
                for tag in tags:
                    sql += " AND tags LIKE ?"
                    params.append(f"%{tag}%")

            # Exclude recipes
            if exclude_ids:
                placeholders = ",".join(["?" for _ in exclude_ids])
                sql += f" AND id NOT IN ({placeholders})"
                params.extend(exclude_ids)

            sql += f" LIMIT ?"
            params.append(limit)

            cursor.execute(sql, params)
            rows = cursor.fetchall()

            recipes = []
            for row in rows:
                try:
                    recipe = self._row_to_recipe(row)
                    # Apply max_time filter post-query for accuracy
                    if max_time and recipe.estimated_time and recipe.estimated_time > max_time:
                        continue
                    recipes.append(recipe)
                except Exception as e:
                    logger.warning(f"Error parsing recipe {row['id']}: {e}")
                    continue

            return recipes

    def get_recipe(self, recipe_id: str) -> Optional[Recipe]:
        """
        Get a specific recipe by ID.

        Args:
            recipe_id: Recipe ID

        Returns:
            Recipe object or None if not found
        """
        with sqlite3.connect(self.recipes_db) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()

            cursor.execute("""
                SELECT id, name, description, ingredients, ingredients_raw,
                       ingredients_structured, steps, servings, serving_size, tags
                FROM recipes WHERE id = ?
            """, (recipe_id,))
            row = cursor.fetchone()

            if row:
                return self._row_to_recipe(row)
            return None

    def _row_to_recipe(self, row: sqlite3.Row) -> Recipe:
        """Convert database row to Recipe object."""
        # Parse ingredients_structured if present
        ingredients_structured = None
        if row["ingredients_structured"]:
            try:
                ing_data = json.loads(row["ingredients_structured"])
                ingredients_structured = [Ingredient(**ing) for ing in ing_data]
            except (json.JSONDecodeError, TypeError) as e:
                logger.warning(f"Failed to parse ingredients_structured for recipe {row['id']}: {e}")
                ingredients_structured = None

        return Recipe(
            id=str(row["id"]),
            name=row["name"],
            description=row["description"],
            ingredients=json.loads(row["ingredients"]) if row["ingredients"] else [],
            ingredients_raw=json.loads(row["ingredients_raw"]) if row["ingredients_raw"] else [],
            ingredients_structured=ingredients_structured,
            steps=json.loads(row["steps"]) if row["steps"] else [],
            servings=row["servings"] or 4,
            serving_size=row["serving_size"] or "",
            tags=json.loads(row["tags"]) if row["tags"] else [],
        )

    # ==================== Meal Plan Operations ====================

    def save_meal_plan(self, meal_plan: MealPlan) -> str:
        """
        Save a meal plan to the database.

        .. deprecated:: Phase 7
            This method writes to the legacy meal_plans table.
            New code should use save_snapshot() instead for snapshot-only architecture.
            This method is kept for backward compatibility with existing meal plans.

        Args:
            meal_plan: MealPlan object

        Returns:
            ID of saved meal plan
        """
        import warnings
        warnings.warn(
            "save_meal_plan() writes to legacy meal_plans table. "
            "Use save_snapshot() for new plans.",
            DeprecationWarning,
            stacklevel=2
        )

        if not meal_plan.id:
            meal_plan.id = f"mp_{meal_plan.week_of}_{datetime.now().strftime('%Y%m%d%H%M%S')}"

        with sqlite3.connect(self.user_db) as conn:
            cursor = conn.cursor()

            cursor.execute(
                """
                INSERT OR REPLACE INTO meal_plans
                (id, week_of, created_at, preferences_applied, meals_json)
                VALUES (?, ?, ?, ?, ?)
                """,
                (
                    meal_plan.id,
                    meal_plan.week_of,
                    meal_plan.created_at.isoformat(),
                    json.dumps(meal_plan.preferences_applied),
                    json.dumps([meal.to_dict() for meal in meal_plan.meals]),
                ),
            )

            # UPSERT meal_events for user history tracking
            # This creates/updates one meal_event per (date, meal_type) slot
            for meal in meal_plan.meals:
                # Get day of week from date
                meal_date = datetime.fromisoformat(meal.date)
                day_of_week = meal_date.strftime("%A")

                # UPSERT: Insert or update if (date, meal_type) already exists
                cursor.execute("""
                    INSERT INTO meal_events (
                        date, day_of_week, meal_type,
                        recipe_id, recipe_name, recipe_cuisine, recipe_difficulty,
                        servings_planned,
                        ingredients_snapshot,
                        meal_plan_id,
                        created_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    ON CONFLICT(date, meal_type) DO UPDATE SET
                        recipe_id = excluded.recipe_id,
                        recipe_name = excluded.recipe_name,
                        recipe_cuisine = excluded.recipe_cuisine,
                        recipe_difficulty = excluded.recipe_difficulty,
                        servings_planned = excluded.servings_planned,
                        ingredients_snapshot = excluded.ingredients_snapshot,
                        meal_plan_id = excluded.meal_plan_id
                """, (
                    meal.date,
                    day_of_week,
                    'dinner',  # Default meal type
                    meal.recipe.id if meal.recipe else meal.recipe_id,
                    meal.recipe.name if meal.recipe else '',
                    meal.recipe.cuisine if meal.recipe else None,
                    meal.recipe.difficulty if meal.recipe else None,
                    meal.servings,
                    json.dumps(meal.recipe.ingredients_raw) if meal.recipe else '[]',
                    meal_plan.id,
                    datetime.now().isoformat()
                ))

            conn.commit()

        logger.info(f"Saved meal plan {meal_plan.id} with {len(meal_plan.meals)} meal events")
        return meal_plan.id

    def get_meal_plan(self, plan_id: str) -> Optional[MealPlan]:
        """
        Get a meal plan by ID.

        Args:
            plan_id: Meal plan ID

        Returns:
            MealPlan object or None
        """
        with sqlite3.connect(self.user_db) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()

            cursor.execute("SELECT * FROM meal_plans WHERE id = ?", (plan_id,))
            row = cursor.fetchone()

            if row:
                return MealPlan(
                    id=row["id"],
                    week_of=row["week_of"],
                    created_at=datetime.fromisoformat(row["created_at"]),
                    preferences_applied=json.loads(row["preferences_applied"]),
                    meals=[PlannedMeal.from_dict(m) for m in json.loads(row["meals_json"])],
                )
            return None

    def get_recent_meal_plans(self, limit: int = 10) -> List[MealPlan]:
        """
        Get recent meal plans.

        Args:
            limit: Maximum number of plans to return

        Returns:
            List of MealPlan objects
        """
        with sqlite3.connect(self.user_db) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()

            cursor.execute(
                "SELECT * FROM meal_plans ORDER BY created_at DESC LIMIT ?",
                (limit,),
            )
            rows = cursor.fetchall()

            return [
                MealPlan(
                    id=row["id"],
                    week_of=row["week_of"],
                    created_at=datetime.fromisoformat(row["created_at"]),
                    preferences_applied=json.loads(row["preferences_applied"]),
                    meals=[PlannedMeal.from_dict(m) for m in json.loads(row["meals_json"])],
                )
                for row in rows
            ]

    def swap_meal_in_plan(
        self, plan_id: str, date: str, new_recipe_id: str
    ) -> Optional[MealPlan]:
        """
        Swap a meal in an existing meal plan.

        .. deprecated:: Phase 7
            This method modifies the legacy meal_plans table.
            New code should update snapshot['planned_meals'] instead for snapshot-only architecture.
            This method is kept for backward compatibility with existing plans.

        Args:
            plan_id: Meal plan ID
            date: Date of meal to swap (YYYY-MM-DD)
            new_recipe_id: New recipe ID

        Returns:
            Updated MealPlan object or None if not found
        """
        import warnings
        warnings.warn(
            "swap_meal_in_plan() modifies legacy meal_plans table. "
            "Update snapshot['planned_meals'] for new plans.",
            DeprecationWarning,
            stacklevel=2
        )

        # Get the meal plan
        meal_plan = self.get_meal_plan(plan_id)
        if not meal_plan:
            return None

        # Get the new recipe
        new_recipe = self.get_recipe(new_recipe_id)
        if not new_recipe:
            logger.warning(f"Recipe {new_recipe_id} not found")
            return None

        # Find and swap the meal
        old_recipe = None
        for i, meal in enumerate(meal_plan.meals):
            if meal.date == date:
                old_recipe = meal.recipe  # Store old recipe for shopping list update
                meal_plan.meals[i] = PlannedMeal(
                    date=date,
                    meal_type=meal.meal_type,
                    recipe=new_recipe,
                    servings=meal.servings,
                    notes=meal.notes,
                )
                break
        else:
            logger.warning(f"No meal found for date {date} in plan {plan_id}")
            return None

        # Save updated plan
        self.save_meal_plan(meal_plan)
        logger.info(f"Swapped meal on {date} in plan {plan_id} to {new_recipe.name}")

        # Update grocery list incrementally (if one exists)
        grocery_list = self.get_grocery_list_by_week(meal_plan.week_of)
        if grocery_list and old_recipe:
            # Remove old recipe ingredients
            grocery_list.remove_recipe_ingredients(old_recipe.name)
            logger.info(f"Removed ingredients for '{old_recipe.name}' from shopping list")

            # Add new recipe ingredients
            grocery_list.add_recipe_ingredients(new_recipe)
            logger.info(f"Added ingredients for '{new_recipe.name}' to shopping list")

            # Save updated grocery list
            self.save_grocery_list(grocery_list)
            logger.info(f"Updated grocery list {grocery_list.id} incrementally")

        return meal_plan

    # ==================== Meal History Operations ====================

    def get_meal_history(self, weeks_back: int = 8) -> List[PlannedMeal]:
        """
        Get meal history from the past N weeks.

        Args:
            weeks_back: Number of weeks to look back

        Returns:
            List of PlannedMeal objects
        """
        with sqlite3.connect(self.user_db) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()

            cursor.execute(
                """
                SELECT * FROM meal_history
                ORDER BY date DESC
                LIMIT ?
                """,
                (weeks_back * 7,),
            )
            rows = cursor.fetchall()

            meals = []
            for row in rows:
                # Create a minimal Recipe object for history
                # (history doesn't have full recipe details)
                recipe = Recipe(
                    id="",  # No ID for historical meals
                    name=row["meal_name"],
                    description="",
                    ingredients=[],
                    ingredients_raw=[],
                    ingredients_structured=[],
                    steps=[],
                    servings=4,
                    tags=[],
                )

                meals.append(
                    PlannedMeal(
                        date=row["date"],
                        meal_type=row["meal_type"],
                        recipe=recipe,
                        servings=4,  # Default
                        notes=None,
                    )
                )

            return meals

    def add_meal_to_history(
        self, date: str, meal_name: str, day_of_week: str, meal_type: str = "dinner"
    ):
        """Add a meal to the history."""
        with sqlite3.connect(self.user_db) as conn:
            cursor = conn.cursor()

            cursor.execute(
                """
                INSERT INTO meal_history (date, meal_name, day_of_week, meal_type)
                VALUES (?, ?, ?, ?)
                """,
                (date, meal_name, day_of_week, meal_type),
            )
            conn.commit()

    # ==================== Grocery List Operations ====================

    def save_grocery_list(self, grocery_list: GroceryList) -> str:
        """
        Save a grocery list to the database.

        .. deprecated:: Phase 7
            This method writes to the legacy grocery_lists table.
            New code should update snapshot['grocery_list'] instead for snapshot-only architecture.
            This method is kept for backward compatibility with existing lists.

        Args:
            grocery_list: GroceryList object

        Returns:
            ID of saved grocery list
        """
        import warnings
        warnings.warn(
            "save_grocery_list() writes to legacy grocery_lists table. "
            "Update snapshot['grocery_list'] for new lists.",
            DeprecationWarning,
            stacklevel=2
        )

        if not grocery_list.id:
            grocery_list.id = f"gl_{grocery_list.week_of}_{datetime.now().strftime('%Y%m%d%H%M%S')}"

        with sqlite3.connect(self.user_db) as conn:
            cursor = conn.cursor()

            cursor.execute(
                """
                INSERT OR REPLACE INTO grocery_lists
                (id, week_of, created_at, estimated_total, items_json, extra_items_json)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    grocery_list.id,
                    grocery_list.week_of,
                    grocery_list.created_at.isoformat(),
                    grocery_list.estimated_total,
                    json.dumps([item.to_dict() for item in grocery_list.items]),
                    json.dumps([item.to_dict() for item in grocery_list.extra_items]),
                ),
            )
            conn.commit()

        logger.info(f"Saved grocery list {grocery_list.id}")
        return grocery_list.id

    def get_grocery_list(self, list_id: str) -> Optional[GroceryList]:
        """Get a grocery list by ID."""
        with sqlite3.connect(self.user_db) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()

            cursor.execute("SELECT * FROM grocery_lists WHERE id = ?", (list_id,))
            row = cursor.fetchone()

            if row:
                items = [GroceryItem.from_dict(i) for i in json.loads(row["items_json"])]
                extra_items = []
                if row["extra_items_json"]:
                    extra_items = [GroceryItem.from_dict(i) for i in json.loads(row["extra_items_json"])]

                return GroceryList(
                    id=row["id"],
                    week_of=row["week_of"],
                    created_at=datetime.fromisoformat(row["created_at"]),
                    estimated_total=row["estimated_total"],
                    items=items,
                    extra_items=extra_items,
                )
            return None

    def get_grocery_list_by_week(self, week_of: str) -> Optional[GroceryList]:
        """
        Get a grocery list by week_of date.

        Args:
            week_of: Week start date (YYYY-MM-DD)

        Returns:
            GroceryList object or None if not found
        """
        with sqlite3.connect(self.user_db) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()

            cursor.execute(
                "SELECT * FROM grocery_lists WHERE week_of = ? ORDER BY created_at DESC LIMIT 1",
                (week_of,)
            )
            row = cursor.fetchone()

            if row:
                items = [GroceryItem.from_dict(i) for i in json.loads(row["items_json"])]
                extra_items = []
                if row["extra_items_json"]:
                    extra_items = [GroceryItem.from_dict(i) for i in json.loads(row["extra_items_json"])]

                return GroceryList(
                    id=row["id"],
                    week_of=row["week_of"],
                    created_at=datetime.fromisoformat(row["created_at"]),
                    estimated_total=row["estimated_total"],
                    items=items,
                    extra_items=extra_items,
                )
            return None

    def get_grocery_list_by_meal_plan(self, meal_plan_id: str) -> Optional[GroceryList]:
        """
        Get the most recent grocery list for a meal plan.

        Looks up the meal plan to get its week_of, then finds the
        corresponding grocery list.

        Args:
            meal_plan_id: Meal plan ID

        Returns:
            GroceryList object or None if not found
        """
        # First get the meal plan to find its week_of
        with sqlite3.connect(self.user_db) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()

            cursor.execute("SELECT week_of FROM meal_plans WHERE id = ?", (meal_plan_id,))
            row = cursor.fetchone()

            if not row:
                return None

            week_of = row["week_of"]

        # Now get the grocery list for that week
        return self.get_grocery_list_by_week(week_of)

    # ==================== Preferences Operations ====================

    def get_preference(self, key: str) -> Optional[str]:
        """Get a user preference by key."""
        with sqlite3.connect(self.user_db) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT value FROM user_preferences WHERE key = ?", (key,))
            row = cursor.fetchone()
            return row[0] if row else None

    def set_preference(self, key: str, value: str):
        """Set a user preference."""
        with sqlite3.connect(self.user_db) as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                INSERT OR REPLACE INTO user_preferences (key, value, updated_at)
                VALUES (?, ?, ?)
                """,
                (key, value, datetime.now().isoformat()),
            )
            conn.commit()

    def get_all_preferences(self) -> Dict[str, str]:
        """Get all user preferences."""
        with sqlite3.connect(self.user_db) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute("SELECT key, value FROM user_preferences")
            rows = cursor.fetchall()
            return {row["key"]: row["value"] for row in rows}

    # ==================== Meal Events Operations ====================

    def add_meal_event(self, event: MealEvent) -> int:
        """
        Add a new meal event to the database.

        Args:
            event: MealEvent object

        Returns:
            ID of created event
        """
        with sqlite3.connect(self.user_db) as conn:
            cursor = conn.cursor()

            cursor.execute(
                """
                INSERT INTO meal_events
                (date, day_of_week, meal_type, recipe_id, recipe_name,
                 recipe_cuisine, recipe_difficulty, servings_planned,
                 servings_actual, ingredients_snapshot, modifications,
                 substitutions, user_rating, cooking_time_actual,
                 notes, would_make_again, meal_plan_id, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    event.date,
                    event.day_of_week,
                    event.meal_type,
                    event.recipe_id,
                    event.recipe_name,
                    event.recipe_cuisine,
                    event.recipe_difficulty,
                    event.servings_planned,
                    event.servings_actual,
                    json.dumps(event.ingredients_snapshot),
                    json.dumps(event.modifications),
                    json.dumps(event.substitutions),
                    event.user_rating,
                    event.cooking_time_actual,
                    event.notes,
                    event.would_make_again,
                    event.meal_plan_id,
                    event.created_at.isoformat(),
                ),
            )
            conn.commit()
            event_id = cursor.lastrowid

        logger.info(f"Added meal event {event_id} for {event.recipe_name} on {event.date}")
        return event_id

    def update_meal_event(self, event_id: int, updates: Dict[str, Any]) -> bool:
        """
        Update an existing meal event.

        Args:
            event_id: ID of event to update
            updates: Dictionary of fields to update

        Returns:
            True if successful
        """
        # Build dynamic UPDATE query
        set_clauses = []
        params = []

        for key, value in updates.items():
            if key in ["ingredients_snapshot", "modifications", "substitutions"]:
                value = json.dumps(value)
            elif key == "created_at" and isinstance(value, datetime):
                value = value.isoformat()

            set_clauses.append(f"{key} = ?")
            params.append(value)

        params.append(event_id)
        sql = f"UPDATE meal_events SET {', '.join(set_clauses)} WHERE id = ?"

        with sqlite3.connect(self.user_db) as conn:
            cursor = conn.cursor()
            cursor.execute(sql, params)
            conn.commit()

        logger.info(f"Updated meal event {event_id}")
        return True

    def get_meal_events(self, weeks_back: int = 8) -> List[MealEvent]:
        """
        Get meal events from the past N weeks.

        Args:
            weeks_back: Number of weeks to look back

        Returns:
            List of MealEvent objects
        """
        with sqlite3.connect(self.user_db) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()

            cursor.execute(
                """
                SELECT * FROM meal_events
                WHERE date >= date('now', '-' || ? || ' days')
                ORDER BY date DESC
                """,
                (weeks_back * 7,),
            )
            rows = cursor.fetchall()

            events = []
            for row in rows:
                events.append(
                    MealEvent(
                        id=row["id"],
                        date=row["date"],
                        day_of_week=row["day_of_week"],
                        meal_type=row["meal_type"],
                        recipe_id=row["recipe_id"],
                        recipe_name=row["recipe_name"],
                        recipe_cuisine=row["recipe_cuisine"],
                        recipe_difficulty=row["recipe_difficulty"],
                        servings_planned=row["servings_planned"],
                        servings_actual=row["servings_actual"],
                        ingredients_snapshot=json.loads(row["ingredients_snapshot"]) if row["ingredients_snapshot"] else [],
                        modifications=json.loads(row["modifications"]) if row["modifications"] else {},
                        substitutions=json.loads(row["substitutions"]) if row["substitutions"] else {},
                        user_rating=row["user_rating"],
                        cooking_time_actual=row["cooking_time_actual"],
                        notes=row["notes"],
                        would_make_again=row["would_make_again"],
                        meal_plan_id=row["meal_plan_id"],
                        created_at=datetime.fromisoformat(row["created_at"]),
                    )
                )

            return events

    def get_favorite_recipes(self, limit: int = 20) -> List[Dict[str, Any]]:
        """
        Get user's favorite recipes based on ratings and frequency.

        Args:
            limit: Maximum number of recipes to return

        Returns:
            List of dictionaries with recipe stats
        """
        with sqlite3.connect(self.user_db) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()

            cursor.execute(
                """
                SELECT recipe_id, recipe_name,
                       AVG(user_rating) as avg_rating,
                       COUNT(*) as times_cooked
                FROM meal_events
                WHERE user_rating IS NOT NULL
                GROUP BY recipe_id
                ORDER BY avg_rating DESC, times_cooked DESC
                LIMIT ?
                """,
                (limit,),
            )
            rows = cursor.fetchall()

            return [
                {
                    "recipe_id": row["recipe_id"],
                    "recipe_name": row["recipe_name"],
                    "avg_rating": row["avg_rating"],
                    "times_cooked": row["times_cooked"],
                }
                for row in rows
            ]

    def get_recent_meals(self, days_back: int = 14) -> List[MealEvent]:
        """
        Get meals from the past N days for variety enforcement.

        Args:
            days_back: Number of days to look back

        Returns:
            List of MealEvent objects
        """
        with sqlite3.connect(self.user_db) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()

            cursor.execute(
                """
                SELECT * FROM meal_events
                WHERE date >= date('now', '-' || ? || ' days')
                ORDER BY date DESC
                """,
                (days_back,),
            )
            rows = cursor.fetchall()

            events = []
            for row in rows:
                events.append(
                    MealEvent(
                        id=row["id"],
                        date=row["date"],
                        day_of_week=row["day_of_week"],
                        meal_type=row["meal_type"],
                        recipe_id=row["recipe_id"],
                        recipe_name=row["recipe_name"],
                        recipe_cuisine=row["recipe_cuisine"],
                        recipe_difficulty=row["recipe_difficulty"],
                        servings_planned=row["servings_planned"],
                        servings_actual=row["servings_actual"],
                        ingredients_snapshot=json.loads(row["ingredients_snapshot"]) if row["ingredients_snapshot"] else [],
                        modifications=json.loads(row["modifications"]) if row["modifications"] else {},
                        substitutions=json.loads(row["substitutions"]) if row["substitutions"] else {},
                        user_rating=row["user_rating"],
                        cooking_time_actual=row["cooking_time_actual"],
                        notes=row["notes"],
                        would_make_again=row["would_make_again"],
                        meal_plan_id=row["meal_plan_id"],
                        created_at=datetime.fromisoformat(row["created_at"]),
                    )
                )

            return events

    def get_cuisine_preferences(self) -> Dict[str, Dict[str, Any]]:
        """
        Get user's cuisine preferences based on frequency and ratings.

        Returns:
            Dictionary mapping cuisine to stats (frequency, avg_rating)
        """
        with sqlite3.connect(self.user_db) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()

            cursor.execute(
                """
                SELECT recipe_cuisine,
                       COUNT(*) as frequency,
                       AVG(user_rating) as avg_rating
                FROM meal_events
                WHERE recipe_cuisine IS NOT NULL
                GROUP BY recipe_cuisine
                ORDER BY frequency DESC, avg_rating DESC
                """
            )
            rows = cursor.fetchall()

            return {
                row["recipe_cuisine"]: {
                    "frequency": row["frequency"],
                    "avg_rating": row["avg_rating"],
                }
                for row in rows
            }

    # ==================== User Profile Operations ====================

    def get_user_profile(self) -> Optional[UserProfile]:
        """
        Get the user profile (single row).

        Returns:
            UserProfile object or None if not set
        """
        with sqlite3.connect(self.user_db) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()

            cursor.execute("SELECT * FROM user_profile WHERE id = 1")
            row = cursor.fetchone()

            if row:
                return UserProfile(
                    id=row["id"],
                    household_size=row["household_size"],
                    cooking_for=json.loads(row["cooking_for"]) if row["cooking_for"] else {"adults": 2, "kids": 2},
                    dietary_restrictions=json.loads(row["dietary_restrictions"]) if row["dietary_restrictions"] else [],
                    allergens=json.loads(row["allergens"]) if row["allergens"] else [],
                    favorite_cuisines=json.loads(row["favorite_cuisines"]) if row["favorite_cuisines"] else [],
                    disliked_ingredients=json.loads(row["disliked_ingredients"]) if row["disliked_ingredients"] else [],
                    preferred_proteins=json.loads(row["preferred_proteins"]) if row["preferred_proteins"] else [],
                    spice_tolerance=row["spice_tolerance"],
                    max_weeknight_cooking_time=row["max_weeknight_cooking_time"],
                    max_weekend_cooking_time=row["max_weekend_cooking_time"],
                    budget_per_week=row["budget_per_week"],
                    variety_preference=row["variety_preference"],
                    health_focus=row["health_focus"],
                    onboarding_completed=bool(row["onboarding_completed"]),
                    created_at=datetime.fromisoformat(row["created_at"]),
                    updated_at=datetime.fromisoformat(row["updated_at"]),
                )
            return None

    def save_user_profile(self, profile: UserProfile) -> bool:
        """
        Save or update the user profile.

        Args:
            profile: UserProfile object

        Returns:
            True if successful
        """
        profile.updated_at = datetime.now()

        with sqlite3.connect(self.user_db) as conn:
            cursor = conn.cursor()

            # Check if profile exists
            cursor.execute("SELECT id FROM user_profile WHERE id = 1")
            exists = cursor.fetchone() is not None

            if exists:
                cursor.execute(
                    """
                    UPDATE user_profile SET
                        household_size = ?,
                        cooking_for = ?,
                        dietary_restrictions = ?,
                        allergens = ?,
                        favorite_cuisines = ?,
                        disliked_ingredients = ?,
                        preferred_proteins = ?,
                        spice_tolerance = ?,
                        max_weeknight_cooking_time = ?,
                        max_weekend_cooking_time = ?,
                        budget_per_week = ?,
                        variety_preference = ?,
                        health_focus = ?,
                        onboarding_completed = ?,
                        updated_at = ?
                    WHERE id = 1
                    """,
                    (
                        profile.household_size,
                        json.dumps(profile.cooking_for),
                        json.dumps(profile.dietary_restrictions),
                        json.dumps(profile.allergens),
                        json.dumps(profile.favorite_cuisines),
                        json.dumps(profile.disliked_ingredients),
                        json.dumps(profile.preferred_proteins),
                        profile.spice_tolerance,
                        profile.max_weeknight_cooking_time,
                        profile.max_weekend_cooking_time,
                        profile.budget_per_week,
                        profile.variety_preference,
                        profile.health_focus,
                        profile.onboarding_completed,
                        profile.updated_at.isoformat(),
                    ),
                )
            else:
                cursor.execute(
                    """
                    INSERT INTO user_profile
                    (id, household_size, cooking_for, dietary_restrictions,
                     allergens, favorite_cuisines, disliked_ingredients,
                     preferred_proteins, spice_tolerance,
                     max_weeknight_cooking_time, max_weekend_cooking_time,
                     budget_per_week, variety_preference, health_focus,
                     onboarding_completed, created_at, updated_at)
                    VALUES (1, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        profile.household_size,
                        json.dumps(profile.cooking_for),
                        json.dumps(profile.dietary_restrictions),
                        json.dumps(profile.allergens),
                        json.dumps(profile.favorite_cuisines),
                        json.dumps(profile.disliked_ingredients),
                        json.dumps(profile.preferred_proteins),
                        profile.spice_tolerance,
                        profile.max_weeknight_cooking_time,
                        profile.max_weekend_cooking_time,
                        profile.budget_per_week,
                        profile.variety_preference,
                        profile.health_focus,
                        profile.onboarding_completed,
                        profile.created_at.isoformat(),
                        profile.updated_at.isoformat(),
                    ),
                )
            conn.commit()

        logger.info("Saved user profile")
        return True

    def is_onboarded(self) -> bool:
        """
        Check if user has completed onboarding.

        Returns:
            True if onboarding is complete
        """
        profile = self.get_user_profile()
        return profile.onboarding_completed if profile else False

    # ==================== Cooking Guides Cache ====================

    def get_cached_cooking_guide(self, recipe_id: str, model_version: str) -> Optional[Dict[str, Any]]:
        """
        Get a cached cooking guide for a recipe.

        Args:
            recipe_id: Recipe ID
            model_version: Model version used to generate the guide

        Returns:
            Cached guide dictionary or None if not found
        """
        with sqlite3.connect(self.user_db) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()

            cursor.execute(
                "SELECT guide_json FROM cooking_guides WHERE recipe_id = ? AND model_version = ?",
                (recipe_id, model_version)
            )
            row = cursor.fetchone()

            if row:
                return json.loads(row["guide_json"])
            return None

    def save_cooking_guide(self, recipe_id: str, model_version: str, guide: Dict[str, Any]):
        """
        Save a cooking guide to the cache.

        Args:
            recipe_id: Recipe ID
            model_version: Model version used to generate the guide
            guide: Guide dictionary to cache
        """
        with sqlite3.connect(self.user_db) as conn:
            cursor = conn.cursor()

            cursor.execute(
                """
                INSERT OR REPLACE INTO cooking_guides
                (recipe_id, model_version, guide_json, created_at)
                VALUES (?, ?, ?, ?)
                """,
                (
                    recipe_id,
                    model_version,
                    json.dumps(guide),
                    datetime.now().isoformat(),
                )
            )
            conn.commit()

        logger.info(f"Cached cooking guide for recipe {recipe_id}")

    # ==================== Shopping Extras Operations ====================

    def add_shopping_extra(self, week_of: str, item: GroceryItem) -> int:
        """Add an extra item to the shopping list."""
        with sqlite3.connect(self.user_db) as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                INSERT INTO shopping_extras (week_of, name, quantity, category, is_checked, created_at)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    week_of,
                    item.name,
                    item.quantity,
                    item.category,
                    False,
                    datetime.now().isoformat()
                )
            )
            conn.commit()
            return cursor.lastrowid

    def get_shopping_extras(self, week_of: str) -> List[GroceryItem]:
        """Get all extra items for a specific week."""
        with sqlite3.connect(self.user_db) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute(
                "SELECT * FROM shopping_extras WHERE week_of = ? ORDER BY created_at",
                (week_of,)
            )
            rows = cursor.fetchall()
            
            items = []
            for row in rows:
                items.append(GroceryItem(
                    name=row["name"],
                    quantity=row["quantity"],
                    category=row["category"],
                    recipe_sources=["User request"],
                    notes="Extra item"
                ))
            return items

    def clear_shopping_extras(self, week_of: str):
        """Clear all extra items for a specific week."""
        with sqlite3.connect(self.user_db) as conn:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM shopping_extras WHERE week_of = ?", (week_of,))
            conn.commit()

    # ==================== Snapshot Operations ====================

    def save_snapshot(self, snapshot: Dict) -> str:
        """
        Save a meal plan snapshot (unified meal plan + grocery list storage).

        Args:
            snapshot: Snapshot dictionary containing:
                - id (optional): Snapshot ID (auto-generated if missing)
                - user_id: User ID
                - week_of: Week start date (YYYY-MM-DD)
                - version: Schema version (default: 1)
                - snapshot_json or all other fields: Will be stored as JSON
                - created_at (optional): ISO timestamp (auto-generated if missing)
                - updated_at (optional): ISO timestamp (auto-generated if missing)

        Returns:
            Snapshot ID
        """
        # Auto-generate ID if missing
        if not snapshot.get('id'):
            week_of = snapshot['week_of']
            timestamp = datetime.now().strftime('%Y%m%d%H%M%S')
            snapshot['id'] = f"mp_{week_of}_{timestamp}"

        # Set timestamps if missing
        now = datetime.now().isoformat()
        if not snapshot.get('created_at'):
            snapshot['created_at'] = now
        snapshot['updated_at'] = now

        # Ensure version is set
        if not snapshot.get('version'):
            snapshot['version'] = 1

        with sqlite3.connect(self.user_db) as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                INSERT OR REPLACE INTO meal_plan_snapshots
                (id, user_id, week_of, version, snapshot_json, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    snapshot['id'],
                    snapshot['user_id'],
                    snapshot['week_of'],
                    snapshot['version'],
                    json.dumps(snapshot),
                    snapshot['created_at'],
                    snapshot['updated_at'],
                )
            )
            conn.commit()

        logger.info(f"Saved snapshot {snapshot['id']} for user {snapshot['user_id']}, week {snapshot['week_of']}")
        return snapshot['id']

    def get_snapshot(self, snapshot_id: str) -> Optional[Dict]:
        """
        Get a snapshot by ID.

        Args:
            snapshot_id: Snapshot ID

        Returns:
            Snapshot dictionary or None if not found
        """
        with sqlite3.connect(self.user_db) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()

            cursor.execute(
                "SELECT snapshot_json FROM meal_plan_snapshots WHERE id = ?",
                (snapshot_id,)
            )
            row = cursor.fetchone()

            if row:
                return json.loads(row['snapshot_json'])

        return None

    def get_user_snapshots(self, user_id: int, limit: int = 10) -> List[Dict]:
        """
        Get recent snapshots for a user.

        Args:
            user_id: User ID
            limit: Maximum number of snapshots to return (default: 10)

        Returns:
            List of snapshot dictionaries, ordered by created_at DESC
        """
        with sqlite3.connect(self.user_db) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()

            cursor.execute(
                """
                SELECT snapshot_json FROM meal_plan_snapshots
                WHERE user_id = ?
                ORDER BY created_at DESC
                LIMIT ?
                """,
                (user_id, limit)
            )
            rows = cursor.fetchall()

            return [json.loads(row['snapshot_json']) for row in rows]

    # ==================== User Authentication Operations ====================

    def create_user(self, username: str, password_hash: str) -> Optional[int]:
        """
        Create a new user.

        Args:
            username: Unique username
            password_hash: Hashed password (use werkzeug.security.generate_password_hash)

        Returns:
            User ID if created, None if username already exists
        """
        try:
            with sqlite3.connect(self.user_db) as conn:
                cursor = conn.cursor()
                cursor.execute(
                    """
                    INSERT INTO users (username, password_hash, created_at)
                    VALUES (?, ?, ?)
                    """,
                    (username, password_hash, datetime.now().isoformat())
                )
                conn.commit()
                user_id = cursor.lastrowid
                logger.info(f"Created user: {username} (ID: {user_id})")
                return user_id
        except sqlite3.IntegrityError:
            logger.warning(f"Username already exists: {username}")
            return None

    def get_user_by_username(self, username: str) -> Optional[Dict[str, Any]]:
        """
        Get user by username.

        Args:
            username: Username to look up

        Returns:
            Dict with id, username, password_hash, created_at or None if not found
        """
        with sqlite3.connect(self.user_db) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute(
                "SELECT id, username, password_hash, created_at FROM users WHERE username = ?",
                (username,)
            )
            row = cursor.fetchone()
            if row:
                return dict(row)
            return None

    def get_user_by_id(self, user_id: int) -> Optional[Dict[str, Any]]:
        """
        Get user by ID.

        Args:
            user_id: User ID to look up

        Returns:
            Dict with id, username, password_hash, created_at or None if not found
        """
        with sqlite3.connect(self.user_db) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute(
                "SELECT id, username, password_hash, created_at FROM users WHERE id = ?",
                (user_id,)
            )
            row = cursor.fetchone()
            if row:
                return dict(row)
            return None
