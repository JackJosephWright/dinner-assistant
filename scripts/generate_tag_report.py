#!/usr/bin/env python3
"""
Generate tag coverage report from recipes database.

This script analyzes the tags field in recipes.db to understand
the actual tag vocabulary available for meal planning constraints.

Usage:
    python scripts/generate_tag_report.py
    python scripts/generate_tag_report.py --db data/recipes.db
"""

import sqlite3
import json
import argparse
from collections import Counter
from pathlib import Path


def generate_tag_report(db_path: str = "data/recipes.db"):
    """Generate tag coverage report from recipes database."""
    print(f"Reading tags from {db_path}...")

    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    # Get all tags
    cursor.execute("SELECT tags FROM recipes WHERE tags IS NOT NULL")
    all_tags = Counter()
    recipe_count = 0

    for (tags_json,) in cursor.fetchall():
        recipe_count += 1
        if tags_json:
            try:
                tags = json.loads(tags_json)
                all_tags.update(tags)
            except json.JSONDecodeError:
                continue

    conn.close()
    print(f"Analyzed {recipe_count:,} recipes, found {len(all_tags):,} unique tags")

    # Categorize tags using keyword heuristics
    cuisine_keywords = [
        "italian", "mexican", "chinese", "indian", "french", "greek",
        "japanese", "thai", "korean", "vietnamese", "spanish", "german",
        "irish", "american", "cajun", "african", "caribbean", "mediterranean",
        "asian", "european", "middle-eastern", "brazilian", "cuban", "polish"
    ]
    dietary_keywords = [
        "vegetarian", "vegan", "low-carb", "low-fat", "healthy", "gluten-free",
        "dairy-free", "kid", "quick", "easy", "weeknight"
    ]
    course_keywords = [
        "main-dish", "main", "entree", "dessert", "appetizer", "side",
        "breakfast", "lunch", "dinner", "snack", "beverage", "drink",
        "sauce", "condiment", "salad", "soup", "bread"
    ]

    def matches_keywords(tag: str, keywords: list) -> bool:
        tag_lower = tag.lower()
        return any(kw in tag_lower for kw in keywords)

    cuisine_candidates = {
        k: v for k, v in all_tags.items() if matches_keywords(k, cuisine_keywords)
    }
    dietary_candidates = {
        k: v for k, v in all_tags.items() if matches_keywords(k, dietary_keywords)
    }
    course_candidates = {
        k: v for k, v in all_tags.items() if matches_keywords(k, course_keywords)
    }

    # Build report
    report = {
        "recipe_count": recipe_count,
        "unique_tag_count": len(all_tags),
        "top_200_tags": dict(all_tags.most_common(200)),
        "cuisine_candidates": dict(sorted(cuisine_candidates.items(), key=lambda x: -x[1])),
        "dietary_candidates": dict(sorted(dietary_candidates.items(), key=lambda x: -x[1])),
        "course_candidates": dict(sorted(course_candidates.items(), key=lambda x: -x[1])),
    }

    # Ensure docs directory exists
    Path("docs").mkdir(exist_ok=True)

    # Write markdown report
    md_path = Path("docs/tag_report.md")
    with open(md_path, "w") as f:
        f.write("# Recipe Tag Report\n\n")
        f.write(f"**Total recipes analyzed:** {recipe_count:,}\n\n")
        f.write(f"**Unique tags found:** {len(all_tags):,}\n\n")

        f.write("## Top 50 Tags (by frequency)\n\n")
        for i, (tag, count) in enumerate(all_tags.most_common(50), 1):
            f.write(f"{i}. `{tag}`: {count:,}\n")

        f.write("\n## Cuisine-Related Tags\n\n")
        for tag, count in sorted(cuisine_candidates.items(), key=lambda x: -x[1])[:30]:
            f.write(f"- `{tag}`: {count:,}\n")

        f.write("\n## Dietary-Related Tags\n\n")
        for tag, count in sorted(dietary_candidates.items(), key=lambda x: -x[1])[:20]:
            f.write(f"- `{tag}`: {count:,}\n")

        f.write("\n## Course/Meal-Type Tags\n\n")
        for tag, count in sorted(course_candidates.items(), key=lambda x: -x[1])[:30]:
            f.write(f"- `{tag}`: {count:,}\n")

    print(f"Written: {md_path}")

    # Write JSON for programmatic use (optional, but helpful for debugging)
    json_path = Path("docs/tag_report.json")
    with open(json_path, "w") as f:
        json.dump(report, f, indent=2)
    print(f"Written: {json_path}")

    return report


def main():
    parser = argparse.ArgumentParser(description="Generate tag coverage report")
    parser.add_argument("--db", default="data/recipes.db", help="Path to recipes database")
    args = parser.parse_args()

    generate_tag_report(args.db)
    print("\nTag report generation complete.")


if __name__ == "__main__":
    main()
