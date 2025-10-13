#!/usr/bin/env python3
"""
Load Food.com recipes from CSV into SQLite database.

Usage:
    python scripts/load_recipes.py --input food_com_recipes.csv
"""

import sqlite3
import csv
import json
import logging
import argparse
from pathlib import Path
import sys

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)


def parse_list_field(field: str) -> list:
    """Parse CSV list field (comma-separated values)."""
    if not field or field.strip() == "":
        return []

    # Handle JSON array format
    if field.strip().startswith("["):
        try:
            return json.loads(field)
        except json.JSONDecodeError:
            pass

    # Handle comma-separated format
    return [item.strip() for item in field.split(",") if item.strip()]


def create_recipes_table(conn: sqlite3.Connection):
    """Create recipes table schema."""
    cursor = conn.cursor()

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS recipes (
            id TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            description TEXT,
            ingredients TEXT,
            ingredients_raw TEXT,
            steps TEXT,
            servings INTEGER,
            serving_size TEXT,
            tags TEXT
        )
    """)

    # Create indexes for common queries
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_name ON recipes(name)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_tags ON recipes(tags)")

    conn.commit()
    logger.info("Created recipes table")


def load_recipes(csv_file: Path, db_file: Path, batch_size: int = 1000):
    """
    Load recipes from CSV into SQLite.

    Args:
        csv_file: Path to Food.com CSV file
        db_file: Path to output SQLite database
        batch_size: Number of rows to insert at once
    """
    if not csv_file.exists():
        logger.error(f"CSV file not found: {csv_file}")
        sys.exit(1)

    logger.info(f"Loading recipes from {csv_file} into {db_file}")

    conn = sqlite3.connect(db_file)
    create_recipes_table(conn)

    cursor = conn.cursor()
    batch = []
    total_count = 0
    error_count = 0

    with open(csv_file, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)

        for row in reader:
            try:
                # Parse list fields
                ingredients = parse_list_field(row.get("ingredients", ""))
                ingredients_raw = parse_list_field(row.get("ingredients_raw", ""))
                steps = parse_list_field(row.get("steps", ""))
                tags = parse_list_field(row.get("tags", ""))

                # Parse servings
                try:
                    servings = int(row.get("servings", 4))
                except (ValueError, TypeError):
                    servings = 4

                # Prepare data
                data = (
                    str(row.get("id", "")),
                    row.get("name", ""),
                    row.get("description", ""),
                    json.dumps(ingredients),
                    json.dumps(ingredients_raw),
                    json.dumps(steps),
                    servings,
                    row.get("serving_size", ""),
                    json.dumps(tags),
                )

                batch.append(data)

                # Insert batch
                if len(batch) >= batch_size:
                    cursor.executemany(
                        """
                        INSERT OR REPLACE INTO recipes
                        (id, name, description, ingredients, ingredients_raw, steps, servings, serving_size, tags)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                        """,
                        batch,
                    )
                    conn.commit()
                    total_count += len(batch)
                    logger.info(f"Loaded {total_count} recipes...")
                    batch = []

            except Exception as e:
                error_count += 1
                logger.warning(f"Error processing row {total_count + len(batch)}: {e}")
                continue

        # Insert remaining batch
        if batch:
            cursor.executemany(
                """
                INSERT OR REPLACE INTO recipes
                (id, name, description, ingredients, ingredients_raw, steps, servings, serving_size, tags)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                batch,
            )
            conn.commit()
            total_count += len(batch)

    conn.close()

    logger.info(f"Loaded {total_count} recipes successfully")
    if error_count > 0:
        logger.warning(f"Encountered {error_count} errors")


def main():
    parser = argparse.ArgumentParser(description="Load Food.com recipes into SQLite")
    parser.add_argument(
        "--input",
        type=Path,
        default="food_com_recipes.csv",
        help="Input CSV file (default: food_com_recipes.csv)",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default="data/recipes.db",
        help="Output SQLite database (default: data/recipes.db)",
    )
    parser.add_argument(
        "--batch-size",
        type=int,
        default=1000,
        help="Batch size for inserts (default: 1000)",
    )

    args = parser.parse_args()

    # Create data directory
    args.output.parent.mkdir(parents=True, exist_ok=True)

    load_recipes(args.input, args.output, args.batch_size)
    logger.info("Done!")


if __name__ == "__main__":
    main()
