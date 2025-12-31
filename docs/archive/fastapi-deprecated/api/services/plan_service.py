"""
Async Plan Service for FastAPI.

Handles meal planning operations:
- Creating new meal plans
- Swapping meals
- Getting current plan
- Managing plan state
"""
import asyncio
import logging
import os
import sys
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Optional, Dict, Any, List, Union

# Add project root and src to path for legacy imports
project_root = os.path.join(os.path.dirname(__file__), '..', '..', '..')
src_dir = os.path.join(project_root, 'src')
sys.path.insert(0, project_root)
sys.path.insert(0, src_dir)

from main import MealPlanningAssistant
from .redis_pubsub import PubSubManager
from .local_pubsub import LocalPubSubManager

logger = logging.getLogger(__name__)

# Thread pool for running sync operations
_executor = ThreadPoolExecutor(max_workers=4, thread_name_prefix="plan_")


class AsyncPlanService:
    """
    Async service for meal planning operations.

    Wraps the synchronous MealPlanningAssistant with async interface
    and publishes progress/state updates via pub/sub.
    """

    def __init__(self, pubsub: Union[PubSubManager, LocalPubSubManager]):
        """
        Initialize the plan service.

        Args:
            pubsub: Pub/sub manager for broadcasting updates
        """
        self.pubsub = pubsub
        self._assistant: Optional[MealPlanningAssistant] = None
        self._lock = asyncio.Lock()

    async def _get_assistant(self) -> MealPlanningAssistant:
        """Get or create the assistant instance."""
        if self._assistant is None:
            loop = asyncio.get_event_loop()
            self._assistant = await loop.run_in_executor(
                _executor,
                lambda: MealPlanningAssistant(db_dir="data", use_agentic=True)
            )
        return self._assistant

    async def create_plan(
        self,
        session_id: str,
        week_of: Optional[str] = None,
        num_days: int = 7,
        user_id: int = 1
    ) -> Dict[str, Any]:
        """
        Create a new meal plan.

        Args:
            session_id: Session ID for progress updates
            week_of: Start date (YYYY-MM-DD), defaults to next Monday
            num_days: Number of days to plan
            user_id: User ID for snapshots

        Returns:
            Dict with plan details
        """
        # Calculate default week_of
        if not week_of:
            today = datetime.now()
            days_until_monday = (7 - today.weekday()) % 7
            if days_until_monday == 0:
                days_until_monday = 7
            next_monday = today + timedelta(days=days_until_monday)
            week_of = next_monday.strftime("%Y-%m-%d")

        # Publish start
        await self.pubsub.publish(f"progress:{session_id}", {
            "status": "progress",
            "message": f"Creating meal plan for week of {week_of}..."
        })

        try:
            assistant = await self._get_assistant()

            # Run plan creation in thread pool
            loop = asyncio.get_event_loop()
            result = await loop.run_in_executor(
                _executor,
                lambda: assistant.plan_week(week_of=week_of, num_days=num_days)
            )

            if result.get("success"):
                meal_plan_id = result["meal_plan_id"]

                # Broadcast state change
                await self.pubsub.publish("state:meal_plan_changed", {
                    "type": "meal_plan_changed",
                    "meal_plan_id": meal_plan_id,
                    "week_of": week_of
                })

                # Start background shopping list generation
                asyncio.create_task(
                    self._generate_shopping_list_background(session_id, meal_plan_id)
                )

                await self.pubsub.publish(f"progress:{session_id}", {
                    "status": "complete",
                    "message": "Meal plan created!"
                })

                return {
                    "success": True,
                    "meal_plan_id": meal_plan_id,
                    "week_of": week_of,
                    "num_days": num_days
                }
            else:
                await self.pubsub.publish(f"progress:{session_id}", {
                    "status": "error",
                    "message": result.get("error", "Failed to create plan")
                })
                return result

        except Exception as e:
            logger.exception(f"Error creating plan: {e}")
            await self.pubsub.publish(f"progress:{session_id}", {
                "status": "error",
                "message": str(e)
            })
            raise

    async def _generate_shopping_list_background(
        self,
        session_id: str,
        meal_plan_id: str
    ):
        """Background task to generate shopping list after plan creation."""
        try:
            logger.info(f"[Background] Generating shopping list for plan {meal_plan_id}")

            assistant = await self._get_assistant()
            loop = asyncio.get_event_loop()

            result = await loop.run_in_executor(
                _executor,
                lambda: assistant.create_shopping_list(meal_plan_id)
            )

            if result.get("success"):
                shopping_list_id = result["grocery_list_id"]
                logger.info(f"[Background] Created shopping list: {shopping_list_id}")

                # Broadcast shopping list change
                await self.pubsub.publish("state:shopping_list_changed", {
                    "type": "shopping_list_changed",
                    "shopping_list_id": shopping_list_id,
                    "meal_plan_id": meal_plan_id
                })
            else:
                logger.error(f"[Background] Shopping list failed: {result.get('error')}")

        except Exception as e:
            logger.exception(f"[Background] Error generating shopping list: {e}")

    async def swap_meal(
        self,
        session_id: str,
        meal_plan_id: str,
        date: str,
        requirements: str
    ) -> Dict[str, Any]:
        """
        Swap a meal in the plan.

        Args:
            session_id: Session ID for progress updates
            meal_plan_id: Current meal plan ID
            date: Date of meal to swap (YYYY-MM-DD)
            requirements: User requirements for new meal

        Returns:
            Dict with swap result
        """
        await self.pubsub.publish(f"progress:{session_id}", {
            "status": "progress",
            "message": f"Finding a new meal for {date}..."
        })

        try:
            assistant = await self._get_assistant()
            loop = asyncio.get_event_loop()

            result = await loop.run_in_executor(
                _executor,
                lambda: assistant.planning_agent.swap_meal(
                    meal_plan_id=meal_plan_id,
                    date=date,
                    requirements=requirements
                )
            )

            if result.get("success"):
                # Broadcast meal plan change
                await self.pubsub.publish("state:meal_plan_changed", {
                    "type": "meal_plan_changed",
                    "meal_plan_id": meal_plan_id,
                    "date_changed": date
                })

                # Start background shopping list regeneration
                asyncio.create_task(
                    self._generate_shopping_list_background(session_id, meal_plan_id)
                )

                await self.pubsub.publish(f"progress:{session_id}", {
                    "status": "complete",
                    "message": "Meal swapped!"
                })

            return result

        except Exception as e:
            logger.exception(f"Error swapping meal: {e}")
            await self.pubsub.publish(f"progress:{session_id}", {
                "status": "error",
                "message": str(e)
            })
            raise

    async def get_current_plan(self, meal_plan_id: str) -> Optional[Dict[str, Any]]:
        """
        Get the current meal plan with enriched data.

        Args:
            meal_plan_id: ID of the meal plan

        Returns:
            Dict with plan details or None if not found
        """
        try:
            assistant = await self._get_assistant()
            loop = asyncio.get_event_loop()

            meal_plan = await loop.run_in_executor(
                _executor,
                lambda: assistant.db.get_meal_plan(meal_plan_id)
            )

            if not meal_plan:
                return None

            # Build enriched response
            enriched_meals = []
            for meal in meal_plan.meals:
                meal_dict = meal.to_dict()
                if meal.recipe:
                    meal_dict['recipe_id'] = meal.recipe.id
                    meal_dict['recipe_name'] = meal.recipe.name
                    meal_dict['description'] = meal.recipe.description
                    meal_dict['estimated_time'] = meal.recipe.estimated_time
                    meal_dict['cuisine'] = meal.recipe.cuisine
                    meal_dict['difficulty'] = meal.recipe.difficulty
                    meal_dict['ingredients'] = meal.recipe.ingredients
                    meal_dict['servings'] = meal.recipe.servings
                meal_dict['meal_date'] = meal_dict.pop('date', None)
                enriched_meals.append(meal_dict)

            return {
                "id": meal_plan.id,
                "week_of": meal_plan.week_of,
                "meals": enriched_meals
            }

        except Exception as e:
            logger.exception(f"Error getting plan: {e}")
            raise

    async def search_recipes(
        self,
        query: Optional[str] = None,
        max_time: Optional[int] = None,
        tags: Optional[List[str]] = None,
        limit: int = 20
    ) -> List[Dict[str, Any]]:
        """
        Search for recipes.

        Args:
            query: Search query
            max_time: Maximum cooking time in minutes
            tags: Tags to filter by
            limit: Maximum results

        Returns:
            List of recipe dicts
        """
        try:
            assistant = await self._get_assistant()
            loop = asyncio.get_event_loop()

            recipes = await loop.run_in_executor(
                _executor,
                lambda: assistant.db.search_recipes(
                    query=query,
                    max_time=max_time,
                    tags=tags,
                    limit=limit
                )
            )

            return [recipe.to_dict() for recipe in recipes]

        except Exception as e:
            logger.exception(f"Error searching recipes: {e}")
            raise


# Global service instance
_plan_service: Optional[AsyncPlanService] = None


def get_plan_service() -> AsyncPlanService:
    """Get the global plan service instance."""
    if _plan_service is None:
        raise RuntimeError("Plan service not initialized")
    return _plan_service


def init_plan_service(pubsub: Union[PubSubManager, LocalPubSubManager]) -> AsyncPlanService:
    """Initialize the global plan service."""
    global _plan_service
    _plan_service = AsyncPlanService(pubsub)
    return _plan_service
