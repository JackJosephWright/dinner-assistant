"""
Chat routes for the FastAPI application.

Provides endpoints for:
- Sending chat messages
- Getting session state
- Managing chat sessions
"""
import logging
from typing import Optional

from fastapi import APIRouter, Request, HTTPException, Depends
from pydantic import BaseModel

from ..services.chat_service import get_chat_service, AsyncChatService

logger = logging.getLogger(__name__)

router = APIRouter()


class ChatRequest(BaseModel):
    """Request body for chat endpoint."""
    message: str
    session_id: Optional[str] = None


class ChatResponse(BaseModel):
    """Response from chat endpoint."""
    response: str
    session_id: str
    meal_plan_changed: bool
    shopping_list_changed: bool


def get_service(request: Request) -> AsyncChatService:
    """Dependency to get the chat service."""
    return get_chat_service()


@router.post("/chat", response_model=ChatResponse)
async def chat(
    chat_request: ChatRequest,
    request: Request,
    service: AsyncChatService = Depends(get_service)
):
    """
    Send a chat message and get a response.

    The chat runs asynchronously and publishes progress updates to
    the SSE progress-stream endpoint. Connect to:
      /api/progress-stream/{session_id}
    before calling this endpoint to receive real-time updates.

    Args:
        chat_request: Message and optional session_id

    Returns:
        ChatResponse with the assistant's response and metadata
    """
    try:
        # Get session ID from request or generate new one
        session_id = chat_request.session_id

        # TODO: Get user_id from authentication
        user_id = None

        result = await service.chat(
            session_id=session_id or "",
            message=chat_request.message,
            user_id=user_id
        )

        return ChatResponse(
            response=result["response"],
            session_id=result["session_id"],
            meal_plan_changed=result["meal_plan_changed"],
            shopping_list_changed=result["shopping_list_changed"]
        )

    except Exception as e:
        logger.exception(f"Chat error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/chat/session/{session_id}")
async def get_session(
    session_id: str,
    service: AsyncChatService = Depends(get_service)
):
    """
    Get the current state of a chat session.

    Returns session metadata including whether a meal plan exists.
    """
    state = await service.get_session_state(session_id)
    if state is None:
        raise HTTPException(status_code=404, detail="Session not found")
    return state


@router.delete("/chat/session/{session_id}")
async def delete_session(
    session_id: str,
    service: AsyncChatService = Depends(get_service)
):
    """
    Delete a chat session and clean up resources.
    """
    cleaned = await service.cleanup_session(session_id)
    if not cleaned:
        raise HTTPException(status_code=404, detail="Session not found")
    return {"status": "deleted", "session_id": session_id}
