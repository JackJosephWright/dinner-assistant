# Meal Planning Workflow

## Overview

The meal planning chatbot should follow a structured 3-phase workflow to ensure users get personalized, iterative meal planning with final confirmation before committing.

## Three Phases

### Phase 1: Initial Suggestions (Context-Based)

**Goal:** Generate initial meal suggestions based on user history and preferences.

**Inputs:**
- User meal history (recent meals to avoid repetition)
- User preferences (cuisines, dietary restrictions, cooking time limits)
- Number of days to plan
- Current date/week

**Process:**
1. Analyze user's meal history (last 2-4 weeks)
2. Identify patterns (favorite cuisines, proteins, cooking styles)
3. Generate 7 diverse meal suggestions with reasoning
4. Present suggestions to user with explanations

**Output Example:**
```
Based on your history, here's what I'm thinking for next week:

Monday: Sheet pan chicken with roasted vegetables
  → Quick weeknight option, you haven't had chicken in a while

Tuesday: Ground beef tacos
  → Mexican cuisine (your favorite), uses up ground beef

Wednesday: Baked salmon with quinoa
  → Favorite protein, different from your usual stir-fry prep

[... etc ...]

What do you think? Would you like to swap anything out?
```

**State After Phase 1:**
- Draft meal plan created (NOT saved to database)
- User can see all suggestions
- Ready for iteration

---

### Phase 2: Iteration & Refinement

**Goal:** Allow user to request changes, substitutions, or regenerations.

**Supported Actions:**
- **Swap a specific meal:** "Replace Wednesday's salmon with shellfish"
- **Regenerate a day:** "Give me something different for Friday"
- **Add constraints:** "Make Tuesday vegetarian instead"
- **Search alternatives:** "Show me other chicken options for Monday"

**Process:**
1. Parse user's requested change
2. Search for alternative recipes matching new criteria
3. Present 2-3 options for user to choose from
4. Update draft meal plan with selection
5. Show updated week overview

**Output Example:**
```
Sure! Here are shellfish options for Wednesday (25-30 min):

1. Garlic butter shrimp pasta - Quick, kid-friendly
2. Shrimp tacos with cilantro lime slaw
3. Lemon garlic shrimp skewers with rice

Which one sounds good?
```

**State During Phase 2:**
- Draft meal plan is mutable
- Changes are tracked but not persisted
- User can iterate multiple times
- System remembers context of the draft plan

**Iteration Continues Until:**
- User says "looks good", "lock it in", "save it"
- User explicitly confirms the plan
- User moves to next phase

---

### Phase 3: Lock-In & Commit

**Goal:** Finalize and save the meal plan, enabling downstream workflows.

**Trigger Phrases:**
- "Lock it in"
- "Save the meal plan"
- "Looks good, let's go with this"
- "Create the plan"
- "I'm happy with this"

**Process:**
1. Confirm final meal plan with user
2. Save meal plan to database with unique ID
3. Display saved plan with meal plan ID
4. Offer next steps (create shopping list, cooking guides)

**Output Example:**
```
Great! I've saved your meal plan for the week of Oct 20-26.

✓ Meal plan saved: mp_2025-10-20_20251013090430

Your week:
  Mon: Sheet pan chicken with roasted vegetables
  Tue: Ground beef tacos
  Wed: Garlic butter shrimp pasta
  Thu: One-pot pasta with Italian sausage
  Fri: Stir-fry chicken with vegetables
  Sat: Grilled chicken Caesar salad
  Sun: Herb-crusted rack of lamb

Would you like me to:
1. Create a shopping list?
2. Show cooking instructions for any meal?
3. Plan another week?
```

**State After Phase 3:**
- Meal plan is persisted in database
- Meal plan ID is stored in chatbot context
- Shopping and cooking agents can now access this plan
- User can't modify the plan (must create new one)

---

## State Management

### Draft vs. Committed Plans

**Draft Plan (Phases 1-2):**
- Stored in chatbot session memory only
- Not in database
- Mutable and temporary
- Lost if session ends

**Committed Plan (Phase 3):**
- Stored in database with unique ID
- Immutable (read-only)
- Persistent across sessions
- Accessible by other agents (shopping, cooking)

### Chatbot Context Variables

```python
self.draft_meal_plan = None           # Phase 1-2: Temporary plan
self.current_meal_plan_id = None      # Phase 3: Saved plan ID
self.planning_phase = None            # "suggesting", "iterating", "committed"
```

---

## Example Full Interaction

```
User: Plan meals for next week

[PHASE 1: Initial Suggestions]
Assistant: Based on your history, here's what I'm thinking for next week:
  Monday: Sheet pan chicken with roasted vegetables
  Tuesday: Ground beef tacos
  Wednesday: Baked salmon with quinoa
  Thursday: One-pot pasta with Italian sausage
  Friday: Stir-fry chicken with vegetables
  Saturday: Grilled chicken Caesar salad
  Sunday: Herb-crusted rack of lamb

What do you think? Would you like to swap anything out?

[PHASE 2: Iteration]
User: Replace Wednesday with a shellfish dish