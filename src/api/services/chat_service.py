"""
Async Chat Service for FastAPI.

Wraps the synchronous MealPlanningChatbot with:
- Async execution via thread pool
- Real-time progress updates via pub/sub
- Session management for concurrent users
"""
import asyncio
import logging
import os
import sys
import uuid
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from typing import Optional, Dict, Any, Union

# Add project root and src to path for legacy imports
project_root = os.path.join(os.path.dirname(__file__), '..', '..', '..')
src_dir = os.path.join(project_root, 'src')
sys.path.insert(0, project_root)
sys.path.insert(0, src_dir)

from chatbot import MealPlanningChatbot
from .redis_pubsub import PubSubManager
from .local_pubsub import LocalPubSubManager

logger = logging.getLogger(__name__)

# Thread pool for running sync chatbot operations
_executor = ThreadPoolExecutor(max_workers=4, thread_name_prefix="chat_")


@dataclass
class ChatSession:
    """Represents an active chat session."""
    session_id: str
    chatbot: MealPlanningChatbot
    user_id: Optional[int] = None


class AsyncChatService:
    """
    Async wrapper around MealPlanningChatbot.

    Key features:
    - Non-blocking async interface
    - Progress updates via pub/sub
    - Session isolation (each user gets their own chatbot instance)
    - Thread-safe operation
    """

    def __init__(self, pubsub: Union[PubSubManager, LocalPubSubManager]):
        """
        Initialize the chat service.

        Args:
            pubsub: Pub/sub manager for broadcasting progress updates
        """
        self.pubsub = pubsub
        self._sessions: Dict[str, ChatSession] = {}
        self._lock = asyncio.Lock()

    def _create_progress_callback(self, session_id: str):
        """
        Create a progress callback that publishes to pub/sub.

        This callback runs in a thread, so we need to safely publish
        to the async pub/sub channel.
        """
        def callback(message: str):
            """Sync callback that queues async publish."""
            # Create a new event loop for this thread if needed
            try:
                loop = asyncio.get_event_loop()
                if loop.is_running():
                    # We're in an async context, schedule the publish
                    asyncio.create_task(
                        self.pubsub.publish(f"progress:{session_id}", {
                            "status": "progress",
                            "message": message
                        })
                    )
                else:
                    # Run synchronously in this thread
                    loop.run_until_complete(
                        self.pubsub.publish(f"progress:{session_id}", {
                            "status": "progress",
                            "message": message
                        })
                    )
            except RuntimeError:
                # No event loop in this thread, create one
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                try:
                    loop.run_until_complete(
                        self.pubsub.publish(f"progress:{session_id}", {
                            "status": "progress",
                            "message": message
                        })
                    )
                finally:
                    loop.close()

        return callback

    async def get_or_create_session(
        self, session_id: Optional[str] = None, user_id: Optional[int] = None
    ) -> ChatSession:
        """
        Get or create a chat session.

        Args:
            session_id: Optional session ID. If None, generates a new one.
            user_id: Optional user ID for loading user-specific data.

        Returns:
            ChatSession instance
        """
        session_id = session_id or str(uuid.uuid4())

        async with self._lock:
            if session_id not in self._sessions:
                logger.info(f"Creating new chat session: {session_id}")

                # Create chatbot in thread pool (it does sync initialization)
                loop = asyncio.get_event_loop()
                chatbot = await loop.run_in_executor(
                    _executor,
                    lambda: MealPlanningChatbot(
                        verbose=True,
                        verbose_callback=self._create_progress_callback(session_id)
                    )
                )

                self._sessions[session_id] = ChatSession(
                    session_id=session_id,
                    chatbot=chatbot,
                    user_id=user_id
                )

            return self._sessions[session_id]

    async def chat(
        self, session_id: str, message: str, user_id: Optional[int] = None
    ) -> Dict[str, Any]:
        """
        Send a message and get a response.

        This is the main async entry point for chat operations.

        Args:
            session_id: Session identifier
            message: User message
            user_id: Optional user ID

        Returns:
            Dict with response and metadata:
            {
                "response": str,
                "meal_plan_changed": bool,
                "shopping_list_changed": bool,
                "session_id": str
            }
        """
        # Publish start event
        await self.pubsub.publish(f"progress:{session_id}", {
            "status": "progress",
            "message": "Processing your message..."
        })

        try:
            # Get or create session
            session = await self.get_or_create_session(session_id, user_id)

            # Update the progress callback for this request
            session.chatbot.verbose_callback = self._create_progress_callback(session_id)

            # Run chat in thread pool
            loop = asyncio.get_event_loop()
            response = await loop.run_in_executor(
                _executor,
                session.chatbot.chat,
                message
            )

            # Check what changed
            meal_plan_changed = session.chatbot.last_meal_plan is not None
            shopping_list_changed = False  # TODO: Track this

            # Publish completion
            await self.pubsub.publish(f"progress:{session_id}", {
                "status": "complete",
                "message": "Done"
            })

            # Broadcast state change if meal plan was modified
            if meal_plan_changed:
                await self.pubsub.publish("state:meal_plan_changed", {
                    "type": "meal_plan_changed",
                    "session_id": session_id
                })

            return {
                "response": response,
                "meal_plan_changed": meal_plan_changed,
                "shopping_list_changed": shopping_list_changed,
                "session_id": session_id
            }

        except Exception as e:
            logger.exception(f"Chat error in session {session_id}: {e}")

            # Publish error
            await self.pubsub.publish(f"progress:{session_id}", {
                "status": "error",
                "message": str(e)
            })

            raise

    async def get_session_state(self, session_id: str) -> Optional[Dict[str, Any]]:
        """
        Get the current state of a session.

        Returns:
            Session state dict or None if session doesn't exist
        """
        async with self._lock:
            session = self._sessions.get(session_id)
            if not session:
                return None

            return {
                "session_id": session.session_id,
                "user_id": session.user_id,
                "has_meal_plan": session.chatbot.last_meal_plan is not None,
                "current_meal_plan_id": session.chatbot.current_meal_plan_id,
                "current_shopping_list_id": session.chatbot.current_shopping_list_id,
            }

    async def cleanup_session(self, session_id: str) -> bool:
        """
        Clean up a session and free resources.

        Returns:
            True if session was cleaned up, False if it didn't exist
        """
        async with self._lock:
            if session_id in self._sessions:
                del self._sessions[session_id]
                logger.info(f"Cleaned up session: {session_id}")
                return True
            return False


# Global service instance (set during app startup)
_chat_service: Optional[AsyncChatService] = None


def get_chat_service() -> AsyncChatService:
    """Get the global chat service instance."""
    if _chat_service is None:
        raise RuntimeError("Chat service not initialized. Call init_chat_service() first.")
    return _chat_service


def init_chat_service(pubsub: Union[PubSubManager, LocalPubSubManager]) -> AsyncChatService:
    """Initialize the global chat service."""
    global _chat_service
    _chat_service = AsyncChatService(pubsub)
    return _chat_service
