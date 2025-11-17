#!/bin/bash
# Run Playwright web UI tests for the Plan page
# This script starts the Flask server and runs the tests in headed mode

set -e  # Exit on error

cd ~/dinner-assistant

echo "======================================"
echo "Dinner Assistant - Web UI Test Runner"
echo "======================================"
echo ""

# Check for ANTHROPIC_API_KEY
if [ -n "$ANTHROPIC_API_KEY" ]; then
    echo "✓ API key IS set in environment"
else
    echo "✗ API key NOT set in environment"
    echo "Loading from .env file..."
    if [ -f .env ]; then
        export $(grep -v '^#' .env | xargs)
        echo "✓ Loaded .env file"
    else
        echo "⚠ Warning: No .env file found. Tests may fail without API key."
    fi
fi

echo ""
echo "Checking for existing Flask server on port 5000..."
EXISTING_PID=$(lsof -ti:5000 2>/dev/null)
if [ -n "$EXISTING_PID" ]; then
    echo "Found Flask running (PID: $EXISTING_PID). Stopping it..."
    kill -9 $EXISTING_PID 2>/dev/null || true
    sleep 1
    echo "✓ Stopped existing Flask server"
fi

echo "Starting Flask server in background..."
python3 src/web/app.py &
FLASK_PID=$!
echo "Flask PID: $FLASK_PID"

# Wait for server to start
echo "Waiting for Flask to start..."
sleep 3

# Check if server is running
if ! kill -0 $FLASK_PID 2>/dev/null; then
    echo "✗ Error: Flask server failed to start"
    exit 1
fi

echo "✓ Flask server running"
echo ""

# Open browser to view the page
echo "Opening browser to http://localhost:5000/plan ..."
if command -v xdg-open > /dev/null; then
    xdg-open "http://localhost:5000/plan" &
elif command -v wslview > /dev/null; then
    wslview "http://localhost:5000/plan" &
else
    echo "⚠ Could not auto-open browser. Please open http://localhost:5000/plan manually."
fi
sleep 2

# Run tests
echo "Running Playwright tests (headed mode with 500ms slowmo)..."
echo "Press Ctrl+C to stop tests"
echo ""

# Run with headed mode and slowmo for visibility
pytest tests/web/test_plan_page.py -v -m web --headed --slowmo=500 || TEST_EXIT_CODE=$?

echo ""
echo "Stopping Flask server..."
kill $FLASK_PID 2>/dev/null || true
wait $FLASK_PID 2>/dev/null || true

echo "✓ Flask server stopped"
echo ""

if [ "${TEST_EXIT_CODE:-0}" -eq 0 ]; then
    echo "======================================"
    echo "✓ All tests passed!"
    echo "======================================"
else
    echo "======================================"
    echo "✗ Some tests failed (exit code: ${TEST_EXIT_CODE})"
    echo "======================================"
    exit ${TEST_EXIT_CODE}
fi
