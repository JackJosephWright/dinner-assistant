#!/usr/bin/env python3
"""
Create development database with enriched recipes only.

This script:
1. Copies the full recipes.db
2. Removes all non-enriched recipes
3. Creates a clean, fast development database

Usage:
    python3 scripts/create_dev_database.py
"""

import sqlite3
import shutil
import os
from pathlib import Path


def create_dev_database():
    """Create development database with enriched recipes only."""

    source_db = 'data/recipes.db'
    dev_db = 'data/recipes_dev.db'

    print("=" * 60)
    print("CREATING DEVELOPMENT DATABASE")
    print("=" * 60)

    # Check source exists
    if not os.path.exists(source_db):
        raise FileNotFoundError(f"Source database not found: {source_db}")

    # Check source has enriched recipes
    conn = sqlite3.connect(source_db)
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) FROM recipes WHERE ingredients_structured IS NOT NULL")
    enriched_count = cursor.fetchone()[0]
    conn.close()

    if enriched_count == 0:
        raise ValueError("Source database has no enriched recipes!")

    print(f"\nSource database: {source_db}")
    print(f"Enriched recipes found: {enriched_count:,}")

    # Remove existing dev database if it exists
    if os.path.exists(dev_db):
        print(f"\n⚠️  Removing existing dev database: {dev_db}")
        os.remove(dev_db)

    # Copy database
    print(f"\n📋 Copying database structure...")
    shutil.copy(source_db, dev_db)

    # Get original file size
    original_size = os.path.getsize(source_db) / (1024 * 1024)  # MB
    print(f"   Original size: {original_size:.1f} MB")

    # Clean up - keep only enriched recipes
    print(f"\n🗑️  Removing non-enriched recipes...")
    conn = sqlite3.connect(dev_db)
    cursor = conn.cursor()

    # Get counts before deletion
    cursor.execute("SELECT COUNT(*) FROM recipes")
    total_before = cursor.fetchone()[0]

    cursor.execute("SELECT COUNT(*) FROM recipes WHERE ingredients_structured IS NULL")
    to_delete = cursor.fetchone()[0]

    print(f"   Total recipes: {total_before:,}")
    print(f"   Will delete: {to_delete:,}")
    print(f"   Will keep: {enriched_count:,}")

    # Delete non-enriched recipes
    cursor.execute("""
        DELETE FROM recipes
        WHERE ingredients_structured IS NULL
    """)

    deleted = cursor.rowcount
    print(f"   ✓ Deleted: {deleted:,} recipes")

    # Commit changes
    conn.commit()

    # Verify
    cursor.execute("SELECT COUNT(*) FROM recipes")
    remaining = cursor.fetchone()[0]

    cursor.execute("SELECT COUNT(*) FROM recipes WHERE ingredients_structured IS NOT NULL")
    enriched_remaining = cursor.fetchone()[0]

    print(f"\n✅ Verification:")
    print(f"   Remaining recipes: {remaining:,}")
    print(f"   All enriched: {enriched_remaining:,}")
    assert remaining == enriched_remaining, "Some non-enriched recipes remain!"

    # Vacuum to reclaim space
    print(f"\n🗜️  Vacuuming database to reclaim space...")
    conn.execute("VACUUM")
    conn.close()

    # Get final file size
    final_size = os.path.getsize(dev_db) / (1024 * 1024)  # MB
    saved = original_size - final_size

    print(f"   Final size: {final_size:.1f} MB")
    print(f"   Space saved: {saved:.1f} MB ({saved/original_size*100:.1f}%)")

    # Summary
    print("\n" + "=" * 60)
    print("✅ DEVELOPMENT DATABASE CREATED!")
    print("=" * 60)
    print(f"\nLocation: {dev_db}")
    print(f"Recipes: {enriched_remaining:,} (all enriched)")
    print(f"Size: {final_size:.1f} MB (was {original_size:.1f} MB)")
    print(f"\nUsage:")
    print(f"  db = DatabaseInterface('{dev_db}')")
    print("=" * 60)


def verify_dev_database():
    """Verify development database integrity."""

    dev_db = 'data/recipes_dev.db'

    if not os.path.exists(dev_db):
        print(f"❌ Development database not found: {dev_db}")
        return False

    print("\n🔍 Verifying development database...")

    conn = sqlite3.connect(dev_db)
    cursor = conn.cursor()

    # Check counts
    cursor.execute("SELECT COUNT(*) FROM recipes")
    total = cursor.fetchone()[0]

    cursor.execute("SELECT COUNT(*) FROM recipes WHERE ingredients_structured IS NOT NULL")
    enriched = cursor.fetchone()[0]

    cursor.execute("SELECT COUNT(*) FROM recipes WHERE ingredients_structured IS NULL")
    non_enriched = cursor.fetchone()[0]

    # Sample a few recipes
    cursor.execute("""
        SELECT id, name,
               json_array_length(ingredients_structured) as ing_count
        FROM recipes
        LIMIT 3
    """)
    samples = cursor.fetchall()

    conn.close()

    print(f"   Total recipes: {total:,}")
    print(f"   Enriched: {enriched:,}")
    print(f"   Non-enriched: {non_enriched:,}")

    if non_enriched > 0:
        print(f"   ⚠️ WARNING: {non_enriched} non-enriched recipes found!")
        return False

    print(f"\n   Sample recipes:")
    for recipe_id, name, ing_count in samples:
        print(f"   - {name[:50]}: {ing_count} ingredients")

    print(f"\n   ✅ All recipes are enriched!")
    return True


if __name__ == "__main__":
    try:
        create_dev_database()
        verify_dev_database()

        print("\n✨ Ready for development!")

    except Exception as e:
        print(f"\n❌ ERROR: {e}")
        import traceback
        traceback.print_exc()
        exit(1)
