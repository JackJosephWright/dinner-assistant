#!/bin/bash
# Convenience script to run the Meal Planning Assistant

# Use python3 explicitly
PYTHON="python3"

# Show usage if no command
if [ $# -eq 0 ]; then
    echo "Meal Planning Assistant"
    echo "======================="
    echo ""
    echo "Usage: ./run.sh <command>"
    echo ""
    echo "Commands:"
    echo "  chat              - 🤖 AI Chatbot (LLM-powered, requires API key)"
    echo "  interactive       - 📝 Interactive mode (command-based)"
    echo "  workflow          - Run complete plan → shop → cook workflow"
    echo "  plan              - Generate meal plan for next week"
    echo "  shop <plan-id>    - Create shopping list from meal plan"
    echo "  cook <recipe-id>  - Get cooking guide for a recipe"
    echo "  test              - Run all tests"
    echo "  explore           - Explore recipes interactively"
    echo ""
    echo "Examples:"
    echo "  ./run.sh interactive    # Chat-style interface (recommended!)"
    echo "  ./run.sh workflow       # Quick one-shot planning"
    echo "  ./run.sh plan           # Just plan meals"
    echo "  ./run.sh test           # Run tests"
    echo ""
    exit 0
fi

# Handle commands
case "$1" in
    chat|c)
        $PYTHON src/chatbot.py
        ;;
    interactive|i)
        $PYTHON src/interactive.py
        ;;
    workflow)
        $PYTHON src/main.py workflow
        ;;
    plan)
        $PYTHON src/main.py plan "${@:2}"
        ;;
    shop)
        if [ -z "$2" ]; then
            echo "Error: meal-plan-id required"
            echo "Usage: ./run.sh shop <meal-plan-id>"
            exit 1
        fi
        $PYTHON src/main.py shop --meal-plan-id "$2"
        ;;
    cook)
        if [ -z "$2" ]; then
            echo "Error: recipe-id required"
            echo "Usage: ./run.sh cook <recipe-id>"
            exit 1
        fi
        $PYTHON src/main.py cook --recipe-id "$2"
        ;;
    test)
        echo "Running all tests..."
        echo ""
        $PYTHON tests/test_vertical_slice.py && \
        $PYTHON tests/test_planning.py && \
        $PYTHON tests/test_integration.py
        ;;
    explore)
        $PYTHON examples/explore_recipes.py
        ;;
    *)
        echo "Unknown command: $1"
        echo "Run './run.sh' for usage"
        exit 1
        ;;
esac
