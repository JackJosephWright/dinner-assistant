#!/bin/bash
# Test interactive swap confirmation flow

cd ~/dinner-assistant

echo "========================================================================"
echo "🧪 TESTING INTERACTIVE SWAP CONFIRMATION"
echo "========================================================================"
echo ""
echo "Testing vague swap request that should show options:"
echo "  1. Plan 3 meals with chicken"
echo "  2. User: 'swap day 2 to something else' (vague request)"
echo "  3. Bot should show 3 options"
echo "  4. User picks option 1"
echo ""
echo "Expected behavior:"
echo "  ✅ Bot shows 3 backup recipe options"
echo "  ✅ User can pick by number (1, 2, 3)"
echo "  ✅ Swap completes in <10ms using backup queue"
echo "  ✅ Specific requests like 'different chicken' still auto-swap"
echo ""
echo "========================================================================"
echo ""

./chat.sh --verbose <<'EOF'
plan me 3 meals with chicken
swap day 2 to something else
1
quit
EOF
