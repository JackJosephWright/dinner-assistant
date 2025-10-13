# Agentic Architecture

## Overview

The Meal Planning Assistant now uses **true LLM-powered agentic architecture** instead of algorithmic rule-based agents. This aligns with the original HANDOFF.md specification.

## What Changed?

### Before (Algorithmic)
- **Planning Agent**: Hard-coded scoring algorithm to select recipes
- **Shopping Agent**: Regex parsing to consolidate ingredients
- **Cooking Agent**: Dictionary lookups for substitutions

### After (Agentic)
- **Planning Agent**: LLM reasons about meal preferences and makes selections
- **Shopping Agent**: LLM intelligently merges ingredients ("2 cups flour" + "1 cup flour" = "3 cups")
- **Cooking Agent**: LLM provides contextual cooking tips and substitutions

## Architecture

```
User → MealPlanningAssistant → Agentic Agents (LangGraph + LLM) → MCP Tools → Database
                                      ↓
                              LLM Reasoning with Tools
```

### Three Agentic Components

#### 1. Agentic Planning Agent (`agentic_planning_agent.py`)

**LangGraph Workflow:**
```
analyze_history → search_recipes → select_meals
```

**How it's agentic:**
- LLM analyzes meal history to understand user preferences
- LLM decides what recipe categories to search for
- LLM selects specific meals with reasoning about variety and balance

**Example LLM reasoning:**
```
"I see the user enjoys salmon and Mexican food. Let me search for:
- Salmon dishes (user frequently has these)
- Quick chicken (weeknight-friendly protein)
- Vegetarian tacos (variety + user's Mexican preference)"
```

#### 2. Agentic Shopping Agent (`agentic_shopping_agent.py`)

**LangGraph Workflow:**
```
collect_ingredients → consolidate_with_llm → save_list
```

**How it's agentic:**
- LLM parses ingredient strings intelligently
- LLM merges quantities across different formats
- LLM categorizes items by store section contextually

**Example LLM reasoning:**
```
Input:
- "2 cups all-purpose flour" (from Pancakes)
- "1 cup flour" (from Cookies)
- "1/2 cup whole wheat flour" (from Bread)

LLM Output:
"flour | 3.5 cups (2 cups all-purpose, 1 cup all-purpose, 0.5 cups whole wheat) | pantry | Pancakes, Cookies, Bread"
```

#### 3. Agentic Cooking Agent (`agentic_cooking_agent.py`)

**LangGraph Workflow:**
```
load_recipe → generate_tips → analyze_timing → format_instructions
```

**How it's agentic:**
- LLM generates contextual cooking tips based on difficulty and ingredients
- LLM analyzes recipe steps to estimate prep vs cook time
- LLM formats instructions in a conversational, friendly way

**Example LLM reasoning:**
```
Recipe: "Beef Wellington" (Difficulty: Hard)

LLM Tips:
- "Read through all steps before starting - this recipe requires precise timing"
- "Have all ingredients prepped and ready (mise en place is crucial)"
- "Use a meat thermometer to ensure the beef is cooked to your preference"
```

## LangGraph State Management

Each agent uses LangGraph's StateGraph for managing workflow state:

### Planning State
```python
class PlanningState(TypedDict):
    week_of: str
    num_days: int
    preferences: Dict[str, Any]
    history_summary: Optional[str]      # LLM analysis
    recipe_candidates: List[Dict]       # LLM search guidance
    selected_meals: List[Dict]          # LLM selections
    reasoning: str                      # LLM explanations
```

### Shopping State
```python
class ShoppingState(TypedDict):
    meal_plan_id: str
    raw_ingredients: List[Dict]
    consolidated_items: List[Dict]      # LLM consolidation
    grocery_list_id: Optional[str]
```

### Cooking State
```python
class CookingState(TypedDict):
    recipe_id: str
    recipe_name: str
    ingredients: List[str]
    steps: List[str]
    cooking_tips: List[str]             # LLM tips
    timing_breakdown: Dict              # LLM timing analysis
```

## Backward Compatibility

The system gracefully falls back to algorithmic agents when:
1. `ANTHROPIC_API_KEY` is not set
2. User explicitly requests algorithmic mode

```python
# main.py automatically chooses:
assistant = MealPlanningAssistant(db_dir="data", use_agentic=True)

# With API key: Uses agentic agents
# Without API key: Falls back to algorithmic agents (logs warning)
```

## Usage

### With API Key (Agentic)
```bash
export ANTHROPIC_API_KEY='your-key-here'

# All modes will use agentic agents
./run.sh chat        # LLM chatbot with agentic agents
./run.sh workflow    # Agentic workflow
./run.sh interactive # Command mode with agentic agents
```

### Without API Key (Algorithmic Fallback)
```bash
# Falls back to algorithmic agents
./run.sh interactive # Command mode with algorithmic agents
./run.sh workflow    # Algorithmic workflow
```

## Testing

### Test Algorithmic Agents (No API Key Needed)
```bash
python tests/test_vertical_slice.py
python tests/test_planning.py
python tests/test_integration.py
```

### Test Agentic Agents (API Key Required)
```bash
export ANTHROPIC_API_KEY='your-key-here'
python tests/test_agentic_agents.py
```

## Key Differences from HANDOFF.md Specification

### ✅ Now Correct
- **Agentic vs Algorithmic**: Agents now use LLM reasoning, not hard-coded rules
- **LangGraph**: Proper StateGraph workflow for each agent
- **Conversational**: Agents explain their reasoning (e.g., "I see you enjoy Italian...")
- **Tool Use**: Agents call MCP tools, LLM decides when/how to use them

### Previous Issues (Now Fixed)
1. ❌ Planning agent used scoring algorithm → ✅ Now uses LLM reasoning
2. ❌ Shopping agent used regex parsing → ✅ Now uses LLM consolidation
3. ❌ Cooking agent used dictionary lookups → ✅ Now uses LLM substitutions
4. ❌ Only chatbot wrapper used LLM → ✅ Now all agents are LLM-powered

## Architecture Comparison

### Before: Chatbot Wraps Algorithmic Agents
```
User → Chatbot (LLM) → Algorithmic Agents (rules) → MCP Tools → Database
                              ↓
                        Hard-coded Logic
```

### After: True Agentic System
```
User → Chatbot (LLM) → Agentic Agents (LangGraph + LLM) → MCP Tools → Database
                              ↓
                        LLM Reasoning
```

## Files

### New Agentic Agents
- `src/agents/agentic_planning_agent.py` - LLM-powered planning
- `src/agents/agentic_shopping_agent.py` - LLM-powered shopping
- `src/agents/agentic_cooking_agent.py` - LLM-powered cooking

### Updated Orchestration
- `src/main.py` - Auto-selects agentic vs algorithmic agents
- `src/chatbot.py` - Uses agentic agents when API key available

### Legacy (Backward Compatibility)
- `src/agents/enhanced_planning_agent.py` - Algorithmic planning (fallback)
- `src/agents/shopping_agent.py` - Algorithmic shopping (fallback)
- `src/agents/cooking_agent.py` - Algorithmic cooking (fallback)

## API Costs

Using the agentic agents with Anthropic Claude API:
- **Model**: claude-3-5-sonnet-20241022
- **Cost**: ~$3 per million input tokens
- **Typical usage**:
  - Meal planning: ~5K tokens = $0.015
  - Shopping list: ~3K tokens = $0.009
  - Cooking guide: ~2K tokens = $0.006
  - **Full workflow**: ~$0.03 per run

Very affordable for personal use!

## Next Steps

Phase 2+ enhancements could include:
- Multi-agent collaboration (agents discussing meal choices)
- User feedback loops (learning from preferences)
- Advanced reasoning (nutritional balancing, budget optimization)
- Conversational refinement (ask clarifying questions)

## Summary

The system now properly implements the agentic architecture specified in HANDOFF.md:
- ✅ LangGraph for orchestration
- ✅ LLM-powered agents that reason
- ✅ Tool use through MCP
- ✅ Conversational and explainable
- ✅ State management between agents

This is a **true multi-agent system** where each agent uses LLM reasoning to make decisions, not just a chatbot wrapper around algorithmic functions.
