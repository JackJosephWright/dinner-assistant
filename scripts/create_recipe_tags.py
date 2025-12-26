#!/usr/bin/env python3
"""
Phase 2: Create normalized recipe_tags table for fast tag queries.

This script creates a recipe_tags(recipe_id, tag) table with an index on tag,
enabling fast lookups that avoid LIKE '%tag%' full table scans.

Usage:
    python scripts/create_recipe_tags.py                    # Uses data/recipes.db
    python scripts/create_recipe_tags.py --db data/recipes_dev.db
"""

import argparse
import sqlite3
import time
import sys


def create_recipe_tags(db_path: str, verbose: bool = True, force: bool = False) -> dict:
    """
    Create normalized recipe_tags table from recipes.tags JSON.

    Returns:
        dict with stats: rows_inserted, time_taken, etc.
    """
    stats = {}

    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    # Check if table already exists
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='recipe_tags'")
    if cursor.fetchone():
        if verbose:
            print(f"Table recipe_tags already exists in {db_path}")
            cursor.execute("SELECT COUNT(*) FROM recipe_tags")
            count = cursor.fetchone()[0]
            print(f"  Current rows: {count:,}")

        # Ask to rebuild (unless force mode)
        if not force:
            response = input("Rebuild table? [y/N]: ").strip().lower()
            if response != 'y':
                print("Skipping rebuild.")
                conn.close()
                return {"skipped": True}

    if verbose:
        print(f"\nCreating recipe_tags table in {db_path}...")

    # Drop existing table if rebuilding
    cursor.execute("DROP TABLE IF EXISTS recipe_tags")

    # Create table
    if verbose:
        print("  Creating table schema...")
    cursor.execute("""
        CREATE TABLE recipe_tags (
            recipe_id TEXT NOT NULL,
            tag TEXT NOT NULL,
            PRIMARY KEY (recipe_id, tag)
        )
    """)

    # Populate from recipes.tags JSON
    if verbose:
        print("  Populating from recipes.tags JSON...")
    start = time.time()

    cursor.execute("""
        INSERT OR IGNORE INTO recipe_tags (recipe_id, tag)
        SELECT recipes.id, json_each.value
        FROM recipes, json_each(recipes.tags)
        WHERE json_valid(recipes.tags)
    """)

    rows_inserted = cursor.rowcount
    populate_time = time.time() - start
    stats["rows_inserted"] = rows_inserted
    stats["populate_time"] = populate_time

    if verbose:
        print(f"  Inserted {rows_inserted:,} rows in {populate_time:.1f}s")

    # Create index
    if verbose:
        print("  Creating index on tag column...")
    start = time.time()
    cursor.execute("CREATE INDEX idx_recipe_tags_tag ON recipe_tags(tag)")
    index_time = time.time() - start
    stats["index_time"] = index_time

    if verbose:
        print(f"  Index created in {index_time:.1f}s")

    # Run ANALYZE for query optimizer
    if verbose:
        print("  Running ANALYZE...")
    cursor.execute("ANALYZE recipe_tags")

    # Commit
    conn.commit()

    # Verify
    cursor.execute("SELECT COUNT(*) FROM recipe_tags")
    final_count = cursor.fetchone()[0]
    stats["final_count"] = final_count

    cursor.execute("SELECT COUNT(DISTINCT recipe_id) FROM recipe_tags")
    recipe_count = cursor.fetchone()[0]
    stats["recipe_count"] = recipe_count

    cursor.execute("SELECT COUNT(DISTINCT tag) FROM recipe_tags")
    unique_tags = cursor.fetchone()[0]
    stats["unique_tags"] = unique_tags

    # Get top tags
    cursor.execute("""
        SELECT tag, COUNT(*) as cnt
        FROM recipe_tags
        GROUP BY tag
        ORDER BY cnt DESC
        LIMIT 10
    """)
    top_tags = cursor.fetchall()
    stats["top_tags"] = top_tags

    conn.close()

    if verbose:
        print(f"\n✅ Done!")
        print(f"   Total rows: {final_count:,}")
        print(f"   Recipes covered: {recipe_count:,}")
        print(f"   Unique tags: {unique_tags:,}")
        print(f"\n   Top 10 tags:")
        for tag, cnt in top_tags:
            print(f"     {tag}: {cnt:,}")

    return stats


def benchmark_queries(db_path: str):
    """Compare query performance before/after recipe_tags."""
    import random

    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    print("\n" + "=" * 60)
    print("QUERY BENCHMARK: LIKE vs JOIN")
    print("=" * 60)

    test_cases = [
        (["main-dish", "italian"], "Italian main dishes"),
        (["main-dish", "vegetarian"], "Vegetarian main dishes"),
        (["main-dish"], "All main dishes"),
    ]

    for tags, description in test_cases:
        print(f"\n{description} ({tags}):")

        # Old method: LIKE
        like_conditions = " AND ".join([f"tags LIKE '%{t}%'" for t in tags])
        start = time.time()
        cursor.execute(f"SELECT rowid FROM recipes WHERE {like_conditions}")
        like_rowids = [r[0] for r in cursor.fetchall()]
        like_time = (time.time() - start) * 1000

        # New method: JOIN on recipe_tags
        if len(tags) == 1:
            join_sql = f"""
                SELECT rt.recipe_id FROM recipe_tags rt
                WHERE rt.tag = ?
            """
            params = tags
        else:
            # INTERSECT for multiple tags
            join_sql = " INTERSECT ".join([
                "SELECT recipe_id FROM recipe_tags WHERE tag = ?"
                for _ in tags
            ])
            params = tags

        start = time.time()
        cursor.execute(join_sql, params)
        join_ids = [r[0] for r in cursor.fetchall()]
        join_time = (time.time() - start) * 1000

        speedup = like_time / join_time if join_time > 0 else float('inf')

        print(f"  LIKE query:  {like_time:>8.1f}ms ({len(like_rowids):,} rows)")
        print(f"  JOIN query:  {join_time:>8.1f}ms ({len(join_ids):,} rows)")
        print(f"  Speedup:     {speedup:>8.1f}x")

    conn.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Create normalized recipe_tags table")
    parser.add_argument("--db", default="data/recipes.db", help="Path to recipes database")
    parser.add_argument("--benchmark", action="store_true", help="Run benchmark after creation")
    parser.add_argument("--quiet", action="store_true", help="Suppress verbose output")
    parser.add_argument("--force", action="store_true", help="Force rebuild without prompting")
    args = parser.parse_args()

    stats = create_recipe_tags(args.db, verbose=not args.quiet, force=args.force)

    if args.benchmark and not stats.get("skipped"):
        benchmark_queries(args.db)
