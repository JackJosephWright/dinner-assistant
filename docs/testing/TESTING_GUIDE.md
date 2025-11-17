# Testing Guide

## Performance Testing Suite - Quick Start

### What You Got

A complete performance testing system that:
- **Operates your live web app** via HTTP requests
- **Tracks backend metrics** (LLM calls, DB queries, timing)
- **Detects bottlenecks** and duplicate work automatically
- **Generates detailed reports** with actionable insights

### Files Created

```
tests/performance/
├── __init__.py
├── README.md                      # Detailed docs
├── instrumentation.py             # Monitoring infrastructure
└── test_web_performance.py        # Main test suite

scripts/test/run_performance_tests.sh           # Convenient test runner
pytest.ini                         # Updated with performance markers
requirements.txt                   # Updated with test deps
```

### How to Run

#### 1. Start Your Web App
```bash
python3 src/web/app.py
```

#### 2. Run Performance Tests
```bash
# Easy way
./scripts/test/run_performance_tests.sh

# Or with pytest directly
pytest tests/performance/ -v -s -m performance
```

### What It Tests

1. **Complete Meal Planning Workflow**
   - Onboarding
   - Meal planning via chat
   - Fetching plan data
   - Preloading shop/cook
   - **Tracks**: LLM calls, DB queries, duplicates, timing

2. **Shopping List Performance**
   - Generation speed
   - Caching effectiveness
   - Duplicate detection

3. **Page Load Times**
   - Home, plan, shop, cook pages
   - Enriched data validation (N+1 fix)

4. **Concurrent Request Handling**
   - Simulates multiple tabs/users
   - Detects race conditions

### Example Output

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

⏱️  Complete Meal Planning Workflow completed in 32.45s

⚠️  DUPLICATES DETECTED:
  - HTTP: POST /api/shop (5 times)
```

### Quick Commands

```bash
# Run just one test
pytest tests/performance/test_web_performance.py::TestWebPerformance::test_complete_meal_planning_workflow -v -s

# Run with longer timeout
pytest tests/performance/ --timeout=600

# Generate HTML report
pytest tests/performance/ --html=report.html

# Run benchmarks
pytest tests/performance/ -m benchmark
```

### Finding Bottlenecks

The tests automatically identify:

🔴 **Critical:**
- Operations taking >60s
- Duplicate API calls ($$$ waste)
- N+1 database queries

🟡 **Medium:**
- LLM calls >10s each
- >5 LLM calls for simple ops
- DB queries >100ms

### Before/After Comparison

```bash
# Before optimization
./scripts/test/run_performance_tests.sh > baseline.txt

# After optimization
./scripts/test/run_performance_tests.sh > optimized.txt

# Compare
diff baseline.txt optimized.txt
```

### Integration with Development

1. **Run before making changes** - establish baseline
2. **Make optimizations** - implement improvements
3. **Run after changes** - measure improvement
4. **Check for regressions** - ensure no slowdowns

### Customization

Edit `tests/performance/test_web_performance.py` to:
- Add new workflow tests
- Adjust timing assertions
- Test specific features

Use the `PerformanceTestContext` for any test:

```python
from tests.performance.instrumentation import PerformanceTestContext

def test_my_feature():
    with PerformanceTestContext("My Feature") as ctx:
        # Your test code here
        response = client.get("/my-endpoint")

    # Auto-generates performance report
```

### Next Steps

1. **Run the tests now** to establish your baseline
2. **Review the output** to see current performance
3. **Identify bottlenecks** from the reports
4. **Implement Phase 1 optimizations** from `PERFORMANCE_OPTIMIZATION.md`
5. **Re-run tests** to measure improvement

### Troubleshooting

**"Connection refused"**
- Flask app isn't running
- Check with: `curl http://localhost:5000/plan`

**Tests timing out**
- Use `--timeout=600` flag
- Check Flask logs for errors

**Import errors**
- Install deps: `pip install -r requirements.txt`

### Related Documents

- `tests/performance/README.md` - Detailed testing docs
- `PERFORMANCE_OPTIMIZATION.md` - Optimization strategies
- `test_webapp.py` - Basic webapp tests (simpler, no instrumentation)

---

## Other Test Suites

### Unit Tests
```bash
pytest tests/unit/ -v
```

### Integration Tests
```bash
pytest tests/integration/ -v
```

### E2E Tests
```bash
pytest tests/e2e/ -v
```

### All Tests
```bash
pytest tests/ -v
```

---

**Happy Testing!** 🧪
