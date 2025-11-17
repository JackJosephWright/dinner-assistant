#!/bin/bash
# Test suite for day/meal interpretation in swaps
# Ensures prompt updates don't break date parsing

cd ~/dinner-assistant

echo "========================================================================"
echo "🧪 TESTING DAY INTERPRETATION (REGRESSION TESTS)"
echo "========================================================================"
echo ""
echo "These tests ensure the LLM correctly interprets user day references:"
echo "  Test 1: 'swap day 3' → should swap 3rd meal (not November 3rd)"
echo "  Test 2: 'swap Monday' → should swap Monday's meal"
echo "  Test 3: 'swap the chicken' → should swap the chicken meal"
echo ""
echo "Expected behavior:"
echo "  ✅ 'day 3' maps to 3rd meal in plan (index 2)"
echo "  ✅ 'Monday' finds Monday's date in the plan"
echo "  ✅ 'the chicken' finds which meal has chicken"
echo ""
echo "========================================================================"
echo ""

# Test 1: Relative day numbers
echo "TEST 1: Relative day numbers (swap day 3)"
echo "=========================================="
./chat.sh --verbose <<'EOF' 2>&1 | grep -A3 "swap_meal_fast" | grep "date"
plan me 5 meals
swap day 3 to something else
quit
EOF

echo ""
echo "Expected: date should be the 3rd meal's date (2025-11-02 if plan starts 2025-10-31)"
echo ""

# Test 2: Day name references
echo "TEST 2: Day name references (swap Monday)"
echo "=========================================="
./chat.sh --verbose <<'EOF' 2>&1 | grep -A3 "swap_meal_fast" | grep "date"
plan me 5 meals
swap Monday to different chicken
quit
EOF

echo ""
echo "Expected: date should be Monday's date from the plan"
echo ""

# Test 3: Recipe-based references
echo "TEST 3: Recipe-based references (swap the chicken meal)"
echo "=========================================="
./chat.sh --verbose <<'EOF' 2>&1 | grep -A3 "swap_meal_fast" | grep "date"
plan me 3 meals with chicken
swap the chicken and petite carrots to different chicken
quit
EOF

echo ""
echo "Expected: date should be the date of the 'Chicken and Petite Carrots' meal"
echo ""

echo "========================================================================"
echo "✅ TEST SUITE COMPLETE"
echo "========================================================================"
echo ""
echo "Review the 'date' values above to ensure correct interpretation."
echo "If any test shows November 3rd (2025-11-03) instead of the 3rd meal,"
echo "the prompt regression has occurred!"
echo ""
