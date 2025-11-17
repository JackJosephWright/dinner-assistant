#!/bin/bash
# Test multi-requirement planning with the new improvements

cd ~/dinner-assistant

echo "========================================================================"
echo "🧪 TESTING MULTI-REQUIREMENT PLANNING IMPROVEMENTS"
echo "========================================================================"
echo ""
echo "Testing: 'plan me 5 meals, i want one to be ramen and one to be spaghetti and meatballs'"
echo ""
echo "Expected behavior:"
echo "  ✅ Should use plan_meals_smart with broad search (e.g., 'dinner')"
echo "  ✅ LLM selector should see user requirements"
echo "  ✅ Should complete in 2-3 LLM calls (not 9)"
echo "  ✅ Should NOT create generic plan + 5 swaps"
echo ""
echo "========================================================================"
echo ""

./chat.sh --verbose <<'EOF'
plan me 5 meals, i want one to be ramen and one to be spaghetti and meatballs
quit
EOF
