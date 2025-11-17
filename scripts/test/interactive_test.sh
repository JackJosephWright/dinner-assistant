#!/bin/bash
# Interactive test script that shows meal plan state

cd ~/dinner-assistant

echo "========================================================================"
echo "🍽️  INTERACTIVE MEAL PLANNING TEST"
echo "========================================================================"
echo ""
echo "This will start the chatbot in verbose mode."
echo "After each interaction, you can see the cached meal plan state."
echo ""
echo "Try these commands:"
echo "  - Plan 3 days with chicken, no dairy"
echo "  - Show me the current plan"
echo "  - Does my plan have any shellfish?"
echo "  - Swap the first day with a different chicken dish"
echo ""
echo "Type 'quit' to exit"
echo ""
echo "========================================================================"
echo ""

./chat.sh --verbose
