# Architectural Decision Log

**Project:** Dinner Assistant - Chat-Forward Redesign
**Start Date:** 2025-10-28

---

## Decision 1: Pre-Enrich Recipe Dataset with Structured Ingredients

**Date:** 2025-10-28
**Status:** ✅ Approved
**Decider:** User

**Context:**
Shopping list generation and recipe scaling require constant parsing of ingredient strings like "2 cups flour". This happens thousands of times during normal usage.

**Decision:**
Pre-parse and enrich all 492K recipes with structured ingredient data during a one-time data loading process.

**Rationale:**
- Shopping list generation: 10-100x faster
- Recipe scaling: Trivial math instead of string parsing
- Allergen detection: Instant filtering
- Enables ingredient-based search
- One-time cost, permanent benefit

**Trade-offs:**
- ✅ Pros: Massive performance improvement, enables powerful features
- ❌ Cons: +1.08 GB database size (3.3 GB total), one-time enrichment cost (~30-60 min)

**Consequences:**
- Database size increases from 2.2 GB to ~3.3 GB (acceptable)
- Enrichment script must handle 492K recipes with error handling
- Must maintain both raw and structured formats for fallback

---

## Decision 2: Ingredient Data Structure

**Date:** 2025-10-28
**Status:** ✅ Approved
**Decider:** User

**Context:**
Need to define structure for parsed ingredient data that will be stored for 492K recipes.

**Decision:**
```python
@dataclass
class Ingredient:
    raw: str
    quantity: Optional[float] = None
    unit: Optional[str] = None
    name: str = ""
    modifier: Optional[str] = None
    preparation: Optional[str] = None
    category: str = "other"
    allergens: List[str] = []
    substitutable: bool = True
    confidence: float = 1.0
    parse_method: str = "auto"
```

**Key Design Choices Approved:**
1. **No additional fields:** Rejected `is_optional`, `storage_location`, `typical_brands` - not needed for MVP
2. **10 categories:** Sufficient granularity (produce, meat, seafood, dairy, baking, pantry, condiments, frozen, beverages, other)
3. **Size acceptable:** ~220 bytes per ingredient, +1.08 GB total database size
4. **Confidence thresholds:** ≥0.9 trust fully, 0.7-0.9 caution, 0.5-0.7 questionable, <0.5 raw only

**Rationale:**
- Keep it simple and focused on core use cases
- 10 categories match typical grocery store layout
- Size increase justified by performance benefits
- Confidence scoring enables graceful degradation

**Consequences:**
- Leaner data structure (easier to maintain)
- Can add additional fields later if needed
- Storage overhead acceptable for modern systems

---

## Decision 3: Embed Full Recipe Objects in Meal Plans

**Date:** 2025-10-28
**Status:** ✅ Approved (pending Step 2e design)
**Decider:** User

**Context:**
Current approach stores only recipe_id in PlannedMeal, requiring re-querying database for shopping list and cooking guidance (5-7 extra queries per plan).

**Decision:**
Embed full Recipe objects (including structured ingredients) in PlannedMeal when creating meal plans.

**Rationale:**
- Eliminates 5-7 database queries per plan usage
- Enables multi-recipe meals (main + sides)
- Chat has full context available
- Shopping list generation has direct access to ingredients
- Recipe scaling works without re-querying

**Trade-offs:**
- ✅ Pros: No re-querying, enables multi-recipe, faster operations
- ❌ Cons: Meal plan storage increases from 840 bytes to 28-56 KB

**Size Impact:**
- Single plan: 840 bytes → 28-56 KB (30-70x larger)
- 50 plans: 42 KB → 1.4-2.8 MB
- **Acceptable:** Modern devices handle this easily

**Consequences:**
- Need to update PlannedMeal structure (Step 4)
- Need to update MealPlan structure (Step 6)
- Need to update serialization logic
- Shopping and cooking agents become simpler (no DB queries)

---

## Template for Future Decisions

**Decision:** [Title]
**Date:** YYYY-MM-DD
**Status:** Proposed / Approved / Rejected / Superseded
**Decider:** User / Team / Claude

**Context:**
[What circumstances led to this decision?]

**Decision:**
[What did we decide?]

**Rationale:**
[Why did we choose this approach?]

**Trade-offs:**
[What are the pros and cons?]

**Consequences:**
[What impact does this have on the system?]

---

**End of Decision Log**
