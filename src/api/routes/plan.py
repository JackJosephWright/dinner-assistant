"""
Plan routes for the FastAPI application.

Provides endpoints for:
- Creating meal plans
- Swapping meals
- Getting current plan
- Searching recipes
"""
import logging
from typing import Optional, List

from fastapi import APIRouter, Request, HTTPException, Depends
from pydantic import BaseModel

from ..services.plan_service import get_plan_service, AsyncPlanService

logger = logging.getLogger(__name__)

router = APIRouter()


# Request/Response models
class CreatePlanRequest(BaseModel):
    """Request body for creating a meal plan."""
    week_of: Optional[str] = None
    num_days: int = 7
    session_id: Optional[str] = None


class CreatePlanResponse(BaseModel):
    """Response from create plan endpoint."""
    success: bool
    meal_plan_id: Optional[str] = None
    week_of: Optional[str] = None
    num_days: Optional[int] = None
    error: Optional[str] = None


class SwapMealRequest(BaseModel):
    """Request body for swapping a meal."""
    meal_plan_id: str
    date: str
    requirements: str
    session_id: Optional[str] = None


class MealResponse(BaseModel):
    """Response model for a single meal."""
    id: Optional[str] = None
    meal_date: Optional[str] = None
    meal_type: str = "dinner"
    recipe_id: Optional[str] = None
    recipe_name: Optional[str] = None
    description: Optional[str] = None
    estimated_time: Optional[int] = None
    cuisine: Optional[str] = None
    difficulty: Optional[str] = None


class PlanResponse(BaseModel):
    """Response model for a meal plan."""
    success: bool
    plan: Optional[dict] = None
    error: Optional[str] = None


class SearchRecipesRequest(BaseModel):
    """Request body for searching recipes."""
    query: Optional[str] = None
    max_time: Optional[int] = None
    tags: Optional[List[str]] = None
    limit: int = 20


def get_service(request: Request) -> AsyncPlanService:
    """Dependency to get the plan service."""
    return get_plan_service()


@router.post("/plan", response_model=CreatePlanResponse)
async def create_plan(
    plan_request: CreatePlanRequest,
    request: Request,
    service: AsyncPlanService = Depends(get_service)
):
    """
    Create a new meal plan.

    Connect to /api/progress-stream/{session_id} before calling this
    endpoint to receive real-time progress updates.

    Args:
        plan_request: Plan configuration (week_of, num_days, session_id)

    Returns:
        CreatePlanResponse with plan details
    """
    try:
        session_id = plan_request.session_id or "default"

        result = await service.create_plan(
            session_id=session_id,
            week_of=plan_request.week_of,
            num_days=plan_request.num_days
        )

        # Store meal plan ID in session state
        if result.get("success") and result.get("meal_plan_id"):
            state = get_session_state(session_id)
            state["meal_plan_id"] = result["meal_plan_id"]

        return CreatePlanResponse(**result)

    except Exception as e:
        logger.exception(f"Error creating plan: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/swap-meal")
async def swap_meal(
    swap_request: SwapMealRequest,
    request: Request,
    service: AsyncPlanService = Depends(get_service)
):
    """
    Swap a meal in the current plan.

    Args:
        swap_request: Swap details (meal_plan_id, date, requirements)

    Returns:
        Result of the swap operation
    """
    try:
        session_id = swap_request.session_id or "default"

        result = await service.swap_meal(
            session_id=session_id,
            meal_plan_id=swap_request.meal_plan_id,
            date=swap_request.date,
            requirements=swap_request.requirements
        )

        return result

    except Exception as e:
        logger.exception(f"Error swapping meal: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/plan/{meal_plan_id}", response_model=PlanResponse)
async def get_plan(
    meal_plan_id: str,
    service: AsyncPlanService = Depends(get_service)
):
    """
    Get a meal plan by ID with enriched recipe data.

    Args:
        meal_plan_id: The plan ID to retrieve

    Returns:
        PlanResponse with full plan details
    """
    try:
        plan = await service.get_current_plan(meal_plan_id)

        if plan is None:
            raise HTTPException(status_code=404, detail="Meal plan not found")

        return PlanResponse(success=True, plan=plan)

    except HTTPException:
        raise
    except Exception as e:
        logger.exception(f"Error getting plan: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/search-recipes")
async def search_recipes(
    search_request: SearchRecipesRequest,
    service: AsyncPlanService = Depends(get_service)
):
    """
    Search for recipes.

    Args:
        search_request: Search parameters

    Returns:
        List of matching recipes
    """
    try:
        recipes = await service.search_recipes(
            query=search_request.query,
            max_time=search_request.max_time,
            tags=search_request.tags,
            limit=search_request.limit
        )

        return {
            "success": True,
            "recipes": recipes
        }

    except Exception as e:
        logger.exception(f"Error searching recipes: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# Session-based state (in production, use Redis or database)
# This is a simple in-memory store for demo purposes
_session_state: dict = {}


def get_session_state(session_id: str) -> dict:
    """Get or create session state."""
    if session_id not in _session_state:
        _session_state[session_id] = {}
    return _session_state[session_id]


@router.get("/plan/current", response_model=PlanResponse)
async def get_current_plan(
    request: Request,
    session_id: str = "default",
    service: AsyncPlanService = Depends(get_service)
):
    """
    Get the current meal plan for the session.

    This endpoint is used by the frontend to fetch the active meal plan.
    """
    try:
        state = get_session_state(session_id)
        meal_plan_id = state.get("meal_plan_id")

        if not meal_plan_id:
            return PlanResponse(success=False, error="No active meal plan")

        plan = await service.get_current_plan(meal_plan_id)

        if plan is None:
            return PlanResponse(success=False, error="Meal plan not found")

        return PlanResponse(success=True, plan=plan)

    except Exception as e:
        logger.exception(f"Error getting current plan: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/plan/preload")
async def preload_plan_data(
    request: Request,
    session_id: str = "default",
    service: AsyncPlanService = Depends(get_service)
):
    """
    Preload shopping list and cook page data for current meal plan.

    This triggers background generation of shopping lists.
    """
    try:
        state = get_session_state(session_id)
        meal_plan_id = state.get("meal_plan_id")

        if not meal_plan_id:
            raise HTTPException(status_code=400, detail="No active meal plan")

        # Trigger shopping list generation in background
        import asyncio
        asyncio.create_task(
            service._generate_shopping_list_background(session_id, meal_plan_id)
        )

        return {
            "success": True,
            "message": "Background preloading started",
            "meal_plan_id": meal_plan_id
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.exception(f"Error preloading data: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/plan/clear")
async def clear_plan(
    request: Request,
    session_id: str = "default"
):
    """
    Clear the current meal plan from the session.
    """
    try:
        state = get_session_state(session_id)
        old_plan_id = state.pop("meal_plan_id", None)
        state.pop("shopping_list_id", None)

        return {
            "success": True,
            "message": "Session cleared",
            "cleared_plan_id": old_plan_id
        }

    except Exception as e:
        logger.exception(f"Error clearing plan: {e}")
        raise HTTPException(status_code=500, detail=str(e))
