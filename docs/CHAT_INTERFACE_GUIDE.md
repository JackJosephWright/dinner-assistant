# Chat Interface Usage Guide

## Quick Start

### 1. Set your API key

```bash
export ANTHROPIC_API_KEY='your-api-key-here'
```

Or load from `.env` file:
```bash
source .env
```

### 2. Launch the chat

**Normal mode:**
```bash
./chat.sh
```

**Verbose mode** (shows tool execution details):
```bash
./chat.sh --verbose
```

Or directly:
```bash
python3 src/chatbot.py --verbose
```

## What You Can Do

### Plan Meals

**Simple planning:**
```
You: Plan 4 days of chicken meals
```

**With allergen filtering:**
```
You: Plan a week of dinners, no dairy or gluten
```

**With time constraints:**
```
You: Plan 5 quick meals under 30 minutes
```

### Search Recipes

```
You: Show me pasta recipes
You: Find quick chicken recipes
```

### Create Shopping Lists

```
You: Create a shopping list for my plan
```

### Swap Meals

```
You: Swap Monday's meal for something with beef
```

## Verbose Mode Output

When running with `--verbose`, you'll see:

```
🔧 [TOOL] plan_meals_smart
   Input: {
     "num_days": 4,
     "search_query": "chicken",
     "exclude_allergens": ["dairy"]
   }
      → Planning 4 days starting 2025-10-28
      → SQL search found 100 candidates for 'chicken'
      → Filtered to 53 recipes without dairy
      → Using LLM to select 4 varied recipes from 53 options...
      → LLM selected: Grilled Chicken Salad, Chicken Stir Fry, Lemon Herb Chicken, Chicken Tacos
   Result: ✓ Created 4-day meal plan!
   ...
```

This shows:
- Which tools the LLM is calling
- Tool input parameters
- Step-by-step execution details
- Tool results

## Example Session

```
$ ./chat.sh --verbose

======================================================================
🍽️  MEAL PLANNING ASSISTANT - AI Chatbot
======================================================================

Powered by Claude Sonnet 4.5 with intelligent tools
Database: 5,000 enriched recipes (100% structured ingredients)
Mode: VERBOSE (showing tool execution details)

✨ What I can do:
  • Plan meals with smart recipe selection
  • Filter by allergens (dairy, gluten, nuts, etc.)
  • Find recipes by keywords or cooking time
  • Create shopping lists organized by category
  • Swap meals in your plan

💡 Try asking:
  "Plan 4 days of chicken meals"
  "Plan a week, no dairy or gluten"
  "Show me quick pasta recipes under 30 minutes"

Type 'quit' to exit.

You: Plan 3 days of beef meals, no dairy

🔧 [TOOL] plan_meals_smart
   Input: {
     "num_days": 3,
     "search_query": "beef",
     "exclude_allergens": ["dairy"]
   }
      → Planning 3 days starting 2025-10-28
      → SQL search found 100 candidates for 'beef'
      → Filtered to 53 recipes without dairy
      → Using LLM to select 3 varied recipes from 53 options...
      → LLM selected: Beef Stir Fry, Beef Tacos, Grilled Beef Kebabs
   Result: ✓ Created 3-day meal plan!

Meals:
- 2025-10-28: Beef Stir Fry (15 ingredients)
- 2025-10-29: Beef Tacos (12 ingredients)
- 2025-10-30: Grilled Beef Kebabs (10 ingredients)

📊 37 total ingredients, allergens: eggs, gluten

🍽️  Assistant: I've created a 3-day meal plan with dairy-free beef recipes!
You'll need 37 ingredients total. Note that the meals contain eggs and gluten
- let me know if you need to avoid those as well.

You: Create a shopping list

🔧 [TOOL] create_shopping_list
   Input: {
     "meal_plan_id": "mp_2025-10-28_20251028145623"
   }
   Result: Created shopping list with 37 items, organized by store section.

🍽️  Assistant: Done! I've created your shopping list with 37 items organized
by store section (produce, meat, dairy, pantry, etc.).

You: quit

🍽️  Assistant: Goodbye! Happy cooking!
```

## Tips

1. **Be specific**: "Plan 5 quick dinners" works better than "plan meals"
2. **Chain requests**: Plan meals, then ask for shopping list
3. **Iterate**: Ask to swap specific meals if you don't like them
4. **Use allergens**: "no dairy", "no gluten", "no nuts" for exact filtering

## Available Tools (Behind the Scenes)

The chatbot has access to these tools:
- `plan_meals_smart` - Intelligent meal planning with SQL + LLM
- `search_recipes` - Find recipes by keywords/tags/time
- `create_shopping_list` - Generate categorized shopping lists
- `swap_meal` - Replace a meal with alternatives
- `get_cooking_guide` - Get detailed recipe instructions
- `show_current_plan` - Display current meal plan
- `get_meal_history` - View past meals

The LLM decides which tools to use based on your request!

## Troubleshooting

**"API key not set"**
- Make sure you've set `ANTHROPIC_API_KEY` in your environment
- Try: `source .env` if you have a `.env` file

**"No recipes found"**
- Try broader search terms
- Reduce constraints (fewer allergens, longer time limits)
- The dev database has 5,000 recipes (not all categories)

**Tool execution errors**
- Run with `--verbose` to see what's happening
- Check logs for specific error messages
- Ensure database is accessible in `data/` directory
