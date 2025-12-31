# FastAPI Code - Archived (December 2025)

This directory contains the deprecated FastAPI implementation that was replaced by Flask.

## Why Archived

The project ran **two web frameworks in parallel** during a migration period:
- Flask (`src/web/app.py`) - 33 routes, full feature set
- FastAPI (`src/api/`) - 21 routes, incomplete feature set

This created:
- 12 duplicate endpoints
- 2,183 lines of duplicate code
- Maintenance burden
- Confusion about which framework to use

## Decision

Flask was chosen as the canonical server because:
1. **Complete feature set** - Auth, sessions, onboarding, history, preferences
2. **All tests pass** - Test suite targets Flask
3. **Active development** - Recent features added to Flask only
4. **Simpler deployment** - Single entrypoint

## What Was Here

```
src/api/
├── main.py (266 lines) - FastAPI app, SSE endpoints
├── routes/
│   ├── plan.py (321 lines) - /api/plan, /api/swap-meal
│   ├── shop.py (208 lines) - /api/shop
│   ├── cook.py (99 lines) - /api/cook/{id}
│   ├── chat.py (115 lines) - /api/chat
│   └── pages.py (106 lines) - HTML templates
└── services/
    ├── plan_service.py (350 lines) - Async planning
    ├── chat_service.py (320 lines) - Async chat
    ├── redis_pubsub.py (213 lines) - Redis pub/sub
    └── local_pubsub.py (183 lines) - Local fallback

Total: 2,183 lines
```

## If You Need This Code

This code is preserved for reference. Key patterns that may be useful:
- `services/redis_pubsub.py` - Redis pub/sub pattern
- `services/plan_service.py` - Async service abstraction

Do NOT attempt to restore this alongside Flask. Choose one framework.

## Current Server

Use Flask: `python3 src/web/app.py`
