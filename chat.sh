#!/bin/bash
# Launch the meal planning chat interface

# Check if API key is set
if [ -z "$ANTHROPIC_API_KEY" ]; then
    echo "❌ Error: ANTHROPIC_API_KEY not set"
    echo ""
    echo "Set your API key first:"
    echo "  export ANTHROPIC_API_KEY='your-key-here'"
    echo ""
    echo "Or load from .env:"
    echo "  source .env"
    exit 1
fi

# Run chatbot directly (like main.py, uses relative imports)
python3 src/chatbot.py "$@"
