# Interactive Mode - Natural Language Support

The interactive mode now understands **natural language** commands!

## 🗣️ Talk Naturally

Instead of memorizing exact commands, just say what you want:

### Planning
```
🍽️  > help me plan my meals for the week
🍽️  > plan my meals
🍽️  > make a plan
🍽️  > create plan
```
All trigger meal planning!

### Shopping
```
🍽️  > make a shopping list
🍽️  > create shopping list
🍽️  > grocery list
```

Show existing list:
```
🍽️  > show my shopping list
🍽️  > show shopping list
🍽️  > display grocery list
```

### Searching
```
🍽️  > find chicken recipes
🍽️  > search for salmon
🍽️  > look for pasta dishes
```

### Viewing
```
🍽️  > show my meal plan
🍽️  > show plan
🍽️  > display my shopping list
```

### Exiting
```
🍽️  > quit
🍽️  > exit
🍽️  > bye
🍽️  > goodbye
```

## 💡 Examples

### Natural Conversation Style
```
🍽️  > help me plan my meals for the week

💡 I'll help you plan meals for the week!

Meal Plan for Week of 2025-10-20
==================================================
[... meal plan displayed ...]

✅ Meal plan created: mp_2025-10-20_xxx

🍽️  > now make a shopping list

✅ Shopping list created!
[... list displayed ...]

🍽️  > find quick chicken recipes

✅ Found 10 recipes:
1. Quick Chicken Stir-Fry (20 min)
[...]

🍽️  > show my plan

[... displays current meal plan ...]

🍽️  > bye

👋 Goodbye! Happy cooking!
```

## 🎯 Still Works: Short Commands

Traditional commands still work:
```
🍽️  > plan
🍽️  > shop
🍽️  > search chicken
🍽️  > show plan
🍽️  > quit
```

## 🌟 Best of Both Worlds

**Natural Language**: More conversational, easier to remember
```
"help me plan my meals" → Plans meals
"find chicken recipes" → Searches for chicken
```

**Short Commands**: Faster for power users
```
plan → Plans meals
search chicken → Searches for chicken
```

Use whichever feels more natural to you!

---

**Try it now:**
```bash
./run.sh interactive
```

Then just talk to it naturally! 💬
