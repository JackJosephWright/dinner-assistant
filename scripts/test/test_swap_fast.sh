#!/bin/bash
# Test script for swap_meal_fast functionality

cd ~/dinner-assistant

# Test 1: Create a plan and swap a meal
./chat.sh --verbose <<'EOF'
Plan 3 days with chicken, no dairy
Show me the current plan
Swap the meal on the first day with a different chicken dish
quit
EOF
