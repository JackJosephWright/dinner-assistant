#!/bin/bash
# Test interactive mode with automated input

echo "Testing interactive mode..."
echo ""

# Send commands to interactive mode
{
    echo "help"
    sleep 1
    echo "stats"
    sleep 1
    echo "history"
    sleep 1
    echo "search chicken"
    sleep 1
    echo "quit"
} | python3 src/interactive.py
