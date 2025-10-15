# Performance Testing Suite

This directory contains performance tests that operate your live web application and monitor backend behavior in real-time.

## What It Does

The performance test suite:
- **Operates the live website** via HTTP requests
- **Tracks backend metrics** (LLM calls, database queries, timing)
- **Detects bottlenecks** automatically
- **Identifies duplicate/redundant work** (like the shopping list bug)
- **Measures end-to-end performance**
- **Generates detailed reports**

## Quick Start

### 1. Start the Flask App

```bash
# From project root
python3 src/web/app.py
```

The app must be running on `http://localhost:5000` for tests to work.

### 2. Run Performance Tests

```bash
# Simple way (uses script)
./run_performance_tests.sh

# Or directly with pytest
pytest tests/performance/ -v -s -m performance
```

## Test Suite Overview

### `test_web_performance.py`
Main test file that simulates real user workflows:

- **`test_complete_meal_planning_workflow`** - Full journey:
  - Onboarding
  - Meal planning via chat
  - Fetching plan
  - Preloading shop/cook data
  - Tracks timing at each step
  - Detects duplicate requests

- **`test_shopping_list_generation_performance`** - Shopping list speed test

- **`test_shop_page_load_speed`** - Tests preload optimization

- **`test_concurrent_request_handling`** - Simulates multiple users/tabs

### `instrumentation.py`
Backend monitoring infrastructure:

- `PerformanceMonitor` - Tracks all metrics
- `PerformanceTestContext` - Context manager for test runs
- `track_llm_calls()` - Wraps Anthropic client
- `track_database_queries()` - Wraps database interface
- `detect_duplicate_requests()` - Finds redundant work

## Example Output

```
======================================================================
          Complete Meal Planning Workflow - Performance Report
======================================================================

🤖 LLM API Calls:
  Count: 4
  Total time: 24.32s
  Average time: 6.08s
  Cache hit rate: 0.0%

💾 Database Queries:
  Count: 12
  Total time: 1.45s
  Average time: 0.121s

🌐 HTTP Requests:
  Count: 8
  Total time: 32.18s

📊 LLM Call Breakdown:
  1. claude-sonnet-4-5 - 3.21s
  2. claude-sonnet-4-5 - 5.43s
  3. claude-sonnet-4-5 - 7.12s
  4. claude-sonnet-4-5 - 8.56s

⚠️  DUPLICATES DETECTED:
  - HTTP: POST /api/shop (5 times)
  - DATABASE: search_recipes(query=chicken) (3 times)
```

## Running Specific Tests

```bash
# Run just the workflow test
pytest tests/performance/test_web_performance.py::TestWebPerformance::test_complete_meal_planning_workflow -v -s

# Run benchmarks only
pytest tests/performance/ -m benchmark

# Run with timeout (useful for slow tests)
pytest tests/performance/ --timeout=300
```

## Using Instrumentation in Your Own Tests

```python
from tests.performance.instrumentation import PerformanceTestContext

def test_my_feature():
    with PerformanceTestContext("My Feature Test") as ctx:
        # Do your testing
        response = client.get("/my-endpoint")

        # Context automatically tracks timing and prints report

    # Optionally check metrics
    metrics = ctx.get_metrics()
    assert metrics.summary()['llm_calls']['count'] < 5
```

## Detecting Performance Regressions

### Before Making Changes
```bash
# Run baseline
./run_performance_tests.sh > baseline_results.txt
```

### After Making Changes
```bash
# Run again
./run_performance_tests.sh > optimized_results.txt

# Compare
diff baseline_results.txt optimized_results.txt
```

## Integration with CI/CD

Add to your GitHub Actions workflow:

```yaml
- name: Run Performance Tests
  run: |
    python3 src/web/app.py &
    sleep 5  # Wait for server to start
    ./run_performance_tests.sh
```

## Configuration

Edit `pytest.ini` to adjust:
- Test timeouts
- Performance baselines
- Report verbosity

## Troubleshooting

### "Connection refused" errors
- Make sure Flask app is running on port 5000
- Check with: `curl http://localhost:5000/plan`

### Tests timing out
- Increase timeout: `pytest --timeout=600`
- Check backend logs for slow operations

### Missing dependencies
```bash
pip install -r requirements.txt
```

## Advanced Usage

### Parallel Execution
```bash
# Run tests in parallel (careful with Flask app state)
pytest tests/performance/ -n 4
```

### Generate HTML Report
```bash
pytest tests/performance/ --html=performance_report.html
```

### Benchmark Comparison
```bash
# Save benchmark results
pytest tests/performance/ --benchmark-save=before

# After changes
pytest tests/performance/ --benchmark-save=after --benchmark-compare=before
```

## What to Look For

🔴 **Critical Issues:**
- Requests taking >60s
- Duplicate API calls (wasted $$$)
- N+1 database queries
- Cache not working

🟡 **Medium Issues:**
- LLM calls taking >10s each
- More than 5 LLM calls for simple operations
- Database queries >100ms

🟢 **Good Performance:**
- Meal planning: 30-45s
- Shopping list (cached): <5s
- Page loads: <1s
- Cache hit rate: >50%

## Contributing

When adding new features, add performance tests:

1. Create test in `test_web_performance.py`
2. Use `PerformanceTestContext` to track metrics
3. Set reasonable assertions for timing
4. Document expected performance in docstring

## Related Files

- `PERFORMANCE_OPTIMIZATION.md` - Optimization strategies
- `test_webapp.py` - Basic webapp tests (no instrumentation)
- `run_performance_tests.sh` - Test runner script
