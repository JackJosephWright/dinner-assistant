# Architecture Discussion - Object State Management

**Date:** 2025-10-28
**Status:** Planning Phase - No implementation yet

## Context

We discovered critical issues with how the chatbot handles objects vs. text, which led to a broader discussion about state management across the entire application.

## The Problem

### Issue 1: Chatbot Ignoring User Questions
**Scenario:**
```
User: "I would like 5 recipes, one is pasta, all must have chicken"
Chatbot: [Returns 5 recipes with IDs, names, times]

User: "Can you see if there is shellfish in any of these?"
Chatbot: [Calls get_cooking_guide for EACH recipe, dumps full cooking guides, never answers the question]
```

**Root Cause:**
1. System prompt tells LLM to be "SHORT" but doesn't emphasize ANALYZING tool results
2. `search_recipes` only returns text (name, ID, time) - no allergen info
3. Chatbot doesn't store Recipe objects in memory between calls
4. LLM re-fetches data instead of using what it already has

### Issue 2: Inefficient Re-fetching
- User asks about recipes already returned from search
- Chatbot calls `get_cooking_guide` for each one (5 API calls!)
- Should have the Recipe objects in memory from the search

### Issue 3: Broader State Management Questions
This revealed a fundamental architecture question:
- **How should the application manage MealPlan and Recipe objects across different interfaces?**
- Chat, Web App tabs (Plan, Shop, Cook), Database persistence, User history

## Two Architectural Paths

### Path 1: Stateless Tool-Based (Current)
- Tools return **text strings**
- No objects stored in memory
- Each request is independent

**Pros:**
- Simple, stateless
- Fast (you noticed the speed!)
- Easy to reason about

**Cons:**
- Can't do follow-up questions efficiently
- LLM sometimes ignores results
- No rich object manipulation

### Path 2: Object-Oriented with Memory
- Tools return **objects** (Recipe, MealPlan) stored in memory
- LLM can query these objects for follow-ups
- Rich methods available (`.get_all_allergens()`, etc.)

**Pros:**
- Efficient follow-ups
- Rich object methods
- Better for complex workflows
- Matches web app architecture

**Cons:**
- More complex state management
- Memory overhead
- Need to serialize objects for LLM

## Key User Requirements (Identified in Discussion)

1. **Multi-tab coordination**: Plan → Shop → Cook tabs need to share state
2. **Persistence**: Save finalized meal plans to database for history
3. **User history**: Track what users have had to suggest better recipes
4. **Performance**: Chatbot is "really snappy" now - must maintain speed
5. **Follow-up questions**: "Can you see if there is shellfish in any of these?"

## Critical Insight from User

> "I think how we manage the object is critical. because we have other tabs (shop and cook) which need this. also we will be saving these finalized meal plans into memory so we get user history, allows us to suggest better recipes in the future. allows users to go back and see what theyve had etc..."

**This means:** Object state management isn't just a chatbot issue - it's a **system-wide architecture decision**.

## Questions to Answer (Not Yet Resolved)

### 1. Web App State Management
- How does Flask app currently store/pass MealPlan/Recipe objects between tabs?
- Session storage, in-memory cache, or DB fetch each time?
- Look at `/plan`, `/shop`, `/cook` routes

### 2. Chatbot State Management
- Does chatbot store MealPlan object or just ID after `plan_meals_smart`?
- Should it keep Recipe objects from searches in memory?

### 3. Database Persistence
- When are MealPlan objects saved to DB?
- How are they loaded back (as objects or raw data)?
- Check `save_meal_plan()`, `get_meal_plan()` in database.py

### 4. Object Flow Lifecycle
Need to trace:
```
Create MealPlan → Use in Chat/Web → Save to DB → Load for history
```
- Where do Recipe objects get embedded into PlannedMeal objects?
- When do we use IDs vs full objects?

## Recommended Next Steps

### Investigation Phase (Next Session)
1. **Analyze current web app state management** - How does Flask handle objects?
2. **Trace object lifecycle** - Creation → Usage → Persistence → Loading
3. **Identify patterns and gaps** - What's consistent? What's broken?

### Design Phase
4. **Design unified state management strategy** across:
   - Chatbot (CLI)
   - Web app (Flask)
   - Database persistence
   - Cross-tab communication

### Implementation Phase
5. **Implement state management** with clear patterns
6. **Fix chatbot issues**:
   - System prompt improvements
   - Object memory for follow-ups
   - Allergen info in search results

## Files Modified So Far (Before This Discussion)

### Committed Changes
- `chat.sh` - Simplified to remove manual API key check
- `src/chatbot.py` - Added `load_dotenv()` to auto-load .env file

### Uncommitted Changes (In Progress)
- `src/chatbot.py` - Added object memory fields (`last_search_results`, `last_meal_plan`)
- `src/chatbot.py` - Updated system prompt with analysis instructions
- `src/chatbot.py` - Added allergen info to `search_recipes` output

**Decision:** Rolled back uncommitted changes - need to design architecture first

## Architecture Considerations

### Consistency is Key
Whatever we choose must be consistent across:
- Chatbot tool execution
- Web app API endpoints
- Database persistence layer
- Object serialization/deserialization

### Performance Requirements
- Maintain current chatbot speed (user emphasized this)
- Minimize redundant DB queries
- Efficient cross-tab state sharing

### Future Features Dependent on This
- User meal history tracking
- Recipe recommendation improvement
- "What did I have last week?" queries
- Shopping list from previous plans

## Current Status

**Phase:** Planning - No implementation started
**Blocked on:** Understanding current state management patterns
**Next action:** Investigate web app, chatbot, and database object handling

## Related Documentation

- `docs/MEAL_PLAN_WORKFLOW_REPORT.md` - MealPlan object design (Phase 2 complete)
- `docs/design/step5_meal_plan_design.md` - MealPlan with rich methods
- `src/data/models.py` - Recipe, PlannedMeal, MealPlan dataclasses
- `src/web/app.py` - Flask web interface
- `src/chatbot.py` - CLI chat interface

## Open Questions for Next Session

1. How does the web app currently share state between Plan/Shop/Cook tabs?
2. Does the database store full MealPlan objects or just IDs with separate meal records?
3. Should we use a shared StateManager class for both web and chatbot?
4. What's the right balance between object memory and stateless tools?
5. How do we serialize MealPlan objects for LLM context efficiently?
