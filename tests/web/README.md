# Web UI Tests (Playwright)

Automated browser tests for the Dinner Assistant web interface.

## Setup

### 1. Install Dependencies

Already installed if you ran the main setup:
```bash
pip install playwright pytest-playwright
```

### 2. Install Browser and System Dependencies

```bash
# Install Chromium browser
playwright install chromium

# Install system libraries (requires sudo)
sudo playwright install-deps
# OR manually:
sudo apt-get install libnspr4 libnss3 libgbm1 libasound2
```

### 3. Configure API Key

For tests that interact with the LLM (planning, swapping), ensure your `.env` file has:
```
ANTHROPIC_API_KEY=your-api-key-here
```

The Flask app auto-loads this file.

## Running Tests

### Quick Run (All Tests)
```bash
./run_web_tests.sh
```

### Manual Runs
```bash
# All web tests (headless mode)
pytest tests/web/test_plan_page.py -v -m web

# Specific test
pytest tests/web/test_plan_page.py::test_split_screen_layout -v

# With visible browser (headed mode + slowmo)
pytest tests/web/test_plan_page.py -v -m web --headed --slowmo=500

# Show print statements
pytest tests/web/test_plan_page.py -v -m web -s
```

## Test Cases

### 1. `test_split_screen_layout` ✓
**Purpose:** Verify the Plan page has correct split-screen layout

**Checks:**
- Split-screen container exists
- Chat column visible on left
- Plan column visible on right
- Chat input field present
- Send button present

**Duration:** ~4 seconds
**API Required:** No

---

### 2. `test_basic_planning_flow` ✓
**Purpose:** Test complete meal planning workflow

**Flow:**
1. Verify days are selected (all selected by default)
2. Type chat message: "plan 3 chicken dinners, no dairy"
3. Click send button
4. Wait for user message to appear
5. Wait for AI response (up to 60s)
6. Check if meals appear in plan column

**Duration:** ~60-90 seconds
**API Required:** Yes (degrades gracefully if missing)

**Note:** If API key isn't configured, test passes with warning message.

---

### 3. `test_verbose_output_visibility` ✓
**Purpose:** Verify tool execution details appear in chat

**Flow:**
1. Select Monday
2. Send: "plan 1 chicken dinner"
3. Wait for verbose messages (`.verbose-message` elements)
4. Verify at least one verbose message appeared

**Duration:** ~30 seconds
**API Required:** Yes (degrades gracefully if missing)

**Expected Verbose Output:**
- Tool execution messages (e.g., "🔧 [TOOL] search_recipes_smart")
- Monospace font styling
- Gray background with indigo border

---

### 4. `test_vague_swap_confirmation` ✓
**Purpose:** Test interactive swap confirmation workflow

**Flow:**
1. Create initial plan: "plan 1 dinner with chicken"
2. Wait for meal to appear
3. Request vague swap: "swap day 1 to something else"
4. Wait for 3 options to appear
5. Select option 1
6. Wait for swap to complete

**Duration:** ~90-120 seconds
**API Required:** Yes (degrades gracefully if missing)

**Note:** This test validates the interactive confirmation flow works end-to-end.

---

## Test Configuration

### Fixtures (tests/conftest.py)

**`flask_app` (session scope)**
- Starts Flask server in background on port 5000
- Waits 3 seconds for startup
- Yields base URL
- Auto-stops server after tests complete

**`browser_context_args` (function scope)**
- Sets viewport to 1920x1080
- Ignores HTTPS errors
- Enables slowmo for headed mode

**`browser_type_launch_args` (session scope)**
- Configures headless mode by default
- Adds Chrome flags for stability:
  - `--no-sandbox`
  - `--disable-setuid-sandbox`
  - `--disable-dev-shm-usage`
  - `--disable-gpu`

### Pytest Markers

Tests are marked with `@pytest.mark.web` to allow selective running:
```bash
# Run only web tests
pytest -m web

# Run all tests except web
pytest -m "not web"
```

## Troubleshooting

### Browser Launch Failed
**Error:** "Host system is missing dependencies to run browsers"

**Solution:**
```bash
sudo playwright install-deps
```

### Connection Refused
**Error:** "net::ERR_CONNECTION_REFUSED at http://localhost:5000/plan"

**Solution:** Flask server didn't start. Check:
1. Port 5000 not already in use: `lsof -i :5000`
2. Flask app runs manually: `python3 src/web/app.py`

### Tests Timeout
**Error:** "Timeout 60000ms exceeded"

**Causes:**
- API key not configured (`.env` file missing)
- Claude API rate limit reached
- Network connectivity issues

**Solution:** Tests will pass with warning messages. To get full functionality, ensure `.env` file exists with valid `ANTHROPIC_API_KEY`.

### No Meals Appear
**Warning:** "No meals created (expected at least 1)"

**Cause:** API returned response but didn't create meal plan

**Solution:**
1. Check Flask logs for errors
2. Verify database exists: `ls -lh data/recipes.db`
3. Test chatbot manually: `./run.sh chat`

## Continuous Integration

To run tests in CI:
```yaml
- name: Install Playwright dependencies
  run: |
    pip install playwright pytest-playwright
    playwright install chromium
    sudo playwright install-deps

- name: Run web tests
  run: pytest tests/web/ -v -m web
  env:
    ANTHROPIC_API_KEY: ${{ secrets.ANTHROPIC_API_KEY }}
```

## Performance

| Test | Duration | API Calls | Database Queries |
|------|----------|-----------|------------------|
| `test_split_screen_layout` | ~4s | 0 | 0 |
| `test_basic_planning_flow` | ~90s | 1-3 | ~10 |
| `test_verbose_output_visibility` | ~30s | 1 | ~5 |
| `test_vague_swap_confirmation` | ~120s | 2-4 | ~15 |

**Total:** ~4 minutes for full suite

## Future Enhancements

Potential additional tests:
- Shopping list generation
- Recipe detail modal
- Day selector toggling
- Error handling (invalid input)
- Mobile responsive layout
- Accessibility (ARIA labels, keyboard navigation)
- Performance metrics (page load, interaction latency)
