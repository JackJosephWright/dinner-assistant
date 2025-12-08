# Chatbot Architecture Refactor

## Goal
Clean up chatbot architecture using professional tool registry pattern with raw Anthropic API. No external agent frameworks.

## Branch Strategy
1. Merge `feature/multi-user-migration` → `main` first
2. Create new branch: `feature/chatbot-refactor` from main
3. Delete `feature/agent-sdk-refactor` (wrong name)

---

## 1. Goals & Constraints

### Non-Negotiables
- **Backwards-compatible UI behavior** - All existing endpoints work identically
- **No LLM provider change** - Stay on Anthropic Claude
- **Zero regression on planning quality** - Same recipes, same cuisine filtering
- **Same cost/call pattern** - No increase in LLM calls

### Nice-to-Have
- Faster swaps (currently swap_meal does LLM, swap_meal_fast uses cache)
- Lower cost via reduced redundant calls

### Concurrency Model
- **Single-user per chatbot instance** - Each Flask request creates new `MealPlanningChatbot`
- **Multi-user via multi-process** - Gunicorn workers handle different users
- **No shared mutable state** - State is per-request, stored in DB

---

## 2. BaseTool Design

### Interface: Context + Services (Not Whole Chatbot)
```python
@dataclass
class ToolContext:
    """Read-only context passed to tools."""
    user_id: int
    current_meal_plan_id: Optional[int]
    current_shopping_list_id: Optional[int]
    last_meal_plan: Optional[MealPlan]  # Cached object
    pending_swap_options: Optional[dict]
    week_start: Optional[date]
    selected_dates: Optional[List[date]]

@dataclass
class ToolServices:
    """Services bundle for tools (DB, LLM, etc.)."""
    db: DatabaseInterface
    anthropic: Anthropic
    shopping_agent: ShoppingAgent
    verbose_callback: Optional[Callable[[str], None]]

class BaseTool(ABC):
    name: str
    description: str
    parameters: dict  # JSON Schema
    category: Literal["query", "action", "agentic"]  # For metrics

    @abstractmethod
    def execute(self, ctx: ToolContext, services: ToolServices, **kwargs) -> ToolResult:
        pass
```

### Return Contract
```python
@dataclass
class ToolResult:
    success: bool
    data: Optional[Any] = None
    error: Optional[str] = None  # User-facing message
    error_code: Optional[str] = None  # Internal code for logging
    state_updates: Optional[Dict[str, Any]] = None  # Mutations to apply

# Examples:
ToolResult(success=True, data={"meals": [...]})
ToolResult(success=False, error="No recipes found for 'dragon meat'", error_code="NO_RESULTS")
ToolResult(success=True, data={"planned": 5, "failed": 2}, error="Could not find 2 meals")  # Partial
```

### State Mutations
- Tools **return** state updates in `state_updates` dict
- Orchestrator **applies** them after execution
- Tools **never** directly mutate chatbot state
- This enables testing tools in isolation

### Tool Categories
| Category | Examples | Metrics |
|----------|----------|---------|
| `query` | `search_recipes`, `get_meal_history`, `show_current_plan` | Fast, no side effects |
| `action` | `create_shopping_list`, `confirm_swap`, `add_extra_items` | DB mutations |
| `agentic` | `plan_meals`, `swap_meal` | LLM calls, slower |

---

## 3. ToolRegistry Design

### Registration: Explicit in `__init__.py`
```python
# src/tools/__init__.py
from .planning import PlanMealsTool
from .shopping import CreateShoppingListTool, AddExtraItemsTool
# ... etc

TOOLS = [
    PlanMealsTool(),
    CreateShoppingListTool(),
    # ...
]

def get_registry() -> ToolRegistry:
    registry = ToolRegistry()
    for tool in TOOLS:
        registry.register(tool)
    return registry
```

**Rationale**: Explicit registration is clearer than auto-discovery magic. Easy to see what's registered.

### Discovery Timing
- Registry created **once per chatbot instance** (constructor)
- Tools are stateless singletons, registry just holds references
- Minimal overhead (~1ms)

### Error Handling
```python
class ToolRegistry:
    def register(self, tool: BaseTool):
        if tool.name in self.tools:
            raise ValueError(f"Duplicate tool: {tool.name}")
        self.tools[tool.name] = tool

    def execute(self, name: str, ctx: ToolContext, services: ToolServices, **kwargs) -> ToolResult:
        if name not in self.tools:
            return ToolResult(success=False, error=f"Unknown tool: {name}", error_code="UNKNOWN_TOOL")
        try:
            return self.tools[name].execute(ctx, services, **kwargs)
        except Exception as e:
            logger.exception(f"Tool {name} failed")
            return ToolResult(success=False, error="Internal error", error_code="EXCEPTION")
```

### Schema Generation
```python
def get_tool_schemas(self) -> List[dict]:
    """Generate Anthropic API tool schemas from registered tools."""
    return [
        {
            "name": tool.name,
            "description": tool.description,
            "input_schema": tool.parameters  # Manually authored JSON Schema
        }
        for tool in self.tools.values()
    ]
```

**Decision**: Keep `parameters` as manually authored JSON Schema (not derived from type hints). More explicit, matches Anthropic API format directly.

---

## 4. LLM → Registry Mapping

### Orchestrator Tool Handling
```python
# In orchestrator (chatbot.py) - NO duplicate checks, all errors via registry
def handle_tool_call(self, tool_name: str, tool_input: dict) -> str:
    # 1. Build fresh context for this tool call
    ctx = self._build_context()

    # 2. Execute via registry (handles unknown tool, exceptions, everything)
    result = self.registry.execute(tool_name, ctx, self.services, **tool_input)

    # 3. Apply state updates
    self._apply_state_updates(result)

    # 4. Return result to LLM
    return json.dumps({"success": result.success, "data": result.data, "error": result.error})
```

### Validation Strategy
- **Trust Anthropic's schema validation** for type/required checks
- **Registry catches exceptions** and returns structured errors
- **No pre-check** for unknown tools (registry handles it uniformly)

### Error Recovery
- All errors returned as structured JSON to LLM
- LLM can retry or ask user for clarification
- Never abort interaction on tool failure

---

## 5. Consolidating plan_meals

### Canonical Semantics: `plan_meals_smart` (inline SQL + LLM)
The inline version is canonical because:
- It passes `search_query` directly to DB (cuisine filtering works)
- It's faster (no LangGraph overhead)
- It's simpler to maintain

### Differences to Preserve
| Feature | `plan_meals` (agentic) | `plan_meals_smart` (inline) | Consolidated |
|---------|------------------------|----------------------------|--------------|
| Cuisine filtering | ❌ Ignores | ✅ Uses search_query | ✅ |
| Variety enforcement | Via LLM prompts | Via backup selection | Via backup selection |
| Progress messages | Via LangGraph | Via verbose_callback | Via verbose_callback |

### Regression Testing Strategy
1. **Before consolidation**: Create golden test transcripts
   - "Plan 7 days of meals" → capture recipe names
   - "Plan French meals for the week" → verify all French
   - "Plan 3 dinners with chicken" → verify chicken recipes
2. **After consolidation**: Compare output patterns

### Hidden Coupling Check
- `swap_meal` uses `last_meal_plan` → ✅ preserved in ToolContext
- `check_allergens` uses `last_meal_plan` → ✅ preserved
- `create_shopping_list` uses `current_meal_plan_id` → ✅ preserved

---

## 6. LangGraph / Shopping Agent

### Interaction Pattern
```python
# In CreateShoppingListTool.execute()
class CreateShoppingListTool(BaseTool):
    category = "agentic"

    def execute(self, ctx: ToolContext, services: ToolServices, **kwargs) -> ToolResult:
        if not ctx.current_meal_plan_id:
            return ToolResult(success=False, error="No meal plan to create list from")

        # Delegate to shopping agent (LangGraph)
        result = services.shopping_agent.create_shopping_list(
            meal_plan_id=ctx.current_meal_plan_id,
            user_id=ctx.user_id
        )

        return ToolResult(
            success=True,
            data=result,
            state_updates={"current_shopping_list_id": result["id"]}
        )
```

### State Access
- Tool accesses state via `ctx.current_meal_plan_id` (read-only)
- Returns updates via `state_updates` (write)
- Never directly mutates

### Caching
- Shopping agent already caches internally
- No additional caching needed in tool layer

---

## 7. State Management

### Formalized ChatState
```python
@dataclass
class ChatState:
    """All mutable state for a chat session."""
    user_id: int
    # Tool-mutable (via state_updates):
    current_meal_plan_id: Optional[int] = None
    current_shopping_list_id: Optional[int] = None
    last_meal_plan: Optional[MealPlan] = None
    last_search_results: List[Recipe] = field(default_factory=list)
    pending_swap_options: Optional[dict] = None
    # UI-set (by orchestrator, not tools):
    selected_dates: Optional[List[date]] = None
    week_start: Optional[date] = None
    # NOT included: conversation_history (caller's responsibility)
```

### State Persistence
- **In-memory per request** - Not persisted between HTTP requests
- **DB for durable state** - meal_plan_id, shopping_list_id stored in DB
- **Session rehydration** - Chatbot loads latest plan from DB on init

### Parallel Tabs / Race Conditions
- Current design: Each tab creates new chatbot instance
- DB is source of truth for meal plans
- `pending_swap_options` is ephemeral (lost on tab switch) - acceptable

---

## 8. System Prompt Strategy

### Minimal Prompt (Target: <20 lines)
```python
SYSTEM_PROMPT = """You are a meal planning assistant. You help users plan meals, create shopping lists, and provide cooking guidance.

Available tools:
- plan_meals: Create a meal plan. Use search_query for specific cuisines/ingredients.
- search_recipes: Search for specific recipes by name or ingredients.
- create_shopping_list: Generate a shopping list from the current meal plan.
- swap_meal: Replace a meal in the plan with alternatives.
- get_cooking_guide: Get detailed cooking instructions for a recipe.

Guidelines:
- For meal planning requests, use plan_meals directly (don't search first).
- For cuisine-specific requests (e.g., "French meals"), pass the cuisine as search_query.
- Be concise in responses. Show meal names, not full recipes unless asked.
"""
```

### Cuisine Logic Migration
| Old Location | New Location |
|--------------|--------------|
| System prompt workaround | Tool description: "Use search_query for cuisines" |
| "DO NOT use search_recipes for planning" | Removed - LLM will learn from tool descriptions |

### Testing Minimal Prompt
1. Test against known failure cases (French meals, "day 1" semantics)
2. If failures occur, add targeted guidance (not blanket rules)
3. Iterate until stable

---

## 9. File Layout & Imports

### Structure
```
src/
├── chatbot.py          # Orchestrator only (~300 lines)
├── tools/
│   ├── __init__.py     # Explicit registration
│   ├── base.py         # BaseTool, ToolResult, ToolContext, ToolServices
│   ├── registry.py     # ToolRegistry
│   ├── planning.py     # PlanMealsTool
│   ├── shopping.py     # CreateShoppingListTool, AddExtraItemsTool
│   ├── recipes.py      # SearchRecipesTool, GetCookingGuideTool
│   ├── meals.py        # SwapMealTool, ConfirmSwapTool, ShowCurrentPlanTool
│   ├── history.py      # GetMealHistoryTool
│   └── allergens.py    # CheckAllergensTool, ListMealsByAllergenTool
├── data/
│   ├── database.py     # DatabaseInterface (unchanged)
│   └── models.py       # Recipe, MealPlan, etc. (unchanged)
└── agents/
    └── shopping_agent.py  # LangGraph shopping (unchanged)
```

### Circular Import Prevention
```python
# src/tools/base.py - Use TYPE_CHECKING
from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from src.data.database import DatabaseInterface
    from anthropic import Anthropic
```

---

## 10. Testing Strategy

### Unit Tests
```python
# tests/unit/test_tools/test_planning.py
def test_plan_meals_with_cuisine():
    ctx = ToolContext(user_id=1, ...)
    services = MockToolServices(db=mock_db, ...)

    tool = PlanMealsTool()
    result = tool.execute(ctx, services, num_days=7, search_query="French")

    assert result.success
    assert len(result.data["meals"]) == 7
    # Verify all meals match "French" query

def test_plan_meals_no_results():
    # Mock DB returns empty
    result = tool.execute(ctx, services, num_days=7, search_query="dragon meat")
    assert not result.success
    assert result.error_code == "NO_RESULTS"
```

### Integration Tests
```python
# tests/integration/test_tool_registry.py
def test_registry_executes_tool():
    registry = get_registry()
    ctx = ToolContext(...)
    services = ToolServices(db=real_db, ...)

    result = registry.execute("search_recipes", ctx, services, query="chicken")
    assert result.success
```

### Golden Tests (Before Consolidation)
```python
# tests/golden/test_planning_transcripts.py
GOLDEN_CASES = [
    ("Plan 7 days of meals", lambda r: len(r["meals"]) == 7),
    ("Plan French meals for the week", lambda r: all("French" in m.get("cuisine", "") or ... for m in r["meals"])),
]
```

### Existing Tests
- Keep all Playwright tests in `tests/web/`
- Keep existing chatbot tests, adapt to new interface

---

## 11. Error Handling & Observability

### Logging
```python
# In registry.execute()
logger.info(f"Tool {name} called", extra={
    "tool": name,
    "category": tool.category,
    "user_id": ctx.user_id,
})

start = time.time()
result = tool.execute(ctx, services, **kwargs)
elapsed = time.time() - start

logger.info(f"Tool {name} completed", extra={
    "tool": name,
    "success": result.success,
    "duration_ms": elapsed * 1000,
    "error_code": result.error_code,
})
```

### Metrics (Future)
- Per-tool latency histograms
- Per-tool success/failure rates
- LLM calls per user request

---

## 12. Performance & Cost

### Call Parity
- Goal: Same number of LLM calls as current implementation
- No new caching requirements

### Startup Time
- Not critical (long-lived Flask process)
- Registry creation: ~1ms
- Acceptable

---

## Implementation Phases

### Phase 1: Infrastructure (Day 1)
1. Create `src/tools/` directory
2. Implement `base.py`: `BaseTool`, `ToolResult`, `ToolContext`, `ToolServices`
3. Implement `registry.py`: `ToolRegistry`
4. Write unit tests for registry

### Phase 2: Extract Simple Tools (Day 1-2)
Extract in order (test each before moving on):
1. `get_meal_history` → `history.py`
2. `show_current_plan` → `meals.py`
3. `search_recipes` → `recipes.py`
4. `get_cooking_guide` → `recipes.py`

### Phase 3: Extract Complex Tools (Day 2-3)
5. `check_allergens` → `allergens.py`
6. `create_shopping_list` → `shopping.py`
7. `swap_meal` + `confirm_swap` → `meals.py`
8. `plan_meals` (consolidated) → `planning.py`

### Phase 4: Integrate & Cleanup (Day 3)
1. Update `chatbot.py` to use registry
2. Remove old `execute_tool()` method
3. Simplify system prompt
4. Run full test suite

### Phase 5: Validate (Day 4)
1. Run golden tests
2. Manual testing of edge cases
3. Playwright tests pass

---

---

## Detailed Design Decisions

### Q1: What "backwards-compatible" means
- **JSON structure**: Same field names and nesting ✅
- **Field ordering**: Not guaranteed (JSON is unordered)
- **Recipe IDs**: Not bit-for-bit identical (LLM jitter exists)
- **Planning quality**: "Qualitatively similar" - same cuisine filtering, reasonable variety
- **Natural-language**: Can differ; only structured data must match
- **Test approach**: Assert properties (`len(meals) == 7`, `all French`) not exact IDs

### Q2: Request/response lifecycle
```python
# What constructor gets:
def __init__(self, user_id: int, verbose_callback=None):
    # Queries from DB on init:
    self.state = ChatState(user_id=user_id)
    self.state.current_meal_plan_id = self._load_most_recent_plan_id()
    # Does NOT load: shopping list, swap options (ephemeral)

# ChatState is attribute on MealPlanningChatbot
class MealPlanningChatbot:
    state: ChatState
    services: ToolServices
    registry: ToolRegistry

# ToolContext built by orchestrator on each tool call
def _build_context(self) -> ToolContext:
    return ToolContext(
        user_id=self.state.user_id,
        current_meal_plan_id=self.state.current_meal_plan_id,
        # ... read-only projection
    )
```

### Q3: pending_swap_options lifecycle
- **Scope**: In-memory within single HTTP request
- **Multi-turn**: Works because LLM tool loop runs in same request
  - Turn 1: swap_meal → sets pending_swap_options → returns to LLM
  - Turn 2: LLM says "option 3" → confirm_swap uses pending_swap_options
  - All within same streaming response
- **Tab switch**: Lost (acceptable) - user just asks to swap again
- **NOT persisted**: No Redis/session storage for swap options

### Q4: Conversation history
- **Storage**: Passed in by Flask caller via request/session
- **Not in ChatState**: History is caller's responsibility
- **Pattern**:
```python
# In Flask route:
history = session.get('chat_history', [])
chatbot = MealPlanningChatbot(user_id=current_user.id)
response = chatbot.chat(message, history=history)
session['chat_history'] = history + [user_msg, assistant_msg]
```

### Q5: Streaming and tool loop
- Tool loop runs inside single request while streaming
- Registry design is transparent to streaming (same as current)
- Multiple tools in one turn: build fresh ToolContext for each
- State updates applied sequentially, in order
- No risk of mid-stream desync (single-threaded per request)

### Q6: ToolServices - what's included
```python
@dataclass
class ToolServices:
    db: DatabaseInterface
    anthropic: Anthropic  # For tools that need LLM (swap, plan)
    shopping_agent: ShoppingAgent  # Injected, not instantiated in tools
    verbose_callback: Optional[Callable[[str], None]]
    # NOT included: logging (use module-level logger)
```
**Decision**: shopping_agent is injected via ToolServices (easier to mock, cleaner DI)

### Q7: Transaction boundaries
- **DatabaseInterface handles transactions**
- Tools call `services.db.save_meal_plan()` etc.
- No explicit transaction wrapping in orchestrator
- If multi-row write needed, tool can use `with services.db.transaction():`

### Q8: ToolResult semantics
```python
# Allowed state_updates keys (enforced by orchestrator):
# These match the "Tool-mutable" fields in ChatState
ALLOWED_STATE_KEYS = {
    'current_meal_plan_id',
    'current_shopping_list_id',
    'last_meal_plan',
    'last_search_results',  # Added - search_recipes sets this
    'pending_swap_options',
}

def apply_state_updates(self, result: ToolResult):
    if result.state_updates:
        for key, value in result.state_updates.items():
            if key not in ALLOWED_STATE_KEYS:
                logger.warning(f"Ignoring unknown state key: {key}")
                continue
            setattr(self.state, key, value)
```

- **Conflicting updates**: Applied in order, last wins (deterministic)
- **Error types**:
  - `success=False` + `error` → user-facing, LLM can recover
  - `error_code` → for logging/metrics only, not exposed to LLM

### Q9: Error handling - single path
```python
# Registry handles all errors uniformly
class ToolRegistry:
    def execute(self, name: str, ctx: ToolContext, services: ToolServices, **kwargs) -> ToolResult:
        if name not in self.tools:
            return ToolResult(success=False, error=f"Unknown tool: {name}", error_code="UNKNOWN_TOOL")
        try:
            return self.tools[name].execute(ctx, services, **kwargs)
        except NoRecipesFoundError as e:
            return ToolResult(success=False, error=str(e), error_code="NO_RESULTS")
        except Exception as e:
            logger.exception(f"Tool {name} failed")
            return ToolResult(success=False, error="Something went wrong", error_code="EXCEPTION")

# Orchestrator just uses registry result, no duplicate checks
```

### Q10: plan_meals consolidation
- **Canonical**: `plan_meals_smart` (inline SQL + LLM)
- **Lost from LangGraph**: Intermediate search steps, slightly more variety
- **Acceptable**: Yes, inline version is faster and cuisine works
- **Cost**: May decrease (fewer sub-calls) - acceptable
- **Golden tests**: Assert properties, not IDs
  - "7 meals returned"
  - "All meals match 'French' (tag or name)"
  - "No duplicates"

### Q11: Swap confirmation flow
```python
# Turn 1: swap_meal returns candidates
class SwapMealTool:
    def execute(...):
        candidates = self._find_alternatives(ctx, services, ...)
        return ToolResult(
            success=True,
            data={"candidates": [{"id": r.id, "name": r.name} for r in candidates[:5]]},
            state_updates={"pending_swap_options": {"meal_index": idx, "candidates": candidates}}
        )

# Turn 2: confirm_swap uses pending state
class ConfirmSwapTool:
    def execute(self, ctx, services, selection: int):
        if not ctx.pending_swap_options:
            return ToolResult(success=False, error="No pending swap")
        selected = ctx.pending_swap_options["candidates"][selection]
        # Write to DB
        services.db.update_planned_meal(...)
        return ToolResult(
            success=True,
            data={"swapped_to": selected.name},
            state_updates={"pending_swap_options": None}  # Clear
        )
```

### Q12: System prompt strategy
- **Enrich tool descriptions** with constraints:
```python
PlanMealsTool.description = """Create a meal plan for specified days.
Use search_query for cuisines (e.g., "French", "Italian") or ingredients (e.g., "chicken").
Call this directly for planning requests - do not use search_recipes to manually build plans."""
```
- **Allow search_recipes → plan_meals** for explicit "find me 10, then build plan" flows
- **Prompt discourages**, tool descriptions reinforce

### Q13: Testing approach
- **Golden tests**: Not yet recorded - will create before consolidation
- **Stabilizing**: Use temperature=0, assert properties not exact outputs
- **Playwright tests**: Check structure (meal cards exist), not exact wording
- **Rollout**: Hard cutover, no feature flag (tests must be green)

### Q14: Performance measurement
- **Instrumentation**: Logging in `registry.execute()` with tool name, duration, user_id
- **LLM call tracking**: Log each `anthropic.messages.create()` call
- **Retry tolerance**: Accept some edge cases with more calls
- **No hard cap**: Trust LLM to not loop infinitely (current behavior)

---

## Final Clarifying Answers (Single Source of Truth)

| Question | Answer |
|----------|--------|
| **History ownership** | Web layer's job. `MealPlanningChatbot` never owns `conversation_history`. Passed as parameter to `chat()`. |
| **Shopping agent injection** | Injected via `ToolServices`. Never instantiated inside tools. |
| **Tool-mutable state** | Exactly: `current_meal_plan_id`, `current_shopping_list_id`, `last_meal_plan`, `last_search_results`, `pending_swap_options` |
| **Validation responsibility** | Trust Anthropic's schema 100%. Registry catches exceptions, returns `EXCEPTION` error code. |
| **Swap interaction model** | v1: Swaps + confirmations always resolved inside single streamed LLM turn. No cross-request persistence of `pending_swap_options`. |

---

## Golden Test Assertions (Strict Enough to Catch Regressions)

```python
# Cuisine tests - must be strict
def test_french_meals():
    result = plan_meals(num_days=7, search_query="French")
    assert len(result["meals"]) == 7
    for meal in result["meals"]:
        # Positive: has French indicator
        assert any([
            "french" in meal["name"].lower(),
            "French" in meal.get("tags", []),
            meal.get("cuisine") == "French"
        ])
        # Negative: no clearly wrong cuisines
        wrong_cuisines = ["Mexican", "Chinese", "Thai", "Indian", "Japanese"]
        for wrong in wrong_cuisines:
            assert wrong not in meal.get("tags", [])

# Variety tests
def test_no_duplicates():
    result = plan_meals(num_days=7)
    recipe_ids = [m["recipe_id"] for m in result["meals"]]
    assert len(recipe_ids) == len(set(recipe_ids))  # No duplicates

def test_variety_unconstrained():
    result = plan_meals(num_days=7)
    # At least 3 distinct "types" (e.g., not all chicken)
    # This is looser - just checks variety exists
    names = [m["name"].lower() for m in result["meals"]]
    assert len(set(names)) >= 5  # At least 5 distinct meal names
```

---

## Success Criteria
- [ ] All 13 tools in `src/tools/` with `BaseTool` interface
- [ ] ToolRegistry with explicit registration
- [ ] `chatbot.py` under 400 lines
- [ ] System prompt under 20 lines
- [ ] All existing tests pass
- [ ] Golden tests for cuisine filtering pass
- [ ] No duplicate planning tools
