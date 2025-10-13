# Refactoring Summary: Algorithmic → Agentic

## Problem Identified

The original implementation was **algorithmic** (rule-based) instead of **agentic** (LLM-powered), which did not match the HANDOFF.md specification.

### What Was Wrong

1. **Planning Agent** (`enhanced_planning_agent.py:175-311`)
   - Used hard-coded scoring algorithm to select recipes
   - Word frequency counter for "preference learning"
   - No LLM reasoning about meal choices

2. **Shopping Agent** (`shopping_tools.py:187-280`)
   - Regex parsing for ingredient extraction
   - Simple numeric addition for consolidation
   - Dictionary-based store section categorization

3. **Cooking Agent** (`cooking_tools.py:28-41`)
   - Fixed dictionary for ingredient substitutions
   - Keyword matching for prep vs cook steps
   - No contextual reasoning

### What HANDOFF.md Required

> "Uses LLM to merge similar ingredients"
> "LangGraph: Proven agent orchestration, state management"
> "I'll create a balanced meal plan for January 20-26. Based on your history, I see you enjoy Italian and Mexican..."

The spec called for **agents that reason and explain their decisions**, not algorithms.

## Solution Implemented

### New Agentic Agents

#### 1. Agentic Planning Agent
**File**: `src/agents/agentic_planning_agent.py`

**LangGraph Workflow**:
```python
analyze_history → search_recipes → select_meals
```

**LLM Reasoning Examples**:
- "User frequently enjoys salmon dishes" → searches for salmon recipes
- "Need at least 1 vegetarian meal, user likes pasta" → searches for vegetarian pasta
- "Quick chicken for Monday, user loves salmon" → selects with reasoning

**Key Methods**:
- `_analyze_history_node()`: LLM analyzes patterns in meal history
- `_search_recipes_node()`: LLM decides what to search for
- `_select_meals_node()`: LLM selects specific meals with variety reasoning

#### 2. Agentic Shopping Agent
**File**: `src/agents/agentic_shopping_agent.py`

**LangGraph Workflow**:
```python
collect_ingredients → consolidate_with_llm → save_list
```

**LLM Reasoning Examples**:
- Input: "2 cups flour", "1 cup flour" → Output: "3 cups flour"
- Input: "yellow onion", "onion" → Output: "onions" (normalized)
- Intelligently categorizes items by store section

**Key Methods**:
- `_collect_ingredients_node()`: Gathers raw ingredients from recipes
- `_consolidate_with_llm_node()`: LLM parses, merges, and categorizes
- `_save_list_node()`: Saves consolidated results

#### 3. Agentic Cooking Agent
**File**: `src/agents/agentic_cooking_agent.py`

**LangGraph Workflow**:
```python
load_recipe → generate_tips → analyze_timing → format_instructions
```

**LLM Reasoning Examples**:
- Contextual tips based on difficulty and ingredients
- Timing analysis by reading actual recipe steps
- Substitutions that consider the recipe context

**Key Methods**:
- `_generate_tips_node()`: LLM creates helpful cooking tips
- `_analyze_timing_node()`: LLM estimates prep vs cook time
- `get_substitutions()`: LLM suggests contextual substitutions

### Backward Compatibility

**File**: `src/main.py`

The orchestrator automatically chooses agents:
```python
if use_agentic and AGENTIC_AVAILABLE:
    # Use LLM-powered agents
    self.planning_agent = AgenticPlanningAgent(self.db)
else:
    # Fall back to algorithmic agents
    self.planning_agent = EnhancedPlanningAgent(self.db)
```

**Benefits**:
- Works without API key (falls back gracefully)
- No breaking changes to existing code
- Users can choose which mode to use

## Files Changed

### New Files Created
1. `src/agents/agentic_planning_agent.py` (519 lines) - LLM-powered planning
2. `src/agents/agentic_shopping_agent.py` (399 lines) - LLM-powered shopping
3. `src/agents/agentic_cooking_agent.py` (448 lines) - LLM-powered cooking
4. `tests/test_agentic_agents.py` (300 lines) - Agentic agent tests
5. `AGENTIC_ARCHITECTURE.md` (350 lines) - Architecture documentation
6. `REFACTORING_SUMMARY.md` (this file)

### Files Modified
1. `src/main.py` - Added agentic agent selection
2. `src/chatbot.py` - Uses agentic agents when available
3. `README.md` - Updated with agentic architecture info

### Files Preserved (Backward Compatibility)
1. `src/agents/enhanced_planning_agent.py` - Algorithmic fallback
2. `src/agents/shopping_agent.py` - Algorithmic fallback
3. `src/agents/cooking_agent.py` - Algorithmic fallback
4. `src/mcp_server/tools/*` - Tools remain unchanged

## Technical Stack

### Dependencies Added
- `langgraph>=0.2.0` - StateGraph workflow management
- `langchain>=0.3.0` - Agent framework
- `langchain-anthropic>=0.2.0` - Anthropic integration

### LangGraph Patterns Used

**StateGraph**:
```python
workflow = StateGraph(PlanningState)
workflow.add_node("analyze_history", self._analyze_history_node)
workflow.add_node("search_recipes", self._search_recipes_node)
workflow.add_node("select_meals", self._select_meals_node)
workflow.set_entry_point("analyze_history")
workflow.add_edge("analyze_history", "search_recipes")
workflow.add_edge("search_recipes", "select_meals")
workflow.add_edge("select_meals", END)
```

**State Management**:
```python
class PlanningState(TypedDict):
    week_of: str
    preferences: Dict[str, Any]
    history_summary: Optional[str]      # LLM output
    recipe_candidates: List[Dict]       # LLM output
    selected_meals: List[Dict]          # LLM output
    reasoning: str                      # LLM explanation
```

## Testing

### Without API Key (Algorithmic Fallback)
```bash
# Existing tests continue to work
python tests/test_vertical_slice.py
python tests/test_planning.py
python tests/test_integration.py
```

### With API Key (Agentic Agents)
```bash
export ANTHROPIC_API_KEY='your-key-here'
python tests/test_agentic_agents.py
```

### Manual Testing
```bash
# Agentic workflow
export ANTHROPIC_API_KEY='your-key-here'
./run.sh workflow

# Algorithmic workflow (fallback)
unset ANTHROPIC_API_KEY
./run.sh workflow
```

## API Costs

**Model**: claude-3-5-sonnet-20241022
**Pricing**: ~$3 per million input tokens

**Typical Usage**:
- Planning Agent: ~5,000 tokens = $0.015
- Shopping Agent: ~3,000 tokens = $0.009
- Cooking Agent: ~2,000 tokens = $0.006
- **Full workflow**: ~$0.03 per run

Very affordable for personal use!

## Verification

### Import Test (No API Key)
```bash
$ python3 -c "
from src.main import MealPlanningAssistant
assistant = MealPlanningAssistant(use_agentic=True)
print(f'Agentic: {assistant.is_agentic}')
"
# Output: Agentic: False (falls back)
```

### Import Test (With API Key)
```bash
$ export ANTHROPIC_API_KEY='sk-ant-...'
$ python3 -c "
from src.main import MealPlanningAssistant
assistant = MealPlanningAssistant(use_agentic=True)
print(f'Agentic: {assistant.is_agentic}')
"
# Output: Agentic: True
```

## Comparison Table

| Feature | Before (Algorithmic) | After (Agentic) |
|---------|---------------------|-----------------|
| **Planning** | Scoring algorithm | LLM reasoning about preferences |
| **Shopping** | Regex parsing | LLM consolidation & categorization |
| **Cooking** | Dictionary lookups | LLM contextual guidance |
| **Explanation** | Template strings | LLM natural language |
| **Workflow** | Sequential functions | LangGraph StateGraph |
| **Reasoning** | Hard-coded rules | LLM decisions with explanations |
| **Flexibility** | Fixed logic | Adapts to context |
| **API Required** | No | Yes (with fallback) |

## Key Achievements

✅ **Matches HANDOFF.md Specification**
- LangGraph for orchestration ✓
- LLM-powered agents ✓
- Conversational reasoning ✓
- Tool use through MCP ✓

✅ **Maintains Backward Compatibility**
- Works without API key ✓
- No breaking changes ✓
- Existing tests pass ✓

✅ **Improved Architecture**
- Proper agent reasoning ✓
- State management with LangGraph ✓
- Explainable decisions ✓

✅ **Production Ready**
- Error handling ✓
- Graceful fallback ✓
- Comprehensive logging ✓
- Full documentation ✓

## Next Steps (Future Enhancements)

1. **Multi-Agent Collaboration**: Agents discuss meal choices with each other
2. **User Feedback Loop**: Learn from "thumbs up/down" on suggestions
3. **Advanced Reasoning**: Nutritional balancing, budget optimization
4. **Conversational Refinement**: Agents ask clarifying questions
5. **Memory**: Long-term preference learning across sessions

## Conclusion

The system now properly implements the **agentic multi-agent architecture** specified in HANDOFF.md:

- ✅ LangGraph for orchestration
- ✅ LLM-powered agents that reason
- ✅ Tool use through MCP
- ✅ Conversational and explainable
- ✅ State management between agents

This is a **true multi-agent system** where each agent uses LLM reasoning to make decisions, not just a chatbot wrapper around algorithmic functions.

The refactoring transforms the project from "algorithmic automation" to "agentic intelligence" while maintaining full backward compatibility for users without API keys.
