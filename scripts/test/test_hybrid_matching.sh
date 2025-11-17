#!/bin/bash
# Test hybrid backup matching with vague requests

cd ~/dinner-assistant

echo "========================================================================"
echo "🧪 TESTING HYBRID BACKUP MATCHING"
echo "========================================================================"
echo ""
echo "Testing vague swap requests that should use backup queue:"
echo "  1. 'something else, no corned beef'"
echo "  2. 'swap to something different'"
echo "  3. 'give me anything else'"
echo ""
echo "Expected behavior:"
echo "  ✅ Should match backup category via vague terms (algorithmic)"
echo "  ✅ Should use backup queue (not fresh search)"
echo "  ✅ Should complete swap in <10ms"
echo ""
echo "========================================================================"
echo ""

./chat.sh --verbose <<'EOF'
plan me 3 meals with chicken
swap the second day to something else, no corned beef
quit
EOF
