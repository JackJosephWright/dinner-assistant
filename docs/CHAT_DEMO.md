# Chat Interface Demo

## Setup Complete! ✅

The chat interface is ready to use with verbose mode for debugging.

## How to Launch

### 1. Set API Key

```bash
export ANTHROPIC_API_KEY='sk-ant-...'
```

Or load from .env:
```bash
source .env
```

### 2. Run Chat

**Normal mode:**
```bash
./chat.sh
```

**Verbose mode (recommended for testing):**
```bash
./chat.sh --verbose
```

## What Gets Displayed

### Welcome Screen

```
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
```

### Example Interaction (Verbose Mode)

```
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
      → LLM selected: Beef Stir Fry, Beef Tacos, Gr...
   Result: ✓ Created 3-day meal plan!

Meals:
- 2025-10-28: Beef Stir Fry (15 ingredients)
- 2025-10-29: Beef Tacos (12 ingredients)
- 2025-10-30: Grilled Beef Kebabs (10 ingredients)

📊 37 total ingredients, allergens: eggs, gluten

🍽️  Assistant: I've created a 3-day meal plan with dairy-free beef recipes!
```

## Verbose Mode Features

When running with `--verbose`, you see:

1. **Tool Calls**: Which tools the LLM decides to use
2. **Tool Input**: Exact parameters passed to each tool
3. **Step-by-Step**: Internal execution flow:
   - SQL search results
   - Allergen filtering stats
   - LLM selection process
4. **Tool Results**: What each tool returns
5. **Final Response**: LLM's conversational response

## What to Test

### Test 1: Basic Planning
```
You: Plan 4 days of chicken meals
```

**Expected verbose output:**
- Tool: `plan_meals_smart`
- SQL search: ~100 candidates for "chicken"
- All 100 have structured ingredients
- LLM selects 4 varied recipes
- Creates meal plan with embedded recipes

### Test 2: Allergen Filtering
```
You: Plan a week with no dairy or gluten
```

**Expected verbose output:**
- SQL search: ~100 candidates
- Filtering: Shows how many recipes remain after allergen filtering
- If <7 recipes: Error message asking to relax constraints
- If >=7 recipes: LLM selects 7 varied meals

### Test 3: Time Constraints
```
You: Plan 5 quick dinners under 30 minutes
```

**Expected verbose output:**
- SQL search with max_time=30
- Fewer candidates (only quick recipes)
- LLM selection from quick recipes

### Test 4: Shopping List
```
You: Create a shopping list
```

**Expected verbose output:**
- Tool: `create_shopping_list`
- Uses current meal plan ID
- Returns: "Created shopping list with X items"

### Test 5: Multi-turn Conversation
```
You: Plan 3 days of pasta
Assistant: [creates plan]

You: Actually, swap Monday for something with chicken
Assistant: [uses swap_meal tool]

You: Now create a shopping list
Assistant: [uses create_shopping_list tool]
```

## Implementation Details

### Files Modified

**src/chatbot.py:**
- Added `verbose` parameter to `__init__`
- Added verbose output in `chat()` method for tool execution
- Added verbose output in `plan_meals_smart` execution
- Enhanced welcome message with usage examples
- Added argparse for `--verbose` flag

**chat.sh:**
- Sets PYTHONPATH correctly
- Checks for API key
- Passes through command-line arguments

**Documentation:**
- `docs/CHAT_INTERFACE_GUIDE.md` - Complete usage guide
- `docs/CHAT_DEMO.md` - This file

### Architecture

```
User Input
    ↓
MealPlanningChatbot.chat()
    ↓
Claude API (with tools)
    ↓
Tool Selection (LLM decides)
    ↓
execute_tool() [with verbose logging]
    ↓
plan_meals_smart:
  - SQL search [logged if verbose]
  - Allergen filter [logged if verbose]
  - LLM selection [logged if verbose]
  - Create MealPlan
    ↓
Tool Result → Claude API
    ↓
Final Response → User
```

### What Verbose Mode Shows

**Normal mode:**
```
You: Plan 3 days of beef

🍽️  Assistant: I've created a 3-day meal plan with beef recipes!
```

**Verbose mode:**
```
You: Plan 3 days of beef

🔧 [TOOL] plan_meals_smart
   Input: {"num_days": 3, "search_query": "beef"}
      → Planning 3 days starting 2025-10-28
      → SQL search found 100 candidates for 'beef'
      → All 100 have structured ingredients
      → Using LLM to select 3 varied recipes from 100 options...
      → LLM selected: Beef Stir Fry, Beef Tacos, Grilled Beef Kebabs
   Result: ✓ Created 3-day meal plan! ...

🍽️  Assistant: I've created a 3-day meal plan with beef recipes!
```

## Benefits for Testing

1. **Transparency**: See exactly what the LLM is doing
2. **Debugging**: Identify where failures occur (SQL, filtering, LLM)
3. **Validation**: Confirm allergen filtering is working correctly
4. **Performance**: See which steps are slow
5. **Learning**: Understand the SQL + LLM hybrid approach

## Next Steps

Once you've tested the chat interface:

1. **Verify tool selection**: Does LLM choose the right tools?
2. **Test edge cases**: No results, too few results, invalid inputs
3. **Multi-turn conversations**: Does context persist?
4. **Error handling**: What happens when tools fail?
5. **Performance**: Is LLM selection fast enough?

Ready to start testing! Just set your API key and run `./chat.sh --verbose`.
