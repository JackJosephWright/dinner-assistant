#!/bin/bash
#
# Performance Test Runner
#
# Runs performance tests against the live Flask application and generates reports.
#

set -e  # Exit on error

# Colors for output
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

echo "======================================================================"
echo "  MEAL PLANNING ASSISTANT - PERFORMANCE TEST SUITE"
echo "======================================================================"
echo ""

# Check if Flask app is running
echo -n "Checking if Flask app is running on localhost:5000... "
if curl -s -f http://localhost:5000/plan > /dev/null 2>&1; then
    echo -e "${GREEN}✓ Running${NC}"
else
    echo -e "${RED}✗ Not running${NC}"
    echo ""
    echo "Please start the Flask app first:"
    echo "  python3 src/web/app.py"
    exit 1
fi

# Install dependencies if needed
if ! python3 -c "import pytest_benchmark" 2>/dev/null; then
    echo ""
    echo "Installing test dependencies..."
    pip install -q pytest-benchmark pytest-timeout pytest-flask
fi

echo ""
echo "Running performance tests..."
echo ""

# Run performance tests with verbose output
pytest tests/performance/ \
    -v \
    -s \
    --tb=short \
    --durations=10 \
    -m "performance or benchmark" \
    "$@"

TEST_EXIT_CODE=$?

echo ""
echo "======================================================================"

if [ $TEST_EXIT_CODE -eq 0 ]; then
    echo -e "${GREEN}✓ All performance tests passed!${NC}"
else
    echo -e "${RED}✗ Some tests failed (exit code: $TEST_EXIT_CODE)${NC}"
fi

echo "======================================================================"

exit $TEST_EXIT_CODE
