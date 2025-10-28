#!/usr/bin/env python3
"""Quick script to enrich exactly 5,000 recipes and write to database."""

import sqlite3
import json
from enrich_recipe_ingredients import SimpleIngredientParser

db_path = "data/recipes.db"
parser = SimpleIngredientParser()

conn = sqlite3.connect(db_path)
conn.row_factory = sqlite3.Row
cursor = conn.cursor()

# Get first 5,000 recipes
cursor.execute("""
    SELECT id, name, ingredients_raw
    FROM recipes
    WHERE ingredients_raw IS NOT NULL
    LIMIT 5000
""")
recipes = cursor.fetchall()

print(f"Enriching {len(recipes)} recipes...")

processed = 0
for recipe in recipes:
    recipe_id = recipe["id"]
    ingredients_raw = json.loads(recipe["ingredients_raw"])

    structured = []
    for raw_ing in ingredients_raw:
        parsed = parser.parse(raw_ing)
        structured.append(parsed.to_dict())

    # Update database
    cursor.execute("""
        UPDATE recipes
        SET ingredients_structured = ?
        WHERE id = ?
    """, (json.dumps(structured), recipe_id))

    processed += 1
    if processed % 500 == 0:
        print(f"  Processed {processed}/{len(recipes)}...")
        conn.commit()

conn.commit()
conn.close()

print(f"✅ Enriched {processed} recipes!")
