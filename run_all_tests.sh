#!/bin/bash
# Run all regression tests before committing changes

cd ~/dinner-assistant

echo "========================================================================"
echo "🧪 RUNNING ALL REGRESSION TESTS"
echo "========================================================================"
echo ""
echo "This will run all test suites to check for regressions."
echo "Review output carefully for any unexpected behavior."
echo ""
echo "========================================================================"
echo ""

FAILED=0

# Test 1: Day interpretation
echo ""
echo "▶️  TEST 1/4: Day Interpretation"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
if timeout 180 ./test_day_interpretation.sh > /tmp/test_day_interp.log 2>&1; then
    echo "✅ PASSED: Day interpretation tests"
    # Show key results
    grep "date" /tmp/test_day_interp.log | head -3
else
    echo "❌ FAILED: Day interpretation tests"
    FAILED=$((FAILED + 1))
    tail -20 /tmp/test_day_interp.log
fi

# Test 2: Interactive swap
echo ""
echo "▶️  TEST 2/4: Interactive Swap"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
if timeout 180 ./test_interactive_swap.sh > /tmp/test_interactive.log 2>&1; then
    if grep -q "I have these options" /tmp/test_interactive.log && \
       grep -q "✓ Swapped meal" /tmp/test_interactive.log; then
        echo "✅ PASSED: Interactive swap tests"
    else
        echo "❌ FAILED: Interactive swap didn't show options or complete swap"
        FAILED=$((FAILED + 1))
        grep -A5 "something else" /tmp/test_interactive.log
    fi
else
    echo "❌ FAILED: Interactive swap tests (timeout or error)"
    FAILED=$((FAILED + 1))
fi

# Test 3: Multi-requirement planning
echo ""
echo "▶️  TEST 3/4: Multi-Requirement Planning"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
if timeout 180 ./test_multi_requirement.sh > /tmp/test_multi.log 2>&1; then
    MEAL_COUNT=$(grep -c "^  •" /tmp/test_multi.log || echo "0")
    if [ "$MEAL_COUNT" -ge 5 ]; then
        echo "✅ PASSED: Multi-requirement planning ($MEAL_COUNT meals created)"
    else
        echo "❌ FAILED: Only $MEAL_COUNT meals created (expected 5)"
        FAILED=$((FAILED + 1))
        grep -A10 "CURRENT MEAL PLAN" /tmp/test_multi.log
    fi
else
    echo "❌ FAILED: Multi-requirement planning (timeout or error)"
    FAILED=$((FAILED + 1))
fi

# Test 4: Hybrid matching
echo ""
echo "▶️  TEST 4/4: Hybrid Matching"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
if timeout 180 ./test_hybrid_matching.sh > /tmp/test_hybrid.log 2>&1; then
    if grep -q "Matched.*via vague terms" /tmp/test_hybrid.log || \
       grep -q "Matched.*via direct match" /tmp/test_hybrid.log; then
        echo "✅ PASSED: Hybrid matching tests"
    else
        echo "❌ FAILED: No matching detected in verbose output"
        FAILED=$((FAILED + 1))
        grep "Matched" /tmp/test_hybrid.log
    fi
else
    echo "❌ FAILED: Hybrid matching tests (timeout or error)"
    FAILED=$((FAILED + 1))
fi

# Summary
echo ""
echo "========================================================================"
if [ $FAILED -eq 0 ]; then
    echo "✅ ALL TESTS PASSED ($((4 - FAILED))/4)"
    echo "========================================================================"
    echo ""
    echo "Safe to commit! All regression tests passing."
    exit 0
else
    echo "❌ SOME TESTS FAILED ($FAILED/4 failed, $((4 - FAILED))/4 passed)"
    echo "========================================================================"
    echo ""
    echo "⚠️  DO NOT COMMIT - Fix failing tests first!"
    echo ""
    echo "Test logs saved in /tmp/test_*.log for debugging."
    exit 1
fi
