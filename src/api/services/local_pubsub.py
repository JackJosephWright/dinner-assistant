"""
Local in-memory Pub/Sub Manager for development without Redis.

This provides the same interface as redis_pubsub.py but uses asyncio
for in-memory message passing. Use this for local development when
Redis is not available.

Limitations:
- Single process only (no horizontal scaling)
- Messages lost on restart
- For development only, not production
"""
import asyncio
import json
import logging
from collections import defaultdict
from typing import AsyncGenerator, Optional, Set
from contextlib import asynccontextmanager

logger = logging.getLogger(__name__)


class LocalPubSubManager:
    """
    In-memory pub/sub using asyncio for local development.

    Implements the same interface as PubSubManager but without Redis.
    """

    def __init__(self):
        """Initialize the local pub/sub manager."""
        # channel -> set of asyncio.Queue subscribers
        self._channels: dict[str, Set[asyncio.Queue]] = defaultdict(set)
        self._pattern_subscribers: dict[str, Set[asyncio.Queue]] = defaultdict(set)
        self._lock = asyncio.Lock()

    async def connect(self) -> None:
        """No-op for local implementation."""
        logger.info("Local pub/sub initialized (no Redis)")

    async def disconnect(self) -> None:
        """Clean up all subscriptions."""
        async with self._lock:
            self._channels.clear()
            self._pattern_subscribers.clear()
        logger.info("Local pub/sub disconnected")

    async def publish(self, channel: str, message: dict) -> int:
        """
        Publish a message to a channel.

        Args:
            channel: Channel name (e.g., "progress:session123")
            message: Dictionary to publish

        Returns:
            Number of subscribers that received the message
        """
        count = 0
        async with self._lock:
            # Direct channel subscribers
            for queue in self._channels.get(channel, set()):
                await queue.put(message)
                count += 1

            # Pattern subscribers (e.g., "state:*" matches "state:broadcast")
            for pattern, subscribers in self._pattern_subscribers.items():
                if self._matches_pattern(pattern, channel):
                    for queue in subscribers:
                        msg_with_channel = message.copy()
                        msg_with_channel["_channel"] = channel
                        await queue.put(msg_with_channel)
                        count += 1

        logger.debug(f"Published to {channel}: {message.get('status', 'unknown')} ({count} subscribers)")
        return count

    def _matches_pattern(self, pattern: str, channel: str) -> bool:
        """Check if a channel matches a glob pattern."""
        if pattern.endswith("*"):
            prefix = pattern[:-1]
            return channel.startswith(prefix)
        return pattern == channel

    async def subscribe(self, channel: str, timeout: float = 30.0) -> AsyncGenerator[dict, None]:
        """
        Subscribe to a channel and yield messages.

        Args:
            channel: Channel name to subscribe to
            timeout: Seconds to wait before yielding a keepalive

        Yields:
            Parsed message dictionaries
        """
        queue: asyncio.Queue = asyncio.Queue()

        async with self._lock:
            self._channels[channel].add(queue)
        logger.debug(f"Subscribed to {channel}")

        try:
            while True:
                try:
                    message = await asyncio.wait_for(queue.get(), timeout=timeout)
                    yield message

                    # Check for terminal status
                    if message.get("status") in ("complete", "error"):
                        logger.debug(f"Terminal status on {channel}: {message.get('status')}")
                        break

                except asyncio.TimeoutError:
                    # Send keepalive
                    yield {"type": "keepalive"}

        finally:
            async with self._lock:
                self._channels[channel].discard(queue)
            logger.debug(f"Unsubscribed from {channel}")

    async def subscribe_broadcast(self, pattern: str = "state:*") -> AsyncGenerator[dict, None]:
        """
        Subscribe to broadcast channels using pattern matching.

        Args:
            pattern: Glob pattern to match (e.g., "state:*")

        Yields:
            Parsed message dictionaries with channel info
        """
        queue: asyncio.Queue = asyncio.Queue()

        async with self._lock:
            self._pattern_subscribers[pattern].add(queue)
        logger.debug(f"Pattern subscribed to {pattern}")

        try:
            while True:
                try:
                    message = await asyncio.wait_for(queue.get(), timeout=30.0)
                    yield message

                except asyncio.TimeoutError:
                    yield {"type": "keepalive"}

        finally:
            async with self._lock:
                self._pattern_subscribers[pattern].discard(queue)
            logger.debug(f"Pattern unsubscribed from {pattern}")


# Global instance for dependency injection
_local_pubsub_manager: Optional[LocalPubSubManager] = None


def get_local_pubsub() -> LocalPubSubManager:
    """Get the global LocalPubSubManager instance."""
    global _local_pubsub_manager
    if _local_pubsub_manager is None:
        _local_pubsub_manager = LocalPubSubManager()
    return _local_pubsub_manager


@asynccontextmanager
async def local_pubsub_lifespan():
    """
    Context manager for FastAPI lifespan events.

    Usage in main.py:
        @asynccontextmanager
        async def lifespan(app: FastAPI):
            async with local_pubsub_lifespan():
                yield

        app = FastAPI(lifespan=lifespan)
    """
    pubsub = get_local_pubsub()
    await pubsub.connect()
    try:
        yield pubsub
    finally:
        await pubsub.disconnect()
