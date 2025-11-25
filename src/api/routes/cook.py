"""
Cook routes for the FastAPI application.

Provides endpoints for:
- Getting cooking guides for recipes
- Getting recipe details
"""
import asyncio
import logging
from concurrent.futures import ThreadPoolExecutor

from fastapi import APIRouter, Request, HTTPException, Depends

from ..services.plan_service import get_plan_service, AsyncPlanService

logger = logging.getLogger(__name__)

router = APIRouter()

# Thread pool for cooking operations
_executor = ThreadPoolExecutor(max_workers=4, thread_name_prefix="cook_")


def get_service(request: Request) -> AsyncPlanService:
    """Dependency to get the plan service."""
    return get_plan_service()


@router.get("/cook/{recipe_id}")
async def get_cooking_guide(
    recipe_id: str,
    service: AsyncPlanService = Depends(get_service)
):
    """
    Get a cooking guide for a recipe.

    The cooking guide includes:
    - Recipe details (name, description, ingredients)
    - Step-by-step cooking instructions
    - Tips and substitutions

    Args:
        recipe_id: The recipe ID to get guide for

    Returns:
        Cooking guide with recipe details and instructions
    """
    try:
        assistant = await service._get_assistant()
        loop = asyncio.get_event_loop()

        result = await loop.run_in_executor(
            _executor,
            lambda: assistant.get_cooking_guide(recipe_id)
        )

        return result

    except Exception as e:
        logger.exception(f"Error getting cooking guide: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/recipe/{recipe_id}")
async def get_recipe(
    recipe_id: str,
    service: AsyncPlanService = Depends(get_service)
):
    """
    Get recipe details by ID.

    Args:
        recipe_id: The recipe ID

    Returns:
        Recipe details including ingredients and steps
    """
    try:
        assistant = await service._get_assistant()
        loop = asyncio.get_event_loop()

        recipe = await loop.run_in_executor(
            _executor,
            lambda: assistant.db.get_recipe(recipe_id)
        )

        if not recipe:
            raise HTTPException(status_code=404, detail="Recipe not found")

        return {
            "success": True,
            "recipe": recipe.to_dict()
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.exception(f"Error getting recipe: {e}")
        raise HTTPException(status_code=500, detail=str(e))
