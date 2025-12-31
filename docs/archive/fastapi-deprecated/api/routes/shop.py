"""
Shop routes for the FastAPI application.

Provides endpoints for:
- Creating shopping lists
- Getting shopping lists
"""
import asyncio
import logging
from typing import Optional

from fastapi import APIRouter, Request, HTTPException, Depends
from pydantic import BaseModel

from ..services.plan_service import get_plan_service, AsyncPlanService

logger = logging.getLogger(__name__)

router = APIRouter()

# Lock to prevent duplicate shopping list generation
_generation_locks: dict = {}
_lock_manager = asyncio.Lock()


class CreateShoppingListRequest(BaseModel):
    """Request body for creating a shopping list."""
    meal_plan_id: str
    scaling_instructions: Optional[str] = None
    session_id: Optional[str] = None


class ShoppingListResponse(BaseModel):
    """Response from shopping list endpoint."""
    success: bool
    grocery_list_id: Optional[str] = None
    cached: bool = False
    error: Optional[str] = None


def get_service(request: Request) -> AsyncPlanService:
    """Dependency to get the plan service."""
    return get_plan_service()


@router.post("/shop", response_model=ShoppingListResponse)
async def create_shopping_list(
    shop_request: CreateShoppingListRequest,
    request: Request,
    service: AsyncPlanService = Depends(get_service)
):
    """
    Create a shopping list from a meal plan.

    Args:
        shop_request: Shopping list configuration

    Returns:
        ShoppingListResponse with list ID
    """
    meal_plan_id = shop_request.meal_plan_id
    session_id = shop_request.session_id or "default"

    # Check/create lock for this meal plan
    async with _lock_manager:
        if meal_plan_id not in _generation_locks:
            _generation_locks[meal_plan_id] = asyncio.Lock()
        lock = _generation_locks[meal_plan_id]

    # Try to acquire lock (non-blocking)
    if lock.locked():
        logger.warning(f"Shopping list already being generated for {meal_plan_id}")
        return ShoppingListResponse(
            success=False,
            error="Shopping list already being generated. Please wait."
        )

    async with lock:
        try:
            await service.pubsub.publish(f"progress:{session_id}", {
                "status": "progress",
                "message": "Generating shopping list..."
            })

            assistant = await service._get_assistant()
            loop = asyncio.get_event_loop()

            from concurrent.futures import ThreadPoolExecutor
            executor = ThreadPoolExecutor(max_workers=1)

            result = await loop.run_in_executor(
                executor,
                lambda: assistant.create_shopping_list(
                    meal_plan_id,
                    scaling_instructions=shop_request.scaling_instructions
                )
            )

            if result.get("success"):
                # Broadcast state change
                await service.pubsub.publish("state:shopping_list_changed", {
                    "type": "shopping_list_changed",
                    "shopping_list_id": result["grocery_list_id"],
                    "meal_plan_id": meal_plan_id
                })

                await service.pubsub.publish(f"progress:{session_id}", {
                    "status": "complete",
                    "message": "Shopping list ready!"
                })

                return ShoppingListResponse(
                    success=True,
                    grocery_list_id=result["grocery_list_id"]
                )
            else:
                await service.pubsub.publish(f"progress:{session_id}", {
                    "status": "error",
                    "message": result.get("error", "Failed to create shopping list")
                })
                return ShoppingListResponse(
                    success=False,
                    error=result.get("error")
                )

        except Exception as e:
            logger.exception(f"Error creating shopping list: {e}")
            raise HTTPException(status_code=500, detail=str(e))


@router.get("/shop/current")
async def get_current_shopping_list(
    meal_plan_id: str,
    service: AsyncPlanService = Depends(get_service)
):
    """
    Get the current shopping list for a meal plan.

    Args:
        meal_plan_id: The meal plan ID to get shopping list for

    Returns:
        Shopping list with items organized by category
    """
    try:
        assistant = await service._get_assistant()
        loop = asyncio.get_event_loop()

        from concurrent.futures import ThreadPoolExecutor
        executor = ThreadPoolExecutor(max_workers=1)

        grocery_list = await loop.run_in_executor(
            executor,
            lambda: assistant.db.get_grocery_list_by_meal_plan(meal_plan_id)
        )

        if not grocery_list:
            return {"success": False, "error": "No shopping list found for this meal plan"}

        return {
            "success": True,
            "grocery_list": grocery_list.to_dict()
        }

    except Exception as e:
        logger.exception(f"Error getting current shopping list: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/shop/{grocery_list_id}")
async def get_shopping_list(
    grocery_list_id: str,
    service: AsyncPlanService = Depends(get_service)
):
    """
    Get a shopping list by ID.

    Args:
        grocery_list_id: The shopping list ID

    Returns:
        Shopping list with items organized by category
    """
    try:
        assistant = await service._get_assistant()
        loop = asyncio.get_event_loop()

        from concurrent.futures import ThreadPoolExecutor
        executor = ThreadPoolExecutor(max_workers=1)

        grocery_list = await loop.run_in_executor(
            executor,
            lambda: assistant.db.get_grocery_list(grocery_list_id)
        )

        if not grocery_list:
            raise HTTPException(status_code=404, detail="Shopping list not found")

        return {
            "success": True,
            "grocery_list": grocery_list.to_dict()
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.exception(f"Error getting shopping list: {e}")
        raise HTTPException(status_code=500, detail=str(e))
