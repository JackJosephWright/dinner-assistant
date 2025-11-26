#!/bin/bash
# Test runner for dinner-assistant
# Usage: ./test.sh [fast|full|web|file]

set -e

case "${1:-fast}" in
    fast)
        echo "=== Running FAST tests (unit only, skipping known-broken) ==="
        pytest tests/unit/ -v --timeout=30 \
            --ignore=tests/unit/test_chatbot_cache.py \
            --ignore=tests/unit/test_contributions.py
        ;;
    full)
        echo "=== Running FULL test suite ==="
        echo ""
        echo "--- Unit tests ---"
        pytest tests/unit/ -v --timeout=30
        echo ""
        echo "--- Integration tests ---"
        pytest tests/integration/ -v --timeout=60
        ;;
    web)
        echo "=== Running WEB tests (requires server) ==="
        echo "Starting server and running Playwright tests..."
        python /home/jack_wright/.claude/plugins/marketplaces/anthropic-agent-skills/webapp-testing/scripts/with_server.py \
            --server "source .env && python3 src/web/app.py" --port 5000 \
            -- python tests/integration/test_webapp_integration.py
        ;;
    coverage)
        echo "=== Running tests with COVERAGE ==="
        pytest tests/unit/ --cov=src --cov-report=term-missing --cov-report=html
        echo ""
        echo "Coverage report: htmlcov/index.html"
        ;;
    *)
        # Run specific test file
        echo "=== Running specific test: $1 ==="
        pytest "$1" -v
        ;;
esac

echo ""
echo "✅ Tests passed!"
