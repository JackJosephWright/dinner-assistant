# Test Suite - Dinner Assistant Chatbot

## Overview
Automated tests to prevent regressions as we iterate on prompts and features.

## Test Scripts

### 1. `test_day_interpretation.sh` - Day/Meal Reference Parsing
**Purpose:** Ensure LLM correctly interprets user day references in swap requests

**Tests:**
- ✅ "swap day 3" → maps to 3rd meal (NOT November 3rd)
- ✅ "swap Monday" → finds Monday's meal in the plan
- ✅ "swap the chicken" → identifies chicken meal by name

**Run:** `./scripts/test/test_day_interpretation.sh`

**What to check:** Verify `date` values match expected meal dates, not calendar dates

---

### 2. `test_interactive_swap.sh` - Interactive Vague Swap Confirmation
**Purpose:** Test vague swap requests show options for user confirmation

**Tests:**
- ✅ "something else" triggers option display (not auto-swap)
- ✅ User can pick option by number (1, 2, 3)
- ✅ Swap completes from backup queue (<10ms)

**Run:** `./scripts/test/test_interactive_swap.sh`

**What to check:** Bot shows 3 options, user picks one, swap happens instantly

---

### 3. `test_multi_requirement.sh` - Multi-Requirement Planning
**Purpose:** Ensure complex planning requests work efficiently

**Tests:**
- ✅ "5 meals, one ramen, one spaghetti" → creates 5 meals (not 1-2)
- ✅ Uses single `plan_meals_smart` call (not plan + 5 swaps)
- ✅ LLM selector receives user requirements

**Run:** `./scripts/test/test_multi_requirement.sh`

**What to check:** Exactly 5 meals created in 2-3 LLM calls (not 9+)

---

### 4. `test_hybrid_matching.sh` - Hybrid Backup Matching
**Purpose:** Test two-tier backup matching (algorithmic + LLM)

**Tests:**
- ✅ Vague terms ("something", "different") match algorithmically
- ✅ Edge cases fall back to LLM semantic matching
- ✅ Specific requests ("different chicken") auto-swap without confirmation

**Run:** `./scripts/test/test_hybrid_matching.sh`

**What to check:** Verbose output shows which tier matched (algorithmic vs LLM)

---

### 5. `test_swap_fast.sh` - Fast Swap Performance
**Purpose:** Verify backup queue swaps complete in <10ms

**Tests:**
- ✅ Swap uses cached backups (0 DB queries)
- ✅ Performance <10ms consistently

**Run:** `./scripts/test/test_swap_fast.sh`

**What to check:** "Performance: <10ms" in output

---

### 6. `demo.sh` - Comprehensive End-to-End Demo
**Purpose:** Full workflow demonstration of all features

**Tests:**
- ✅ Multi-requirement planning
- ✅ Interactive vague swap
- ✅ Specific auto-swap
- ✅ Meal plan display

**Run:** `./scripts/demo/demo.sh`

**What to check:** All features work together smoothly

---

## Running All Tests

```bash
cd ~/dinner-assistant

# Quick validation (run all tests)
./scripts/test/test_day_interpretation.sh
./scripts/test/test_interactive_swap.sh
./scripts/test/test_multi_requirement.sh
./scripts/test/test_hybrid_matching.sh

# Full demo
./scripts/demo/demo.sh
```

---

## When to Run Tests

### Before Committing Changes
Run all tests to ensure no regressions:
```bash
./scripts/test/test_day_interpretation.sh && \
./scripts/test/test_interactive_swap.sh && \
./scripts/test/test_multi_requirement.sh && \
./scripts/test/test_hybrid_matching.sh
```

### After Prompt Updates
Especially run:
- `test_day_interpretation.sh` (day parsing is prompt-dependent)
- `test_multi_requirement.sh` (LLM selection is prompt-dependent)

### After Code Changes
Run relevant test based on what changed:
- Backup matching logic → `test_hybrid_matching.sh`
- Swap functionality → `test_swap_fast.sh`, `test_interactive_swap.sh`
- Planning logic → `test_multi_requirement.sh`

---

## Expected Failures

### Non-Deterministic LLM Behavior
Since we use LLMs, some variation is expected:
- Recipe selection may vary slightly
- Exact wording in responses may differ
- Tool choice might vary if multiple valid approaches exist

**What matters:**
- ✅ Correct tool is eventually called
- ✅ Correct data is passed to tools (especially dates!)
- ✅ Final outcome is correct (right meal swapped, right number of meals created)

### Flaky Tests
If a test occasionally fails:
1. Check if LLM chose a different (but valid) approach
2. Look for actual bugs (wrong date, wrong meal count, etc.)
3. If it's truly non-deterministic and acceptable, note it in this doc

---

## Test Coverage

### Prompt-Dependent Features (HIGH PRIORITY to test)
- ✅ Day interpretation ("day 3" → 3rd meal)
- ✅ Multi-requirement planning strategy
- ✅ Vague vs specific swap detection
- ✅ Tool selection (which tool to call when)

### Code-Dependent Features (MEDIUM PRIORITY)
- ✅ Backup queue performance
- ✅ Hybrid matching logic (algorithmic + LLM)
- ✅ JSON parsing robustness

### Integration Features (COVERAGE via demo.sh)
- ✅ End-to-end workflows
- ✅ Cache management
- ✅ Database persistence

---

## Adding New Tests

When adding a new prompt-dependent feature:

1. **Create a test script** named `test_<feature>.sh`
2. **Add to this document** with description and success criteria
3. **Run it before committing** any prompt changes
4. **Update demo.sh** if it's a user-facing feature

Template:
```bash
#!/bin/bash
# Test <feature name>

cd ~/dinner-assistant

echo "Testing <feature>..."
./chat.sh --verbose <<'EOF'
<test commands>
quit
EOF

echo "Expected: <what should happen>"
```

---

## Known Issues / TODOs

### Current Limitations
- [ ] No automated assertion checks (manual review of output required)
- [ ] No CI/CD integration yet
- [ ] LLM non-determinism makes strict assertions difficult

### Future Improvements
- [ ] Add Python-based test harness with assertions
- [ ] Mock LLM responses for deterministic testing
- [ ] Add performance benchmarks
- [ ] Create test fixtures with known-good outputs

---

## Maintenance

**Owner:** Update this file when adding/modifying tests

**Review Frequency:** Update after each major feature addition

**Last Updated:** 2025-10-31
