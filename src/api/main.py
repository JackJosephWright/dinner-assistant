"""
FastAPI application for Dinner Assistant.

This replaces the Flask app with:
- Native async/await support
- Redis pub/sub for distributed messaging (enables horizontal scaling)
- Local fallback for development without Redis
- Proper SSE implementation using StreamingResponse
- Clean dependency injection
"""
import logging
import os
from contextlib import asynccontextmanager
from typing import AsyncGenerator, Union

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse, JSONResponse
from sse_starlette.sse import EventSourceResponse

from .services.redis_pubsub import PubSubManager, pubsub_lifespan, get_pubsub
from .services.local_pubsub import LocalPubSubManager, local_pubsub_lifespan, get_local_pubsub

# Configure logging
logging.basicConfig(
    level=logging.DEBUG if os.getenv("DEBUG", "false").lower() == "true" else logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Application lifespan manager.

    Handles startup and shutdown of:
    - Redis pub/sub connections (with local fallback)
    - Any other resources that need lifecycle management
    """
    logger.info("Starting Dinner Assistant API...")

    # Try Redis first, fall back to local pub/sub
    use_redis = os.getenv("USE_REDIS", "true").lower() == "true"

    if use_redis:
        try:
            async with pubsub_lifespan() as pubsub:
                app.state.pubsub = pubsub
                app.state.pubsub_type = "redis"
                logger.info("Redis pub/sub connected")

                # Initialize services with pub/sub
                from .services.chat_service import init_chat_service
                from .services.plan_service import init_plan_service
                init_chat_service(pubsub)
                init_plan_service(pubsub)
                logger.info("Services initialized (chat, plan)")

                yield
        except Exception as e:
            logger.warning(f"Redis connection failed: {e}")
            logger.info("Falling back to local pub/sub (no horizontal scaling)")
            async with local_pubsub_lifespan() as pubsub:
                app.state.pubsub = pubsub
                app.state.pubsub_type = "local"

                # Initialize services with local pub/sub
                from .services.chat_service import init_chat_service
                from .services.plan_service import init_plan_service
                init_chat_service(pubsub)
                init_plan_service(pubsub)
                logger.info("Services initialized (local mode)")

                yield
    else:
        logger.info("Using local pub/sub (USE_REDIS=false)")
        async with local_pubsub_lifespan() as pubsub:
            app.state.pubsub = pubsub
            app.state.pubsub_type = "local"

            # Initialize services with local pub/sub
            from .services.chat_service import init_chat_service
            from .services.plan_service import init_plan_service
            init_chat_service(pubsub)
            init_plan_service(pubsub)
            logger.info("Services initialized (local mode)")

            yield

    logger.info("Dinner Assistant API shutdown complete")


# Create FastAPI app with lifespan
app = FastAPI(
    title="Dinner Assistant API",
    description="AI-powered meal planning assistant with real-time progress updates",
    version="2.0.0",
    lifespan=lifespan,
)

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # TODO: Restrict in production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
async def health_check(request: Request):
    """
    Health check endpoint for load balancers and container orchestration.

    Returns 200 if the service is healthy.
    """
    try:
        pubsub_type = getattr(request.app.state, "pubsub_type", "unknown")

        if pubsub_type == "redis":
            pubsub = request.app.state.pubsub
            await pubsub.redis.ping()
            return {"status": "healthy", "pubsub": "redis"}
        else:
            return {"status": "healthy", "pubsub": "local"}
    except Exception as e:
        logger.error(f"Health check failed: {e}")
        return JSONResponse(
            status_code=503,
            content={"status": "unhealthy", "error": str(e)}
        )


@app.get("/api/progress-stream/{session_id}")
async def progress_stream(session_id: str, request: Request):
    """
    SSE endpoint for progress updates during LLM operations.

    Uses Redis pub/sub (or local fallback) so any worker can publish
    progress and any client can receive it - enabling horizontal scaling.

    Args:
        session_id: Unique session identifier for this operation

    Returns:
        Server-Sent Events stream with progress updates
    """
    pubsub = request.app.state.pubsub
    channel = f"progress:{session_id}"

    async def event_generator() -> AsyncGenerator[dict, None]:
        """Generate SSE events from Redis pub/sub channel."""
        logger.debug(f"SSE client connected to progress:{session_id}")

        async for message in pubsub.subscribe(channel, timeout=30.0):
            # Check if client disconnected
            if await request.is_disconnected():
                logger.debug(f"SSE client disconnected from {channel}")
                break

            # Yield message (will be auto-serialized by EventSourceResponse)
            yield message

            # Exit on terminal status
            if message.get("status") in ("complete", "error"):
                break

        logger.debug(f"SSE stream ended for {channel}")

    return EventSourceResponse(
        event_generator(),
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",  # Critical for Cloud Run/nginx
        }
    )


@app.get("/api/state-stream")
async def state_stream(request: Request, tab_id: str = None):
    """
    SSE endpoint for cross-tab state synchronization.

    All browser tabs subscribe to state:* pattern and receive
    broadcasts when meal plans or shopping lists change.

    Args:
        tab_id: Optional identifier for this browser tab

    Returns:
        Server-Sent Events stream with state change notifications
    """
    import uuid
    tab_id = tab_id or str(uuid.uuid4())

    pubsub = request.app.state.pubsub

    async def event_generator() -> AsyncGenerator[dict, None]:
        """Generate SSE events from state broadcast channels."""
        logger.debug(f"State stream connected: tab={tab_id}")

        async for message in pubsub.subscribe_broadcast("state:*"):
            # Check if client disconnected
            if await request.is_disconnected():
                logger.debug(f"State stream disconnected: tab={tab_id}")
                break

            yield message

    return EventSourceResponse(
        event_generator(),
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        }
    )


# Import and include route modules
from .routes import chat, plan, shop, cook, pages
from .services.chat_service import init_chat_service
from .services.plan_service import init_plan_service

# Include API routers
app.include_router(chat.router, prefix="/api", tags=["chat"])
app.include_router(plan.router, prefix="/api", tags=["planning"])
app.include_router(shop.router, prefix="/api", tags=["shopping"])
app.include_router(cook.router, prefix="/api", tags=["cooking"])

# Include page routes (HTML templates)
app.include_router(pages.router, tags=["pages"])

# Mount static files
from fastapi.staticfiles import StaticFiles
import os as _os
_static_dir = _os.path.join(_os.path.dirname(__file__), '..', 'web', 'static')
if _os.path.exists(_static_dir):
    app.mount("/static", StaticFiles(directory=_static_dir), name="static")


if __name__ == "__main__":
    import uvicorn

    port = int(os.getenv("PORT", 5000))
    uvicorn.run(
        "src.api.main:app",
        host="0.0.0.0",
        port=port,
        reload=True,
        log_level="debug",
    )
