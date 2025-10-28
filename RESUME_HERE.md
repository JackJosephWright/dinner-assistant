# Resume Session - 2025-10-28

## Where We Left Off

We were in a **critical architecture discussion** about how to manage MealPlan and Recipe objects across the application.

## Quick Context

### The Trigger
Testing the chatbot revealed an issue:
```
User: "I would like 5 recipes, one is pasta, all must have chicken"
Chatbot: ✅ Returns 5 recipes

User: "Can you see if there is shellfish in any of these?"
Chatbot: ❌ Re-fetches all recipes, dumps cooking guides, never answers the question
```

### The Real Issue Discovered
This isn't just a chatbot bug - it's a **system-wide architecture question**:
- How should we manage state across chatbot, web app tabs (Plan/Shop/Cook), and database?
- Should we use objects in memory or stay stateless with IDs?
- How do we maintain performance while enabling rich interactions?

## Key Requirements You Identified

1. **Multi-tab coordination** - Plan → Shop → Cook tabs need shared state
2. **User history** - Save meal plans to learn preferences over time
3. **Performance** - Keep the chatbot "really snappy" (your words)
4. **Follow-up questions** - Handle "check these recipes for shellfish" efficiently

## Your Critical Insight

> "I think how we manage the object is critical. because we have other tabs (shop and cook) which need this. also we will be saving these finalized meal plans into memory so we get user history, allows us to suggest better recipes in the future."

**Translation:** This isn't a chatbot-only decision - it affects the entire system architecture.

## What We Saved

📄 **Full discussion captured in:** `docs/ARCHITECTURE_DISCUSSION.md`

✅ **Committed changes:**
- Architecture discussion document
- WIP chatbot improvements (object memory fields, better prompts, allergen info)
- All context preserved

## Next Steps When You Return

### 1. Investigation Phase (Start Here)
Run this command to analyze current state management:
```bash
# Launch planning agent to investigate
# This will analyze web app, chatbot, and database patterns
```

Or manually investigate:
- `src/web/app.py` - How does Flask share state between tabs?
- `src/chatbot.py` - How does chatbot handle MealPlan after creation?
- `src/data/database.py` - How are objects persisted/loaded?

### 2. Design Unified Strategy
Based on investigation, design how objects should flow:
```
Create MealPlan → Use in Chat/Web → Save to DB → Load for history
```

### 3. Implement State Management
- Decide: In-memory objects vs. stateless IDs?
- Pattern for cross-tab sharing
- Chatbot object memory strategy

## Files to Review

1. **Planning doc:** `docs/ARCHITECTURE_DISCUSSION.md` - Full discussion
2. **Web app:** `src/web/app.py` - Current Flask patterns
3. **Chatbot:** `src/chatbot.py` - WIP changes
4. **Models:** `src/data/models.py` - MealPlan, Recipe classes
5. **Database:** `src/data/database.py` - Persistence layer

## Quick Test

If you want to see the issue again:
```bash
cd ~/dinner-assistant
./chat.sh --verbose

# Then try:
You: I would like 5 recipes, one is pasta, all must have chicken
You: Can you see if there is shellfish in any of these?
# Watch it re-fetch everything instead of using what it has
```

## Git Status

```
Branch: main
Last commit: 86933f3 - docs: capture architecture discussion
Ahead of origin: 8 commits
Status: Clean working directory
```

## The Big Question

**Should the application use in-memory objects or stay stateless with IDs?**

Your answer will determine:
- How chatbot handles follow-ups
- How web app shares state between tabs
- How database persistence works
- Future features like history and recommendations

---

**Open this file when you return and you'll be right back in context!**
