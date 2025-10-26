#!/usr/bin/env python3
"""
Database Migration Script: Create Enhanced Recipes Table

This script creates an optimized recipes_enhanced table with pre-computed,
indexed fields for fast structured queries. It processes all 492k+ recipes
from the original recipes table.

New features:
- Pre-computed cuisine, difficulty, estimated_time (no runtime derivation)
- Extracted primary_protein from ingredients
- Dietary flags (vegetarian, vegan, gluten-free, dairy-free)
- Indexed columns for fast filtering
- Searchable ingredient list for FTS

Run time: ~5-10 minutes for 492k recipes
"""

import sqlite3
import json
import logging
import re
from pathlib import Path
from typing import List, Optional, Set

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


class RecipeEnhancer:
    """Enhances recipes with pre-computed searchable fields."""

    # Protein keywords to search for in ingredients
    PROTEINS = {
        'chicken': ['chicken', 'poultry'],
        'beef': ['beef', 'steak', 'ground beef', 'sirloin', 'ribeye'],
        'pork': ['pork', 'ham', 'bacon', 'sausage'],
        'fish': ['fish', 'salmon', 'tuna', 'cod', 'tilapia', 'halibut'],
        'seafood': ['shrimp', 'crab', 'lobster', 'scallop', 'mussel', 'clam', 'oyster'],
        'tofu': ['tofu', 'tempeh', 'seitan'],
        'beans': ['beans', 'lentils', 'chickpeas', 'black beans', 'kidney beans'],
        'eggs': ['egg', 'eggs'],
        'turkey': ['turkey'],
        'lamb': ['lamb'],
    }

    # Dietary indicators
    DAIRY_KEYWORDS = ['milk', 'cheese', 'butter', 'cream', 'yogurt', 'sour cream', 'parmesan']
    GLUTEN_KEYWORDS = ['flour', 'wheat', 'bread', 'pasta', 'noodles']
    MEAT_KEYWORDS = ['chicken', 'beef', 'pork', 'fish', 'seafood', 'meat', 'sausage', 'bacon']

    def extract_cuisine(self, tags: List[str]) -> Optional[str]:
        """Extract cuisine from tags (same as Recipe model)."""
        cuisine_tags = [
            "italian", "mexican", "chinese", "thai", "indian",
            "japanese", "french", "greek", "american", "korean",
            "spanish", "vietnamese", "mediterranean", "middle-eastern"
        ]
        for tag in tags:
            if tag in cuisine_tags:
                return tag.title()
        return None

    def extract_time(self, tags: List[str]) -> Optional[int]:
        """Extract estimated time from tags (same as Recipe model)."""
        time_tags = {
            "15-minutes-or-less": 15,
            "30-minutes-or-less": 30,
            "60-minutes-or-less": 60,
            "4-hours-or-less": 240,
        }
        for tag in tags:
            if tag in time_tags:
                return time_tags[tag]
        return None

    def extract_difficulty(self, tags: List[str]) -> str:
        """Extract difficulty from tags (same as Recipe model)."""
        if "easy" in tags or "beginner-cook" in tags:
            return "easy"
        elif "difficult" in tags or "advanced" in tags:
            return "hard"
        return "medium"

    def extract_primary_protein(self, ingredients: List[str]) -> Optional[str]:
        """
        Extract primary protein from ingredient list.

        Returns the first protein found, prioritizing animal proteins.
        """
        ingredients_lower = ' '.join(ingredients).lower()

        # Check each protein category
        for protein, keywords in self.PROTEINS.items():
            for keyword in keywords:
                if keyword in ingredients_lower:
                    return protein

        return None

    def extract_dietary_flags(self, ingredients: List[str], tags: List[str]) -> List[str]:
        """
        Determine dietary flags based on ingredients and tags.

        Returns list of flags: vegetarian, vegan, gluten-free, dairy-free
        """
        flags = []
        ingredients_lower = ' '.join(ingredients).lower()
        tags_str = ' '.join(tags).lower()

        # Check for meat
        has_meat = any(keyword in ingredients_lower for keyword in self.MEAT_KEYWORDS)

        # Vegetarian: no meat
        if not has_meat or 'vegetarian' in tags_str:
            flags.append('vegetarian')

        # Vegan: no meat, dairy, eggs
        has_dairy = any(keyword in ingredients_lower for keyword in self.DAIRY_KEYWORDS)
        has_eggs = 'egg' in ingredients_lower
        if not has_meat and not has_dairy and not has_eggs:
            flags.append('vegan')

        # Gluten-free: check tags (ingredient checking is too complex)
        if 'gluten-free' in tags_str:
            flags.append('gluten-free')

        # Dairy-free
        if not has_dairy or 'dairy-free' in tags_str:
            flags.append('dairy-free')

        return flags


def migrate_recipes(db_path: str):
    """
    Main migration function.

    Creates recipes_enhanced table and populates it from recipes table.
    """
    logger.info(f"Starting migration for {db_path}")

    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    # Create enhanced table
    logger.info("Creating recipes_enhanced table...")
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS recipes_enhanced (
            id TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            description TEXT,
            ingredients TEXT,
            ingredients_raw TEXT,
            steps TEXT,
            servings INTEGER,
            serving_size TEXT,
            tags TEXT,

            -- Enhanced fields
            cuisine TEXT,
            difficulty TEXT,
            estimated_time INTEGER,
            primary_protein TEXT,
            dietary_flags TEXT,
            ingredient_list TEXT
        )
    """)

    # Create indexes
    logger.info("Creating indexes...")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_enhanced_cuisine ON recipes_enhanced(cuisine)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_enhanced_difficulty ON recipes_enhanced(difficulty)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_enhanced_time ON recipes_enhanced(estimated_time)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_enhanced_protein ON recipes_enhanced(primary_protein)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_enhanced_name ON recipes_enhanced(name)")

    conn.commit()

    # Count existing recipes
    cursor.execute("SELECT COUNT(*) FROM recipes")
    total_recipes = cursor.fetchone()[0]
    logger.info(f"Found {total_recipes:,} recipes to process")

    # Check if already migrated
    cursor.execute("SELECT COUNT(*) FROM recipes_enhanced")
    existing_count = cursor.fetchone()[0]
    if existing_count > 0:
        logger.warning(f"Found {existing_count:,} existing recipes in recipes_enhanced")
        response = input("Clear and re-migrate? (y/n): ")
        if response.lower() == 'y':
            logger.info("Clearing recipes_enhanced...")
            cursor.execute("DELETE FROM recipes_enhanced")
            conn.commit()
        else:
            logger.info("Migration cancelled")
            conn.close()
            return

    # Process recipes in batches
    enhancer = RecipeEnhancer()
    batch_size = 1000
    processed = 0
    offset = 0

    while True:
        cursor.execute(f"SELECT * FROM recipes LIMIT {batch_size} OFFSET {offset}")
        rows = cursor.fetchall()
        if not rows:
            break

        offset += batch_size

        batch_data = []
        for row in rows:
            try:
                recipe_id = row[0]
                name = row[1]
                description = row[2]
                ingredients_json = row[3]
                ingredients_raw_json = row[4]
                steps_json = row[5]
                servings = row[6]
                serving_size = row[7]
                tags_json = row[8]

                # Parse JSON
                ingredients = json.loads(ingredients_json) if ingredients_json else []
                tags = json.loads(tags_json) if tags_json else []

                # Extract enhanced fields
                cuisine = enhancer.extract_cuisine(tags)
                difficulty = enhancer.extract_difficulty(tags)
                estimated_time = enhancer.extract_time(tags)
                primary_protein = enhancer.extract_primary_protein(ingredients)
                dietary_flags = enhancer.extract_dietary_flags(ingredients, tags)

                # Create searchable ingredient list
                ingredient_list = ' '.join(ingredients).lower()

                batch_data.append((
                    recipe_id, name, description,
                    ingredients_json, ingredients_raw_json, steps_json,
                    servings, serving_size, tags_json,
                    cuisine, difficulty, estimated_time, primary_protein,
                    json.dumps(dietary_flags), ingredient_list
                ))

            except Exception as e:
                logger.error(f"Error processing recipe {row[0]}: {e}")
                continue

        # Insert batch
        cursor.executemany("""
            INSERT INTO recipes_enhanced
            (id, name, description, ingredients, ingredients_raw, steps,
             servings, serving_size, tags, cuisine, difficulty, estimated_time,
             primary_protein, dietary_flags, ingredient_list)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, batch_data)

        conn.commit()
        processed += len(batch_data)

        if processed % 10000 == 0:
            logger.info(f"Processed {processed:,} / {total_recipes:,} recipes ({processed/total_recipes*100:.1f}%)")

    logger.info(f"Migration complete! Processed {processed:,} recipes")

    # Show statistics
    cursor.execute("SELECT COUNT(*) FROM recipes_enhanced WHERE cuisine IS NOT NULL")
    with_cuisine = cursor.fetchone()[0]

    cursor.execute("SELECT COUNT(*) FROM recipes_enhanced WHERE estimated_time IS NOT NULL")
    with_time = cursor.fetchone()[0]

    cursor.execute("SELECT COUNT(*) FROM recipes_enhanced WHERE primary_protein IS NOT NULL")
    with_protein = cursor.fetchone()[0]

    cursor.execute("SELECT primary_protein, COUNT(*) FROM recipes_enhanced WHERE primary_protein IS NOT NULL GROUP BY primary_protein")
    protein_stats = cursor.fetchall()

    logger.info("\n=== Migration Statistics ===")
    logger.info(f"Total recipes: {processed:,}")
    logger.info(f"With cuisine: {with_cuisine:,} ({with_cuisine/processed*100:.1f}%)")
    logger.info(f"With time: {with_time:,} ({with_time/processed*100:.1f}%)")
    logger.info(f"With protein: {with_protein:,} ({with_protein/processed*100:.1f}%)")
    logger.info("\nProtein distribution:")
    for protein, count in sorted(protein_stats, key=lambda x: x[1], reverse=True):
        logger.info(f"  {protein}: {count:,}")

    conn.close()


if __name__ == "__main__":
    import sys

    # Default to data/recipes.db
    db_path = sys.argv[1] if len(sys.argv) > 1 else "data/recipes.db"

    if not Path(db_path).exists():
        logger.error(f"Database not found: {db_path}")
        sys.exit(1)

    migrate_recipes(db_path)
