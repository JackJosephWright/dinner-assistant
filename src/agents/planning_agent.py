"""
Planning Agent for meal planning.

Uses LangGraph to orchestrate meal planning with MCP tools.
Analyzes user preferences, searches recipes, and generates balanced weekly meal plans.
"""

import logging
import json
from typing import Dict, List, Any, Optional
from datetime import datetime, timedelta
from dataclasses import dataclass

from langchain_anthropic import ChatAnthropic
from langchain_core.messages import HumanMessage, SystemMessage, AIMessage
from langgraph.graph import StateGraph, END
from langgraph.prebuilt import ToolNode

logger = logging.getLogger(__name__)


@dataclass
class PlanningState:
    """State for planning agent workflow."""

    messages: List[Any]
    week_of: str
    num_days: int = 7
    meal_plan: Optional[List[Dict]] = None
    preferences: Optional[Dict] = None
    history: Optional[List[Dict]] = None
    error: Optional[str] = None


class PlanningAgent:
    """Agent for generating weekly meal plans."""

    def __init__(self, mcp_client: Any, model: str = "claude-3-5-sonnet-20241022"):
        """
        Initialize Planning Agent.

        Args:
            mcp_client: MCP client for tool calls
            model: LLM model to use
        """
        self.mcp_client = mcp_client
        self.llm = ChatAnthropic(model=model, temperature=0.7)

        # Build the workflow graph
        self.workflow = self._build_workflow()
        self.app = self.workflow.compile()

        logger.info("Planning Agent initialized")

    def _build_workflow(self) -> StateGraph:
        """Build the LangGraph workflow for meal planning."""

        workflow = StateGraph(PlanningState)

        # Define nodes
        workflow.add_node("gather_context", self._gather_context_node)
        workflow.add_node("generate_plan", self._generate_plan_node)
        workflow.add_node("save_plan", self._save_plan_node)

        # Define edges
        workflow.set_entry_point("gather_context")
        workflow.add_edge("gather_context", "generate_plan")
        workflow.add_edge("generate_plan", "save_plan")
        workflow.add_edge("save_plan", END)

        return workflow

    async def _gather_context_node(self, state: PlanningState) -> PlanningState:
        """Gather user preferences and meal history."""
        try:
            # Get user preferences
            prefs_result = await self.mcp_client.call_tool(
                "get_user_preferences", {}
            )
            state.preferences = json.loads(prefs_result[0].text)

            # Get meal history
            history_result = await self.mcp_client.call_tool(
                "get_meal_history", {"weeks_back": 8}
            )
            state.history = json.loads(history_result[0].text)

            logger.info(
                f"Gathered context: {len(state.history)} historical meals, "
                f"{len(state.preferences)} preferences"
            )

        except Exception as e:
            logger.error(f"Error gathering context: {e}")
            state.error = str(e)

        return state

    async def _generate_plan_node(self, state: PlanningState) -> PlanningState:
        """Generate meal plan using LLM with tool access."""
        try:
            # Build system prompt
            system_prompt = self._build_system_prompt(state)

            # Build user prompt
            user_prompt = self._build_user_prompt(state)

            # Create messages
            messages = [
                SystemMessage(content=system_prompt),
                HumanMessage(content=user_prompt),
            ]

            # Generate plan with tool access
            # For now, we'll do a simple search and selection
            # In a full implementation, this would use LangGraph's tool calling

            # Search for variety of recipes
            recipes = await self._search_diverse_recipes(state)

            # Select recipes for the week
            meal_plan = self._select_weekly_meals(recipes, state)

            state.meal_plan = meal_plan
            logger.info(f"Generated plan with {len(meal_plan)} meals")

        except Exception as e:
            logger.error(f"Error generating plan: {e}")
            state.error = str(e)

        return state

    async def _save_plan_node(self, state: PlanningState) -> PlanningState:
        """Save the generated meal plan."""
        try:
            if not state.meal_plan:
                state.error = "No meal plan to save"
                return state

            # Format meals for save_meal_plan tool
            meals = []
            for meal in state.meal_plan:
                meals.append(
                    {
                        "date": meal["date"],
                        "meal_type": meal.get("meal_type", "dinner"),
                        "recipe_id": meal["recipe_id"],
                        "recipe_name": meal["recipe_name"],
                        "servings": meal.get("servings", 4),
                    }
                )

            # Call save tool
            result = await self.mcp_client.call_tool(
                "save_meal_plan",
                {
                    "week_of": state.week_of,
                    "meals": meals,
                    "preferences_applied": ["variety", "time_constraints"],
                },
            )

            save_result = json.loads(result[0].text)
            if not save_result.get("success"):
                state.error = save_result.get("error", "Unknown error saving plan")
            else:
                logger.info(f"Saved meal plan: {save_result.get('meal_plan_id')}")

        except Exception as e:
            logger.error(f"Error saving plan: {e}")
            state.error = str(e)

        return state

    async def _search_diverse_recipes(
        self, state: PlanningState
    ) -> List[Dict[str, Any]]:
        """Search for diverse recipes across categories."""
        all_recipes = []

        # Get recently used recipe names for exclusion
        recent_names = {meal["recipe_name"].lower() for meal in state.history[:14]}

        # Search different categories
        categories = [
            {"query": "chicken", "tags": None},
            {"query": "salmon", "tags": None},
            {"query": "vegetarian", "tags": ["vegetarian"]},
            {"query": "pasta", "tags": None},
            {"query": "soup", "tags": None},
        ]

        for category in categories:
            try:
                result = await self.mcp_client.call_tool(
                    "search_recipes",
                    {
                        "query": category["query"],
                        "tags": category["tags"],
                        "max_time": 60,
                        "limit": 10,
                    },
                )
                recipes = json.loads(result[0].text)

                # Filter out recently used
                recipes = [
                    r
                    for r in recipes
                    if r["name"].lower() not in recent_names
                ]

                all_recipes.extend(recipes)

            except Exception as e:
                logger.warning(f"Error searching {category['query']}: {e}")

        return all_recipes

    def _select_weekly_meals(
        self, recipes: List[Dict], state: PlanningState
    ) -> List[Dict]:
        """Select meals for the week with variety."""
        if not recipes:
            logger.warning("No recipes available for selection")
            return []

        meal_plan = []

        # Parse week_of date
        week_start = datetime.fromisoformat(state.week_of)

        # Select diverse recipes
        used_cuisines = set()
        recipe_index = 0

        for day in range(state.num_days):
            if recipe_index >= len(recipes):
                recipe_index = 0  # Wrap around if needed

            # Find a recipe with different cuisine
            selected = None
            attempts = 0
            while attempts < len(recipes):
                candidate = recipes[(recipe_index + attempts) % len(recipes)]
                cuisine = candidate.get("cuisine", "other")

                # Prefer different cuisine
                if cuisine not in used_cuisines or len(used_cuisines) >= 3:
                    selected = candidate
                    used_cuisines.add(cuisine)
                    if len(used_cuisines) > 3:
                        used_cuisines.clear()
                    break

                attempts += 1

            if not selected:
                selected = recipes[recipe_index % len(recipes)]

            # Create meal entry
            meal_date = (week_start + timedelta(days=day)).strftime("%Y-%m-%d")
            meal_plan.append(
                {
                    "date": meal_date,
                    "meal_type": "dinner",
                    "recipe_id": selected["id"],
                    "recipe_name": selected["name"],
                    "servings": 4,
                }
            )

            recipe_index += 1

        return meal_plan

    def _build_system_prompt(self, state: PlanningState) -> str:
        """Build system prompt for the LLM."""
        return """You are a meal planning assistant. Your job is to create balanced,
        varied weekly meal plans that respect user preferences and avoid recently used recipes.

        Consider:
        - Variety of cuisines and proteins
        - Cooking time constraints (weeknights vs weekends)
        - User's meal history to avoid repetition
        - Balanced nutrition across the week

        You have access to a large recipe database via the search_recipes tool."""

    def _build_user_prompt(self, state: PlanningState) -> str:
        """Build user prompt for the LLM."""
        recent_meals = [m["recipe_name"] for m in state.history[:14]]

        return f"""Please create a meal plan for the week of {state.week_of}.

        Recent meals to avoid: {', '.join(recent_meals[:10])}

        Generate a plan with {state.num_days} diverse, appealing dinners."""

    async def plan_week(
        self, week_of: str, num_days: int = 7
    ) -> Dict[str, Any]:
        """
        Generate a meal plan for a week.

        Args:
            week_of: ISO date string for Monday of the week (e.g., "2025-01-20")
            num_days: Number of days to plan (default: 7)

        Returns:
            Dictionary with meal plan results
        """
        initial_state = PlanningState(
            messages=[],
            week_of=week_of,
            num_days=num_days,
        )

        try:
            final_state = await self.app.ainvoke(initial_state)

            if final_state.error:
                return {
                    "success": False,
                    "error": final_state.error,
                }

            return {
                "success": True,
                "meal_plan": final_state.meal_plan,
                "week_of": final_state.week_of,
                "num_meals": len(final_state.meal_plan) if final_state.meal_plan else 0,
            }

        except Exception as e:
            logger.error(f"Error planning week: {e}")
            return {
                "success": False,
                "error": str(e),
            }
