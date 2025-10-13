#!/usr/bin/env python3
"""
Database migration script for meal events system.

This script:
1. Backs up the existing user_data.db
2. Initializes new tables (meal_events, user_profile)
3. Optionally migrates old meal_history data to meal_events

Usage:
    python3 scripts/migrate_database.py [--migrate-history]
"""

import sys
import shutil
import argparse
import logging
from pathlib import Path
from datetime import datetime

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from src.data.database import DatabaseInterface
from src.data.models import MealEvent

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


def backup_database(db_path: Path) -> Path:
    """
    Create a backup of the database.

    Args:
        db_path: Path to database file

    Returns:
        Path to backup file
    """
    if not db_path.exists():
        logger.warning(f"Database {db_path} does not exist, skipping backup")
        return None

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_path = db_path.parent / f"{db_path.stem}_backup_{timestamp}{db_path.suffix}"

    shutil.copy2(db_path, backup_path)
    logger.info(f"Created backup: {backup_path}")

    return backup_path


def migrate_history_to_events(db: DatabaseInterface) -> int:
    """
    Migrate old meal_history records to meal_events table.

    Args:
        db: Database interface

    Returns:
        Number of records migrated
    """
    logger.info("Migrating old meal_history to meal_events...")

    try:
        # Get old history
        old_meals = db.get_meal_history(weeks_back=52)  # Get a year

        if not old_meals:
            logger.info("No meal history to migrate")
            return 0

        migrated = 0

        for meal in old_meals:
            try:
                # Create minimal meal event from history
                # Note: Old history lacks recipe_id, ingredients, etc.
                event = MealEvent(
                    date=meal.date,
                    day_of_week=datetime.fromisoformat(meal.date).strftime("%A"),
                    meal_type=meal.meal_type,
                    recipe_id=meal.recipe_id if meal.recipe_id else "unknown",
                    recipe_name=meal.recipe_name,
                    recipe_cuisine=None,
                    recipe_difficulty=None,
                    servings_planned=meal.servings,
                    created_at=datetime.now(),
                )

                db.add_meal_event(event)
                migrated += 1

            except Exception as e:
                logger.warning(f"Failed to migrate meal {meal.recipe_name} on {meal.date}: {e}")
                continue

        logger.info(f"Successfully migrated {migrated} meal history records")
        return migrated

    except Exception as e:
        logger.error(f"Error during migration: {e}")
        return 0


def initialize_tables(db_dir: str) -> bool:
    """
    Initialize new database tables.

    Args:
        db_dir: Directory containing databases

    Returns:
        True if successful
    """
    try:
        logger.info("Initializing new database tables...")

        # Create database interface (this will run _init_user_database)
        db = DatabaseInterface(db_dir=db_dir)

        logger.info("Successfully initialized tables: meal_events, user_profile")
        return True

    except Exception as e:
        logger.error(f"Error initializing tables: {e}")
        return False


def verify_migration(db: DatabaseInterface):
    """
    Verify the migration was successful.

    Args:
        db: Database interface
    """
    logger.info("Verifying migration...")

    try:
        # Check if tables exist by trying to query them
        events = db.get_meal_events(weeks_back=1)
        profile = db.get_user_profile()

        logger.info(f"✅ meal_events table: OK ({len(events)} events)")
        logger.info(f"✅ user_profile table: OK ({'exists' if profile else 'empty'})")

    except Exception as e:
        logger.error(f"❌ Verification failed: {e}")
        raise


def main():
    """Main migration workflow."""
    parser = argparse.ArgumentParser(
        description="Migrate database to meal events system"
    )
    parser.add_argument(
        "--migrate-history",
        action="store_true",
        help="Migrate old meal_history data to meal_events",
    )
    parser.add_argument(
        "--db-dir",
        default="data",
        help="Database directory (default: data)",
    )

    args = parser.parse_args()

    logger.info("=" * 60)
    logger.info("Database Migration for Meal Events System")
    logger.info("=" * 60)

    db_dir = Path(args.db_dir)
    user_db_path = db_dir / "user_data.db"

    # Step 1: Backup existing database
    logger.info("\n[1/4] Backing up database...")
    backup_path = backup_database(user_db_path)

    # Step 2: Initialize new tables
    logger.info("\n[2/4] Initializing new tables...")
    if not initialize_tables(str(db_dir)):
        logger.error("❌ Failed to initialize tables")
        return 1

    # Step 3: Migrate history (optional)
    if args.migrate_history:
        logger.info("\n[3/4] Migrating meal history...")
        db = DatabaseInterface(db_dir=str(db_dir))
        migrated_count = migrate_history_to_events(db)
        logger.info(f"Migrated {migrated_count} records")
    else:
        logger.info("\n[3/4] Skipping history migration (use --migrate-history to enable)")

    # Step 4: Verify migration
    logger.info("\n[4/4] Verifying migration...")
    db = DatabaseInterface(db_dir=str(db_dir))
    verify_migration(db)

    logger.info("\n" + "=" * 60)
    logger.info("✅ Migration completed successfully!")
    logger.info("=" * 60)

    if backup_path:
        logger.info(f"\n📦 Backup saved to: {backup_path}")

    logger.info("""
Next steps:
1. Run onboarding flow for new users
2. Start planning meals with rich event tracking
3. All agents will now learn from meal_events
""")

    return 0


if __name__ == "__main__":
    sys.exit(main())
