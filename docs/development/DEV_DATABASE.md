# Development Database Setup

**Created:** 2025-10-28
**Purpose:** Isolated development environment with enriched recipes only

---

## Overview

We maintain two separate databases:

| Database | Purpose | Recipes | Size | Enriched |
|----------|---------|---------|------|----------|
| **recipes.db** | Production | 492,630 | ~2.2 GB | 5,000 (1%) |
| **recipes_dev.db** | Development | 5,000 | ~1.1 GB | 5,000 (100%) |

---

## Why Separate Databases?

### Benefits ✅

1. **Stable Development Data**
   - Enriched recipes won't change as we improve the parser
   - Can develop features without worrying about data quality

2. **Fast Queries**
   - 5K vs 492K records = 98x faster queries
   - Faster test runs

3. **Safe Experimentation**
   - Can't accidentally break production data
   - Easy to reset/recreate

4. **Clear Separation**
   - Development vs production data isolated
   - No confusion about which recipes are enriched

---

## Creating the Development Database

### Initial Creation

```bash
python3 scripts/create_dev_database.py
```

This script:
1. Copies `data/recipes.db` → `data/recipes_dev.db`
2. Removes all non-enriched recipes (487,630 recipes)
3. Vacuums the database to reclaim space
4. Verifies all remaining recipes are enriched

### Re-creating from Scratch

If you need to rebuild the dev database:

```bash
# 1. Delete existing dev database
rm data/recipes_dev.db

# 2. Re-create from production
python3 scripts/create_dev_database.py
```

---

## Using the Development Database

### In Code

```python
from src.data.database import DatabaseInterface

# Development (use this during feature development)
db = DatabaseInterface('data/recipes_dev.db')

# Production (use this for testing against full dataset)
db = DatabaseInterface('data/recipes.db')
```

### In Tests

```python
# test_enhanced_recipe.py uses dev database
conn = sqlite3.connect('data/recipes_dev.db')
```

### Environment Variable (Optional)

You can set an environment variable to control which database to use:

```bash
# .env
RECIPE_DB=data/recipes_dev.db  # Development
# RECIPE_DB=data/recipes.db     # Production
```

Then in code:
```python
import os
db_path = os.getenv('RECIPE_DB', 'data/recipes_dev.db')
db = DatabaseInterface(db_path)
```

---

## Database Schema

Both databases have identical schemas:

```sql
CREATE TABLE recipes (
    id TEXT PRIMARY KEY,
    name TEXT,
    description TEXT,
    ingredients TEXT,                -- Clean names (for search)
    ingredients_raw TEXT,            -- Raw with quantities
    ingredients_structured TEXT,     -- Parsed JSON (enriched only)
    steps TEXT,
    servings INTEGER,
    serving_size TEXT,
    tags TEXT
);
```

**Key difference:** `recipes_dev.db` has `ingredients_structured` populated for **ALL** recipes.

---

## Enrichment Status

### Production Database (recipes.db)

- **Total recipes:** 492,630
- **Enriched:** 5,000 (1%)
- **Non-enriched:** 487,630 (99%)
- **Status:** Most recipes are NOT enriched yet

### Development Database (recipes_dev.db)

- **Total recipes:** 5,000
- **Enriched:** 5,000 (100%)
- **Non-enriched:** 0 (0%)
- **Status:** All recipes ready for development

---

## Enrichment Quality (5,000 recipes)

Based on enrichment test results:

```
Total recipes:       5,000
✅ High quality:     4,900 (98.0%)
⚠️  Partial:          100 (2.0%)
❌ Low quality:      0 (0.0%)
📈 Avg confidence:   0.958
```

**Excellent quality!** Ready for development.

---

## Common Workflows

### Scenario 1: Developing New Feature

```python
# Always use dev database for feature development
from src.data.database import DatabaseInterface

db = DatabaseInterface('data/recipes_dev.db')
recipe = db.get_recipe('71247')  # Cherry Streusel Cobbler

# All recipes in dev DB are enriched
assert recipe.has_structured_ingredients()

ingredients = recipe.get_ingredients()  # Works!
allergens = recipe.get_all_allergens()  # Works!
scaled = recipe.scale_ingredients(8)    # Works!
```

### Scenario 2: Testing Parser Improvements

```python
# 1. Modify parser in scripts/enrich_recipe_ingredients.py
# 2. Re-enrich production database (first 5K)
python3 scripts/enrich_5k_recipes.py

# 3. Re-create dev database with new enrichment
rm data/recipes_dev.db
python3 scripts/create_dev_database.py

# 4. Continue development with improved data
```

### Scenario 3: Testing Against Full Dataset

```python
# Use production database to test with 492K recipes
db = DatabaseInterface('data/recipes.db')

# Most recipes won't be enriched
recipes = db.search_recipes("pasta")

for recipe in recipes:
    if recipe.has_structured_ingredients():
        # Can use enhanced features
        allergens = recipe.get_all_allergens()
    else:
        # Fall back to basic features
        print(f"Recipe {recipe.name} not enriched")
```

---

## Migration Path to Production

### Phase 1: Development (Current)
- Use `recipes_dev.db` (5,000 enriched recipes)
- Develop all features
- Test thoroughly

### Phase 2: Expanded Testing
- Enrich 25,000 recipes in production DB
- Test at scale
- Validate performance

### Phase 3: Full Enrichment
- Enrich all 492,630 recipes
- Deploy to production
- Switch to `recipes.db` everywhere

---

## File Sizes

```
data/
├── recipes.db          2,248 MB  (492,630 recipes, 5K enriched)
├── recipes_dev.db      1,128 MB  (5,000 recipes, all enriched)
└── user_data.db           <1 MB  (user profiles, meal plans)
```

**Note:** `recipes_dev.db` is ~50% smaller despite having enriched data, because it only has 5K recipes instead of 492K.

---

## Git Ignore

Both databases are ignored by git:

```gitignore
# .gitignore
data/*.db
data/*.db-journal
data/*.db-wal
data/*.db-shm
```

**Never commit databases to git!** They are too large and contain user data.

---

## Backup Strategy

### Development Database
- Can be recreated anytime from production
- No need to back up

### Production Database
- Contains original 492K recipes
- Should be backed up regularly
- Critical data

```bash
# Backup production database
cp data/recipes.db backups/recipes_$(date +%Y%m%d).db
```

---

## Troubleshooting

### "Recipe not found" errors

**Problem:** Trying to load a recipe by ID that doesn't exist in dev database.

**Solution:** Check if recipe ID is in dev database:
```python
import sqlite3
conn = sqlite3.connect('data/recipes_dev.db')
cursor = conn.cursor()
cursor.execute("SELECT id, name FROM recipes WHERE id = ?", ('71247',))
print(cursor.fetchone())
```

Dev database only has IDs from the first 5,000 recipes (IDs: 71247-505744).

### "Recipe has not been enriched" errors

**Problem:** Using dev database but somehow got a non-enriched recipe.

**Solution:** Re-create dev database:
```bash
rm data/recipes_dev.db
python3 scripts/create_dev_database.py
```

### Database locked errors

**Problem:** Multiple processes trying to write to database.

**Solution:** Close all database connections:
```python
conn.close()
```

Or restart Python interpreter.

---

## Related Documentation

- **Enrichment Process:** `docs/design/step2d_subset_enrichment.md`
- **Enhanced Recipe Design:** `docs/design/step2e_enhanced_recipe_design.md`
- **Checkpoint Document:** `docs/development/CHECKPOINT_RECIPE_ENRICHMENT.md`
- **Implementation Status:** `docs/development/IMPLEMENTATION_STATUS.md`

---

**Last Updated:** 2025-10-28
**Next Review:** After Phase 2 (expanded testing)
