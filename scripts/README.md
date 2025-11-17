# Scripts Directory

This directory contains utility scripts for testing, demos, and development.

## Directory Structure

```
scripts/
├── test/          # Test and validation scripts
└── demo/          # Demo and example scripts
```

## Test Scripts (`scripts/test/`)

Scripts for testing various functionality. Run from project root.

### Test Runners

- **`run_all_tests.sh`** - Run complete test suite (unit + integration + e2e)
- **`run_web_tests.sh`** - Run web/Flask tests with Playwright
- **`run_performance_tests.sh`** - Run performance benchmarks

### Feature Tests

- **`test_swap_fast.sh`** - Test fast meal swap with incremental shopping list update
- **`test_interactive_swap.sh`** - Test swap via interactive mode
- **`test_day_interpretation.sh`** - Test day/meal reference parsing
- **`test_hybrid_matching.sh`** - Test hybrid backup matching
- **`test_multi_requirement.sh`** - Test multi-requirement planning
- **`test_interactive.sh`** - Test interactive mode
- **`interactive_test.sh`** - Interactive test harness

### Usage

All test scripts should be run from the project root:

```bash
# From project root
cd /home/jack_wright/dinner-assistant

# Run specific test
./scripts/test/test_swap_fast.sh

# Run all tests
./scripts/test/run_all_tests.sh

# Run web tests
./scripts/test/run_web_tests.sh

# Run performance tests
./scripts/test/run_performance_tests.sh
```

## Demo Scripts (`scripts/demo/`)

Demonstration scripts showing system capabilities.

- **`demo.sh`** - Comprehensive end-to-end demo
- **`demo_meal_plan_workflow.py`** - Python demo of meal plan workflow with embedded recipes

### Usage

```bash
# Shell demo
./scripts/demo/demo.sh

# Python workflow demo
python3 scripts/demo/demo_meal_plan_workflow.py
```

## Notes

- All scripts are designed to be run from the project root directory
- Test scripts use temporary databases and don't affect production data
- Make sure you have all dependencies installed: `pip install -r requirements-dev.txt`
- Some tests require `ANTHROPIC_API_KEY` environment variable

## Contributing

When adding new scripts:

1. Place in appropriate subdirectory (`test/` or `demo/`)
2. Make executable: `chmod +x scripts/test/your_script.sh`
3. Add documentation to this README
4. Follow existing naming conventions
5. Include comments explaining what the script does

## See Also

- [tests/README.md](../tests/README.md) - Automated test suite documentation
- [docs/testing/TESTING_GUIDE.md](../docs/testing/TESTING_GUIDE.md) - Full testing guide
- [docs/testing/TEST_SUITE.md](../docs/testing/TEST_SUITE.md) - Detailed test descriptions
