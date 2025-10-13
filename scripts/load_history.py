#!/usr/bin/env python3
"""
Load meal history from CSV into SQLite database.

The CSV format is:
- First row: column headers (sunday, Monday, tuesday, etc.)
- Each subsequent row: one week of meals
- Columns: days of the week plus optional 'lunches' column

Usage:
    python scripts/load_history.py --input meal_history.csv
"""

import sqlite3
import csv
import logging
import argparse
from pathlib import Path
from datetime import datetime, timedelta
import sys

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)


def normalize_day_name(day: str) -> str:
    """Normalize day name from CSV headers."""
    day = day.strip().lower()
    day_mapping = {
        "sunday": "sunday",
        "monday": "monday",
        "tuesday": "tuesday",
        "wednesday": "wednesday",
        "thursday": "thursday",
        "friday": "friday",
        "saturday": "saturday",
        "lunches": "lunches",
    }
    return day_mapping.get(day, day)


def estimate_date_for_week(week_index: int, day_of_week: str) -> str:
    """
    Estimate a date for a historical week.

    Since the CSV doesn't have dates, we work backwards from today.
    Week 0 is most recent (this week), week 1 is last week, etc.

    Args:
        week_index: Week number (0 = most recent)
        day_of_week: Day name (e.g., "monday")

    Returns:
        ISO date string (YYYY-MM-DD)
    """
    today = datetime.now()

    # Find the most recent Monday
    days_since_monday = (today.weekday() - 0) % 7  # Monday = 0
    most_recent_monday = today - timedelta(days=days_since_monday)

    # Go back by week_index weeks
    target_week_monday = most_recent_monday - timedelta(weeks=week_index)

    # Map day name to offset from Monday
    day_offsets = {
        "monday": 0,
        "tuesday": 1,
        "wednesday": 2,
        "thursday": 3,
        "friday": 4,
        "saturday": 5,
        "sunday": 6,
        "lunches": 0,  # Default to Monday for lunch column
    }

    offset = day_offsets.get(day_of_week.lower(), 0)
    target_date = target_week_monday + timedelta(days=offset)

    return target_date.strftime("%Y-%m-%d")


def load_meal_history(csv_file: Path, db_file: Path):
    """
    Load meal history from CSV into SQLite.

    Args:
        csv_file: Path to meal history CSV
        db_file: Path to user_data.db
    """
    if not csv_file.exists():
        logger.error(f"CSV file not found: {csv_file}")
        sys.exit(1)

    logger.info(f"Loading meal history from {csv_file} into {db_file}")

    # Ensure database exists with schema
    db_file.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(db_file)
    cursor = conn.cursor()

    # Create table (same as in database.py)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS meal_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            date TEXT NOT NULL,
            meal_name TEXT NOT NULL,
            day_of_week TEXT,
            meal_type TEXT DEFAULT 'dinner'
        )
    """)
    conn.commit()

    # Clear existing history (for idempotent loading)
    cursor.execute("DELETE FROM meal_history")
    conn.commit()
    logger.info("Cleared existing meal history")

    total_count = 0

    with open(csv_file, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)

        # Normalize column names
        fieldnames = [normalize_day_name(name) for name in reader.fieldnames]

        for week_index, row in enumerate(reader):
            # Create normalized row with cleaned keys
            normalized_row = {}
            for old_key, new_key in zip(reader.fieldnames, fieldnames):
                normalized_row[new_key] = row[old_key]

            # Process each day column
            for day_name in ["sunday", "monday", "tuesday", "wednesday", "thursday", "friday", "saturday"]:
                if day_name not in normalized_row:
                    continue

                meal_name = normalized_row[day_name].strip()
                if not meal_name:
                    continue

                # Estimate date
                estimated_date = estimate_date_for_week(week_index, day_name)

                # Insert into database
                cursor.execute(
                    """
                    INSERT INTO meal_history (date, meal_name, day_of_week, meal_type)
                    VALUES (?, ?, ?, ?)
                    """,
                    (estimated_date, meal_name, day_name, "dinner"),
                )
                total_count += 1

            # Handle lunches column if present
            if "lunches" in normalized_row and normalized_row["lunches"].strip():
                lunch_meals = normalized_row["lunches"].strip()
                estimated_date = estimate_date_for_week(week_index, "monday")

                cursor.execute(
                    """
                    INSERT INTO meal_history (date, meal_name, day_of_week, meal_type)
                    VALUES (?, ?, ?, ?)
                    """,
                    (estimated_date, lunch_meals, "various", "lunch"),
                )
                total_count += 1

        conn.commit()

    conn.close()

    logger.info(f"Loaded {total_count} meals from history")


def main():
    parser = argparse.ArgumentParser(description="Load meal history into SQLite")
    parser.add_argument(
        "--input",
        type=Path,
        default="meal_history.csv",
        help="Input CSV file (default: meal_history.csv)",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default="data/user_data.db",
        help="Output SQLite database (default: data/user_data.db)",
    )

    args = parser.parse_args()

    load_meal_history(args.input, args.output)
    logger.info("Done!")


if __name__ == "__main__":
    main()
