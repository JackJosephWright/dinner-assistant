#!/bin/bash
# Comprehensive demo of dinner-assistant chatbot features

cd ~/dinner-assistant

echo "========================================================================"
echo "🍽️  DINNER ASSISTANT - COMPREHENSIVE DEMO"
echo "========================================================================"
echo ""
echo "This demo showcases all the key features:"
echo ""
echo "  1. Multi-requirement planning"
echo "     → 'Plan 5 meals, one chicken, one beef, one thai'"
echo ""
echo "  2. Interactive vague swap (NEW!)"
echo "     → 'Swap day 2 to something else'"
echo "     → Bot shows 3 options, user picks one"
echo ""
echo "  3. Specific auto-swap"
echo "     → 'Swap day 3 to different chicken'"
echo "     → Instant swap, no confirmation needed"
echo ""
echo "  4. Verbose meal plan display"
echo "     → Shows current plan state after each operation"
echo ""
echo "========================================================================"
echo ""
echo "Starting demo in 3 seconds..."
sleep 3
echo ""

./chat.sh --verbose <<'EOF'
plan me 5 meals, one chicken, one beef, one thai
swap day 2 to something else
1
swap day 3 to different chicken
show me the current plan
quit
EOF

echo ""
echo "========================================================================"
echo "✅ DEMO COMPLETE"
echo "========================================================================"
echo ""
echo "What you just saw:"
echo "  ✅ Created 5-meal plan with specific requirements"
echo "  ✅ Vague swap showed 3 options for user to choose"
echo "  ✅ User selected option 1"
echo "  ✅ Specific swap auto-swapped without confirmation"
echo "  ✅ Meal plan state displayed throughout"
echo ""
echo "All operations completed in milliseconds using backup queue!"
echo ""
