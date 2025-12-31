"""
Redis Pub/Sub Manager for distributed SSE messaging.

This replaces the in-memory queue.Queue() approach with Redis pub/sub,
enabling horizontal scaling across multiple workers/containers.

Key concepts:
- publish(): Send a message to a channel (any worker can do this)
- subscribe(): Listen for messages on a channel (SSE endpoint does this)
- Channels are named by purpose: "progress:{session_id}", "state:broadcast"
"""
import json
import logging
import os
from typing import AsyncGenerator, Optional
from contextlib import asynccontextmanager

import redis.asyncio as redis

logger = logging.getLogger(__name__)


class PubSubManager:
    """
    Manages Redis pub/sub connections for real-time messaging.

    Usage:
        pubsub = PubSubManager()
        await pubsub.connect()

        # Publishing (from any worker)
        await pubsub.publish("progress:session123", {"status": "progress", "message": "Loading..."})

        # Subscribing (SSE endpoint)
        async for message in pubsub.subscribe("progress:session123"):
            yield f"data: {json.dumps(message)}\n\n"
    """

    def __init__(self, redis_url: Optional[str] = None):
        """
        Initialize the pub/sub manager.

        Args:
            redis_url: Redis connection URL. Defaults to REDIS_URL env var or localhost.
        """
        self.redis_url = redis_url or os.getenv("REDIS_URL", "redis://localhost:6379")
        self._redis: Optional[redis.Redis] = None

    async def connect(self) -> None:
        """Establish Redis connection."""
        if self._redis is None:
            try:
                self._redis = redis.from_url(
                    self.redis_url,
                    encoding="utf-8",
                    decode_responses=True
                )
                # Test connection
                await self._redis.ping()
                logger.info(f"Connected to Redis at {self.redis_url}")
            except redis.ConnectionError as e:
                logger.warning(f"Redis not available at {self.redis_url}: {e}")
                logger.warning("Running in local-only mode (no horizontal scaling)")
                self._redis = None
                raise

    async def disconnect(self) -> None:
        """Close Redis connection."""
        if self._redis:
            await self._redis.close()
            self._redis = None
            logger.info("Disconnected from Redis")

    @property
    def redis(self) -> redis.Redis:
        """Get the Redis client, raising if not connected."""
        if self._redis is None:
            raise RuntimeError("Redis not connected. Call connect() first.")
        return self._redis

    async def publish(self, channel: str, message: dict) -> int:
        """
        Publish a message to a channel.

        Args:
            channel: Channel name (e.g., "progress:session123")
            message: Dictionary to publish (will be JSON serialized)

        Returns:
            Number of subscribers that received the message
        """
        payload = json.dumps(message)
        count = await self.redis.publish(channel, payload)
        logger.debug(f"Published to {channel}: {message.get('status', 'unknown')} ({count} subscribers)")
        return count

    async def subscribe(self, channel: str, timeout: float = 30.0) -> AsyncGenerator[dict, None]:
        """
        Subscribe to a channel and yield messages.

        Args:
            channel: Channel name to subscribe to
            timeout: Seconds to wait before yielding a keepalive (default 30s)

        Yields:
            Parsed message dictionaries

        Note:
            This is an infinite generator. The caller should break out when
            receiving a "complete" or "error" status.
        """
        pubsub = self.redis.pubsub()
        await pubsub.subscribe(channel)
        logger.debug(f"Subscribed to {channel}")

        try:
            while True:
                try:
                    # Wait for message with timeout
                    message = await pubsub.get_message(
                        ignore_subscribe_messages=True,
                        timeout=timeout
                    )

                    if message is None:
                        # Timeout - send keepalive
                        yield {"type": "keepalive"}
                        continue

                    if message["type"] == "message":
                        data = json.loads(message["data"])
                        yield data

                        # Check for terminal status
                        if data.get("status") in ("complete", "error"):
                            logger.debug(f"Terminal status on {channel}: {data.get('status')}")
                            break

                except json.JSONDecodeError as e:
                    logger.error(f"Invalid JSON on {channel}: {e}")
                    continue

        finally:
            await pubsub.unsubscribe(channel)
            await pubsub.close()
            logger.debug(f"Unsubscribed from {channel}")

    async def subscribe_broadcast(self, pattern: str = "state:*") -> AsyncGenerator[dict, None]:
        """
        Subscribe to broadcast channels using pattern matching.

        Args:
            pattern: Redis pattern to match (e.g., "state:*")

        Yields:
            Parsed message dictionaries with channel info
        """
        pubsub = self.redis.pubsub()
        await pubsub.psubscribe(pattern)
        logger.debug(f"Pattern subscribed to {pattern}")

        try:
            while True:
                message = await pubsub.get_message(
                    ignore_subscribe_messages=True,
                    timeout=30.0
                )

                if message is None:
                    yield {"type": "keepalive"}
                    continue

                if message["type"] == "pmessage":
                    data = json.loads(message["data"])
                    data["_channel"] = message["channel"]
                    yield data

        finally:
            await pubsub.punsubscribe(pattern)
            await pubsub.close()


# Global instance for dependency injection
_pubsub_manager: Optional[PubSubManager] = None


def get_pubsub() -> PubSubManager:
    """Get the global PubSubManager instance."""
    global _pubsub_manager
    if _pubsub_manager is None:
        _pubsub_manager = PubSubManager()
    return _pubsub_manager


@asynccontextmanager
async def pubsub_lifespan():
    """
    Context manager for FastAPI lifespan events.

    Usage in main.py:
        @asynccontextmanager
        async def lifespan(app: FastAPI):
            async with pubsub_lifespan():
                yield

        app = FastAPI(lifespan=lifespan)
    """
    pubsub = get_pubsub()
    await pubsub.connect()
    try:
        yield pubsub
    finally:
        await pubsub.disconnect()
