# Project Roadmap

**Last Updated**: October 13, 2025

---

## ✅ Phase 1: Meal Events System (COMPLETE)

### Completed Items

✅ **Design and Architecture**
- Design document (MEAL_EVENTS_DESIGN.md)
- Data models for MealEvent and UserProfile
- Database schema with tables and indexes

✅ **Core Implementation**
- Models: MealEvent, UserProfile classes
- Database: CRUD operations, analytics queries
- Onboarding: 6-step conversational flow
- Agent Integration: Planning tools updated
- Migration: Database migration script

✅ **Testing Framework**
- pytest setup and configuration
- 39 unit tests (models + database)
- Test fixtures and documentation
- Code coverage reporting (92% models, 57% database)

**Status**: All systems ready for use!

---

## 🔄 Phase 2: Integration & User Experience (IN PROGRESS)

### High Priority

#### 1. Run Database Migration
**Status**: Ready to run
**Time**: 5 minutes
**Action**:
```bash
python3 scripts/migrate_database.py
```

#### 2. Integrate Onboarding into Chatbot
**Status**: Not started
**Effort**: Medium (2-3 hours)
**Tasks**:
- Add onboarding check on chatbot startup
- Integrate OnboardingFlow into chat loop
- Handle onboarding state transitions
- Test complete onboarding workflow

**Files to modify**:
- `src/chatbot.py` - Add onboarding check and flow

#### 3. Update Cooking Agent to Write Events
**Status**: Not started
**Effort**: Medium (2-3 hours)
**Tasks**:
- Update meal_events when user cooks
- Capture modifications and substitutions
- Record actual cooking time
- Add feedback prompts

**Files to modify**:
- `src/agents/cooking_agent.py` or `src/agents/agentic_cooking_agent.py`
- Add `update_meal_event()` calls

#### 4. Update Shopping Agent to Learn
**Status**: Not started
**Effort**: Medium (2-3 hours)
**Tasks**:
- Query meal_events for common ingredients
- Adjust quantities based on servings_actual
- Remember modification patterns
- Optimize shopping lists

**Files to modify**:
- `src/agents/shopping_agent.py` or `src/agents/agentic_shopping_agent.py`
- `src/mcp_server/tools/shopping_tools.py`

### Medium Priority

#### 5. Complete Testing Suite
**Status**: 39/~100 tests complete
**Effort**: Large (1-2 days)
**Tasks**:
- Unit tests for onboarding.py (10-15 tests)
- Integration tests for planning_tools.py (8-10 tests)
- Integration tests for agent workflows (5-8 tests)
- End-to-end test: complete meal planning (3-5 tests)

**Files to create**:
- `tests/unit/test_onboarding.py`
- `tests/integration/test_planning_tools.py`
- `tests/e2e/test_meal_planning_workflow.py`

#### 6. Post-Meal Feedback Collection
**Status**: Not started
**Effort**: Medium (2-3 hours)
**Tasks**:
- Add chatbot prompts after meals
- "How was the [recipe name]?"
- Capture ratings, notes, would_make_again
- Update meal_events with feedback

**Files to modify**:
- `src/chatbot.py` - Add feedback loop
- May need new conversation state

### Low Priority

#### 7. Analytics Dashboard (Optional)
**Status**: Not started
**Effort**: Large (2-3 days)
**Tasks**:
- Most popular recipes view
- Cuisine frequency charts
- Ingredient usage patterns
- Success rate tracking
- Weekly/monthly trends

**New files needed**:
- `src/analytics.py` - Query and visualization logic
- Could be CLI or simple web dashboard

---

## 🎯 Phase 3: Production Readiness (PLANNED)

### Infrastructure

#### 1. CI/CD Pipeline
**Status**: Not started
**Effort**: Medium (3-4 hours)
**Tasks**:
- GitHub Actions workflow
- Run tests on every push/PR
- Code coverage reporting
- Automated deployment (if needed)

**File to create**:
- `.github/workflows/test.yml`

#### 2. Configuration Management
**Status**: Not started
**Effort**: Small (1-2 hours)
**Tasks**:
- Environment-based config
- Separate dev/test/prod settings
- Secrets management

**Files to create**:
- `config/development.yaml`
- `config/production.yaml`
- Update `.env` handling

#### 3. Logging and Monitoring
**Status**: Basic logging exists
**Effort**: Medium (2-3 hours)
**Tasks**:
- Structured logging
- Log levels per environment
- Error tracking (Sentry?)
- Performance monitoring

**Files to modify**:
- All agent files
- Add logging framework

### Code Quality

#### 4. Type Hints and Validation
**Status**: Partial
**Effort**: Medium (2-3 hours)
**Tasks**:
- Add type hints to all functions
- Run mypy for type checking
- Add Pydantic for validation

#### 5. Code Documentation
**Status**: Partial
**Effort**: Medium (2-3 hours)
**Tasks**:
- Complete docstrings
- API documentation
- Architecture diagrams
- Setup guide

### Performance

#### 6. Performance Optimization
**Status**: Not started
**Effort**: Medium (2-3 hours)
**Tasks**:
- Profile database queries
- Add caching where appropriate
- Optimize recipe search
- Batch operations

#### 7. Scalability Testing
**Status**: Not started
**Effort**: Medium (2-3 hours)
**Tasks**:
- Test with 1000+ recipes
- Test with 1000+ meal events
- Test concurrent operations
- Memory profiling

---

## 🚀 Phase 4: Feature Enhancements (FUTURE)

### User Experience

#### 1. Multi-User Support
**Status**: Not planned yet
**Effort**: Large
**Tasks**:
- Multiple user profiles
- User authentication
- Per-user preferences
- Shared meal plans (families)

#### 2. Recipe Customization
**Status**: Not planned yet
**Effort**: Medium
**Tasks**:
- User-created recipes
- Recipe notes/modifications
- Recipe sharing
- Recipe import from URLs

#### 3. Advanced Meal Planning
**Status**: Not planned yet
**Effort**: Large
**Tasks**:
- Meal prep optimization
- Leftover management
- Batch cooking suggestions
- Weekly themes

### Agent Improvements

#### 4. LLM Model Flexibility
**Status**: Not planned yet
**Effort**: Medium
**Tasks**:
- Support multiple LLM providers
- Model selection per agent
- Cost optimization
- Fallback models

#### 5. Agent Memory and Context
**Status**: Not planned yet
**Effort**: Large
**Tasks**:
- Long-term conversation memory
- Context window management
- User preference learning
- Adaptive recommendations

### Integration

#### 6. External Integrations
**Status**: Not planned yet
**Effort**: Large
**Tasks**:
- Grocery delivery APIs
- Recipe websites (scraping)
- Nutrition databases
- Calendar integration

---

## 📊 Current Status Summary

### What Works Right Now

✅ **Core Data Layer**
- MealEvent and UserProfile models
- Full database CRUD operations
- Rich meal tracking

✅ **Planning Agent**
- Reads user_profile for preferences
- Reads meal_events for history
- Automatically creates meal_events

✅ **Onboarding**
- 6-step conversational flow
- Natural language parsing
- Profile creation

✅ **Testing**
- 39 unit tests passing
- Coverage reporting
- Test fixtures

### What Needs Work

⏳ **Integration**
- Onboarding not integrated into chatbot
- Cooking agent doesn't update events
- Shopping agent doesn't learn from events

⏳ **Testing**
- 39/~100 tests complete
- No integration tests yet
- No e2e tests yet

⏳ **User Experience**
- No feedback collection
- No analytics/reporting
- Manual migration required

---

## 🎯 Recommended Next Steps

### Option A: Quick Integration (2-3 hours)
Focus on getting the system working end-to-end:

1. Run database migration
2. Integrate onboarding into chatbot
3. Test complete workflow manually
4. Deploy to "production" (your environment)

**Result**: System is usable with all new features active

### Option B: Testing First (1-2 days)
Focus on test coverage before adding more features:

1. Complete unit tests for onboarding
2. Add integration tests for planning tools
3. Add e2e test for meal planning workflow
4. Run database migration
5. Integrate onboarding into chatbot

**Result**: High confidence, well-tested system

### Option C: Agent Updates (3-4 hours)
Focus on making all agents learn from meal_events:

1. Run database migration
2. Update cooking agent to write events
3. Update shopping agent to learn from events
4. Add feedback collection
5. Test complete learning cycle

**Result**: Full intelligent agent system

---

## 💭 My Recommendation

Start with **Option A** (Quick Integration):

1. **Run migration** (5 min)
2. **Integrate onboarding** (2-3 hours)
3. **Test workflow** (30 min)

This gets the system working end-to-end so you can:
- See the onboarding flow in action
- Start collecting meal_events automatically
- Validate the design with real usage

Then move to **Option C** (Agent Updates) to complete the learning cycle.

**Option B** (Testing) can happen in parallel or after - tests are important but don't block usage.

---

## 📝 Decision Points

### Before Moving Forward

**Question 1**: Do you want to start using the system now?
- YES → Run migration, integrate onboarding (Option A)
- NO → Focus on testing first (Option B)

**Question 2**: What's the priority?
- **User experience** → Option A (integration)
- **Code quality** → Option B (testing)
- **Agent intelligence** → Option C (agent updates)

**Question 3**: Time available?
- **2-3 hours** → Pick one option and start
- **1 day** → Do Option A + start Option C
- **2-3 days** → Do all three options

---

*Roadmap created: October 13, 2025*
*Ready for your decision on next steps!*
