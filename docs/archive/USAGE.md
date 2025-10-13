# Quick Usage Guide

## 🚀 Getting Started (5 seconds)

### Interactive Mode (Recommended!)

```bash
./run.sh interactive
```

Then type commands like:
- `plan` - Generate meal plan
- `shop` - Create shopping list
- `search chicken` - Find recipes
- `help` - See all commands

### Quick One-Shot

```bash
# Run the complete workflow
./run.sh workflow
```

That's it! You'll get:
- ✅ 7-day meal plan
- ✅ Shopping list (organized by store section)
- ✅ Cooking guide for first meal

---

## 📝 All Commands

### Interactive Mode (Best Experience)

```bash
# Start interactive mode
./run.sh interactive

# Then use commands:
🍽️  > plan                    # Generate meal plan
🍽️  > shop                    # Create shopping list
🍽️  > cook first              # Cooking guide for first meal
🍽️  > search chicken          # Find chicken recipes
🍽️  > search quick            # Recipes under 30 min
🍽️  > history                 # Your recent meals
🍽️  > show plan               # Show current plan
🍽️  > show list               # Show shopping list
🍽️  > help                    # All commands
🍽️  > quit                    # Exit
```

### One-Shot Commands

```bash
# Show help
./run.sh

# Complete workflow
./run.sh workflow

# Just plan meals
./run.sh plan

# Create shopping list (use ID from plan command)
./run.sh shop mp_2025-10-20_20251013012021

# Get cooking guide (use recipe ID)
./run.sh cook 21702

# Run all tests
./run.sh test

# Explore recipes
./run.sh explore
```

### Using Python Directly

```bash
# Complete workflow
python3 src/main.py workflow

# Individual commands
python3 src/main.py plan
python3 src/main.py shop --meal-plan-id <ID>
python3 src/main.py cook --recipe-id <ID>

# Plan for specific week (must be a Monday)
python3 src/main.py plan --week 2025-10-27
```

---

## 🎯 Common Workflows

### Weekly Meal Planning

```bash
# 1. Generate meal plan
./run.sh plan

# You'll see output like:
# ✓ Meal plan saved: mp_2025-10-20_20251013012021

# 2. Create shopping list using that ID
./run.sh shop mp_2025-10-20_20251013012021

# 3. Get cooking guide for any meal
#    (recipe IDs are in the meal plan output)
./run.sh cook 21702
```

### Quick Demo

```bash
# See everything at once
./run.sh workflow

# This runs: plan → shop → cook automatically
```

### Explore Recipes

```bash
# Interactive recipe browser
./run.sh explore

# Shows:
# - Your recent meal history
# - Quick recipes (under 30 min)
# - Recipes by ingredient
# - Easy beginner recipes
# - Vegetarian options
```

### Run Tests

```bash
# Run all tests
./run.sh test

# Or individual test suites
python3 tests/test_vertical_slice.py    # Database tests
python3 tests/test_planning.py          # Planning agent
python3 tests/test_integration.py       # Full workflow
```

---

## 💡 Tips

### Finding Recipe IDs

Recipe IDs are shown in meal plans:
```
Monday, 2025-10-20: Caramelized Onion Chicken
  (30 min, easy, 4 servings)
```

Use the database to search:
```python
from src.data.database import DatabaseInterface
db = DatabaseInterface(db_dir="data")
recipes = db.search_recipes(query="chicken", limit=5)
for r in recipes:
    print(f"{r.id}: {r.name}")
```

### Planning for Different Weeks

Always use a Monday date:
```bash
python3 src/main.py plan --week 2025-10-27  # Next week
python3 src/main.py plan --week 2025-11-03  # Week after
```

### Checking What's Saved

```bash
# View databases
ls -lh data/

# You'll see:
# recipes.db      - 492K recipes (1.1 GB)
# user_data.db    - Your plans and history (grows over time)
```

---

## 🔧 Troubleshooting

### "Command 'python' not found"

Use `python3` instead:
```bash
python3 src/main.py workflow
# Or use the helper script:
./run.sh workflow
```

### "No module named 'data'"

Make sure you're in the project directory:
```bash
cd ~/dinner-assistant
./run.sh workflow
```

### "Database not found"

Databases should be in `data/`:
```bash
ls -lh data/
# Should show recipes.db and user_data.db
```

If missing, they're already loaded! Check the size.

### Tests Failing

All tests should pass. If not:
```bash
# Make sure you're in project root
cd ~/dinner-assistant

# Run tests individually to see which fails
python3 tests/test_vertical_slice.py
python3 tests/test_planning.py
python3 tests/test_integration.py
```

---

## 📊 Understanding Output

### Meal Plan Format

```
Meal Plan for Week of 2025-10-20
==================================================

Monday, 2025-10-20: Caramelized Onion Chicken
  (30 min, easy, 4 servings)

Variety Summary:
  Cuisines: American (1), Mexican (1), Italian (1)
  Difficulty: easy (6), medium (1)

✓ Meal plan saved: mp_2025-10-20_20251013012021
```

The ID at the end (`mp_...`) is what you use for shopping.

### Shopping List Format

```
Shopping List for Week of 2025-10-20
============================================================

Total Items: 78

PRODUCE
------------------------------
  ☐ Onion - 1 medium onion, sliced
      For: Caramelized Onion Chicken
```

Organized by store section. Check off items as you shop!

### Cooking Guide Format

```
🍳 Caramelized Onion Chicken
============================================================
⏱️  Time: 30 minutes
🍽️  Servings: 4

💡 Tips:
   🌿 Fresh ingredients recommended

📋 Ingredients:
   1. 2 boneless chicken breasts...

👨‍🍳 Instructions:
   Step 1: Sprinkle the chicken...
```

---

## 🎓 Learn More

- `README.md` - Project overview
- `FINAL_STATUS.md` - Complete feature list
- `HANDOFF.md` - Original specification
- Code is documented with docstrings

---

**Need help?** Check `QUICKSTART.md` for more details.

**Want to understand the code?** Start with `src/main.py` - it's the entry point.
