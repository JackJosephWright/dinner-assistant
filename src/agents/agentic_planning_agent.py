"""
LLM-Powered Planning Agent using LangGraph.

This agent uses Claude to reason about meal planning decisions,
replacing the algorithmic scoring approach with true agentic reasoning.
"""

import logging
import os
from typing import Dict, List, Any, Optional, TypedDict, Annotated
from datetime import datetime, timedelta
import operator

from langgraph.graph import StateGraph, END
from anthropic import Anthropic

import sys
from pathlib import Path

# Add src to path if needed
if __name__ == "__main__":
    sys.path.insert(0, str(Path(__file__).parent.parent))

from data.database import DatabaseInterface
from data.models import MealPlan, PlannedMeal, Recipe

logger = logging.getLogger(__name__)


class PlanningState(TypedDict):
    """State for the meal planning agent."""
    week_of: str
    num_days: int
    preferences: Dict[str, Any]

    # Analysis results
    history_summary: Optional[str]
    recent_meals: List[str]
    favorite_patterns: Optional[str]

    # Recipe search results
    recipe_candidates: List[Dict[str, Any]]

    # Final selections
    selected_meals: List[Dict[str, Any]]
    reasoning: str

    # Error handling
    error: Optional[str]


class AgenticPlanningAgent:
    """LLM-powered agent for generating intelligent weekly meal plans."""

    def __init__(self, db: DatabaseInterface, api_key: Optional[str] = None, progress_callback=None, verbose_callback=None):
        """
        Initialize Planning Agent with LLM.

        Args:
            db: Database interface instance
            api_key: Anthropic API key (or from env)
            progress_callback: Optional callback function for progress updates
            verbose_callback: Optional callback for verbose/debug output (AI reasoning)
        """
        self.db = db
        self.progress_callback = progress_callback
        self.verbose_callback = verbose_callback

        # Initialize Anthropic client
        api_key = api_key or os.environ.get("ANTHROPIC_API_KEY")
        if not api_key:
            raise ValueError(
                "ANTHROPIC_API_KEY required for agentic planning. "
                "Set environment variable or pass api_key parameter."
            )

        self.client = Anthropic(api_key=api_key)
        self.model = "claude-sonnet-4-5-20250929"

        # Build the LangGraph workflow
        self.graph = self._build_graph()

        logger.info("Agentic Planning Agent initialized with LLM")

    def _verbose_output(self, message: str):
        """Send verbose output to both logger and callback if enabled."""
        logger.info(message)
        if self.verbose_callback:
            self.verbose_callback(message)

    def _build_graph(self) -> StateGraph:
        """Build the LangGraph state graph for planning workflow."""

        # Define the workflow
        workflow = StateGraph(PlanningState)

        # Add nodes
        workflow.add_node("analyze_history", self._analyze_history_node)
        workflow.add_node("search_recipes", self._search_recipes_node)
        workflow.add_node("select_meals", self._select_meals_node)

        # Define edges
        workflow.set_entry_point("analyze_history")
        workflow.add_edge("analyze_history", "search_recipes")
        workflow.add_edge("search_recipes", "select_meals")
        workflow.add_edge("select_meals", END)

        return workflow.compile()

    def plan_week(
        self,
        week_of: str,
        num_days: int = 7,
        preferences: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Generate a meal plan for a week using LLM reasoning.

        Args:
            week_of: ISO date string for Monday (e.g., "2025-01-20")
            num_days: Number of days to plan (default: 7)
            preferences: Optional preferences override

        Returns:
            Dictionary with meal plan results
        """
        try:
            # Load preferences
            if preferences is None:
                preferences = self._get_preferences()

            # Initialize state
            initial_state = PlanningState(
                week_of=week_of,
                num_days=num_days,
                preferences=preferences,
                history_summary=None,
                recent_meals=[],
                favorite_patterns=None,
                recipe_candidates=[],
                selected_meals=[],
                reasoning="",
                error=None,
            )

            # Run the graph
            final_state = self.graph.invoke(initial_state)

            # Check for errors
            if final_state.get("error"):
                return {
                    "success": False,
                    "error": final_state["error"],
                }

            # Convert selected meals to PlannedMeal objects
            meals = []
            week_start = datetime.fromisoformat(week_of)

            for i, meal_data in enumerate(final_state["selected_meals"]):
                meal_date = (week_start + timedelta(days=i)).strftime("%Y-%m-%d")

                # Load full Recipe object from database
                recipe = self.db.get_recipe(meal_data["recipe_id"])
                if not recipe:
                    logger.error(f"Recipe {meal_data['recipe_id']} not found in database")
                    continue

                meals.append(
                    PlannedMeal(
                        date=meal_date,
                        meal_type="dinner",
                        recipe=recipe,
                        servings=meal_data.get("servings", 4),
                    )
                )

            # Save the meal plan
            meal_plan = MealPlan(
                week_of=week_of,
                meals=meals,
                preferences_applied=list(preferences.keys()),
            )

            plan_id = self.db.save_meal_plan(meal_plan)

            logger.info(f"Generated meal plan {plan_id} with {len(meals)} meals using LLM")

            return {
                "success": True,
                "meal_plan_id": plan_id,
                "week_of": week_of,
                "meals": [
                    {
                        "date": m.date,
                        "recipe_name": m.recipe.name,
                        "recipe_id": m.recipe.id,
                        "servings": m.servings,
                    }
                    for m in meals
                ],
                "reasoning": final_state["reasoning"],
                "preferences_applied": list(preferences.keys()),
            }

        except Exception as e:
            logger.error(f"Error planning week: {e}", exc_info=True)
            return {
                "success": False,
                "error": str(e),
            }

    def _analyze_history_node(self, state: PlanningState) -> PlanningState:
        """
        LangGraph node: Analyze meal history using LLM.

        The LLM reasons about user preferences from historical data.
        """
        try:
            # Emit progress
            if self.progress_callback:
                self.progress_callback("Analyzing your meal preferences...")

            # Get meal history
            history = self.db.get_meal_history(weeks_back=8)
            recent_history = self.db.get_meal_history(weeks_back=2)

            if not history:
                state["history_summary"] = "No meal history available - user is new."
                state["recent_meals"] = []
                state["favorite_patterns"] = "No patterns detected."
                return state

            # Format history for LLM
            history_text = "\n".join([f"- {m.recipe.name}" for m in history[:30]])
            recent_text = "\n".join([f"- {m.recipe.name}" for m in recent_history])

            # Ask LLM to analyze patterns
            prompt = f"""You are a meal planning assistant analyzing a user's meal history.

Recent meals (last 2 weeks):
{recent_text}

Historical meals (last 8 weeks, sample):
{history_text}

Please analyze this data and provide:
1. A brief summary of the user's preferences (cuisines, proteins, cooking styles)
2. Key patterns you notice (e.g., "enjoys Mexican food on weeknights", "frequently has salmon")
3. Suggestions for variety based on what they haven't had recently

Be concise but insightful. Focus on actionable patterns for meal planning."""

            response = self.client.messages.create(
                model=self.model,
                max_tokens=1024,
                messages=[{"role": "user", "content": prompt}]
            )

            analysis = response.content[0].text

            # Store results
            state["history_summary"] = analysis
            state["recent_meals"] = [m.recipe.name for m in recent_history]
            state["favorite_patterns"] = analysis

            logger.info("LLM analyzed meal history")

            return state

        except Exception as e:
            logger.error(f"Error in analyze_history_node: {e}")
            state["error"] = f"History analysis failed: {str(e)}"
            return state

    def _search_recipes_node(self, state: PlanningState) -> PlanningState:
        """
        LangGraph node: Search for recipe candidates using LLM guidance.

        The LLM decides what to search for based on history analysis.
        """
        try:
            # Emit progress
            if self.progress_callback:
                self.progress_callback("Searching for recipe candidates...")

            preferences = state["preferences"]
            history_summary = state.get("history_summary", "")

            # Ask LLM what to search for
            prompt = f"""You are a meal planning assistant. Based on this user analysis:

{history_summary}

And these preferences:
- Max weeknight cooking time: {preferences.get('max_weeknight_time', 45)} minutes
- Max weekend cooking time: {preferences.get('max_weekend_time', 90)} minutes
- Preferred cuisines: {preferences.get('preferred_cuisines', [])}
- Minimum vegetarian meals: {preferences.get('min_vegetarian_meals', 1)}

The user needs {state['num_days']} meals planned.

Please provide 5-7 simple search keywords to find diverse recipe candidates.
Use SHORT, SIMPLE keywords (1-2 words) that work well for database search.

Format each line EXACTLY as: KEYWORD | REASON

Example:
salmon | User frequently enjoys salmon dishes
tofu | Need vegetarian options, user likes tofu
chicken | Weeknight protein staple
pasta | Quick Italian comfort food

Keep keywords simple and searchable. Do NOT use complex phrases."""

            response = self.client.messages.create(
                model=self.model,
                max_tokens=1024,
                messages=[{"role": "user", "content": prompt}]
            )

            search_plan = response.content[0].text
            self._verbose_output(f"🔍 AI Search Plan:\n{search_plan}")

            # Parse search queries and execute them
            recipe_candidates = []
            recent_meal_names = set(m.lower() for m in state["recent_meals"])

            for line in search_plan.split("\n"):
                # Skip comments, headers, and empty lines
                line = line.strip()
                if not line or line.startswith("#") or line.startswith("**") or ":" not in line and "|" not in line:
                    continue

                # Extract keyword - could be in format "**keyword**" or "keyword |"
                keyword = ""
                reason = ""

                if "|" in line:
                    parts = line.split("|")
                    keyword = parts[0].strip()
                    reason = parts[1].strip() if len(parts) > 1 else ""
                elif ":" in line:
                    # Handle format like "tofu stir fry: reason"
                    parts = line.split(":", 1)
                    keyword = parts[0].strip()
                    reason = parts[1].strip() if len(parts) > 1 else ""

                # Clean up markdown formatting
                keyword = keyword.replace("**", "").replace("*", "").strip()

                # Skip if keyword is empty or too short
                if not keyword or len(keyword) < 3:
                    continue

                # Search database
                max_time = preferences.get("max_weeknight_time", 45)
                recipes = self.db.search_recipes(
                    query=keyword,
                    max_time=max_time,
                    limit=15,
                )

                # Filter out recent meals (but not too aggressively)
                filtered_recipes = [r for r in recipes if r.name.lower() not in recent_meal_names]

                # If filtering removed everything, use unfiltered results
                # (better to repeat a meal than have no options)
                if not filtered_recipes and recipes:
                    logger.warning(f"All recipes for '{keyword}' were recent meals, using them anyway")
                    filtered_recipes = recipes

                # Add to candidates with metadata
                for recipe in filtered_recipes[:5]:  # Top 5 per search
                    recipe_candidates.append({
                        "recipe_id": recipe.id,
                        "recipe_name": recipe.name,
                        "cuisine": recipe.cuisine,
                        "difficulty": recipe.difficulty,
                        "estimated_time": recipe.estimated_time,
                        "search_keyword": keyword,
                        "search_reason": reason,
                    })

            # Deduplicate candidates by recipe_id
            seen_ids = set()
            unique_candidates = []
            for candidate in recipe_candidates:
                if candidate["recipe_id"] not in seen_ids:
                    seen_ids.add(candidate["recipe_id"])
                    unique_candidates.append(candidate)

            state["recipe_candidates"] = unique_candidates
            self._verbose_output(f"✓ Found {len(unique_candidates)} recipe candidates")

            return state

        except Exception as e:
            logger.error(f"Error in search_recipes_node: {e}")
            state["error"] = f"Recipe search failed: {str(e)}"
            return state

    def _select_meals_node(self, state: PlanningState) -> PlanningState:
        """
        LangGraph node: LLM selects specific meals for each day.

        The LLM reasons about variety, balance, and preferences to make final selections.
        """
        try:
            # Emit progress
            if self.progress_callback:
                self.progress_callback("Selecting the best meals for your week...")

            candidates = state["recipe_candidates"]
            num_days = state["num_days"]
            week_of = state["week_of"]
            history_summary = state.get("history_summary", "")

            if not candidates:
                state["error"] = "No recipe candidates found"
                return state

            # Format candidates for LLM
            candidates_text = ""
            for i, candidate in enumerate(candidates[:50]):  # Limit to 50 for token efficiency
                candidates_text += f"{i+1}. {candidate['recipe_name']}\n"
                candidates_text += f"   ID: {candidate['recipe_id']}\n"
                candidates_text += f"   Cuisine: {candidate.get('cuisine', 'unknown')}, "
                candidates_text += f"Time: {candidate.get('estimated_time', '?')} min, "
                candidates_text += f"Difficulty: {candidate.get('difficulty', 'unknown')}\n"
                candidates_text += f"   Why: {candidate.get('search_reason', '')}\n\n"

            # Ask LLM to select meals
            week_start = datetime.fromisoformat(week_of)
            days_list = []
            for i in range(num_days):
                date = week_start + timedelta(days=i)
                day_name = date.strftime("%A")
                is_weekend = date.weekday() >= 5
                days_list.append(f"{day_name} ({date.strftime('%Y-%m-%d')}) - {'Weekend' if is_weekend else 'Weeknight'}")

            days_text = "\n".join(days_list)

            prompt = f"""You are a meal planning assistant. Please select {num_days} meals for this week:

{days_text}

User Context:
{history_summary}

Available Recipe Candidates:
{candidates_text}

Please select one recipe for each day, ensuring:
1. Good variety across the week (different cuisines, proteins, cooking styles)
2. Appropriate difficulty for weeknights vs weekends
3. No repeated recipes
4. Balance that reflects user preferences

For each day, provide:
- The recipe NUMBER from the list above (just the number)
- Brief reasoning (one sentence)

Format exactly as:
DAY 1: NUMBER | REASONING
DAY 2: NUMBER | REASONING
...

Example:
DAY 1: 5 | Quick salmon dish perfect for Monday, user loves salmon
DAY 2: 12 | Different protein (chicken), still weeknight-friendly"""

            response = self.client.messages.create(
                model=self.model,
                max_tokens=2048,
                messages=[{"role": "user", "content": prompt}]
            )

            selection_text = response.content[0].text
            self._verbose_output(f"🎯 AI Meal Selections:\n{selection_text}")

            # Parse LLM selections
            selected_meals = []
            reasoning_parts = []

            for line in selection_text.split("\n"):
                if not line.strip() or "DAY" not in line:
                    continue

                try:
                    # Parse: "DAY 1: 5 | Reasoning here"
                    if ":" not in line:
                        continue

                    parts = line.split(":", 1)[1].strip()
                    if "|" not in parts:
                        continue

                    number_str, reason = parts.split("|", 1)
                    number = int(number_str.strip()) - 1  # Convert to 0-indexed

                    if 0 <= number < len(candidates):
                        candidate = candidates[number]
                        selected_meals.append(candidate)
                        reasoning_parts.append(f"- {candidate['recipe_name']}: {reason.strip()}")

                except (ValueError, IndexError) as e:
                    logger.warning(f"Failed to parse selection line: {line} - {e}")
                    continue

            # Fallback if parsing failed
            if len(selected_meals) < num_days:
                logger.warning(f"Only parsed {len(selected_meals)} meals, using fallback for remaining")
                # Add random candidates to fill
                used_ids = {m["recipe_id"] for m in selected_meals}
                for candidate in candidates:
                    if len(selected_meals) >= num_days:
                        break
                    if candidate["recipe_id"] not in used_ids:
                        selected_meals.append(candidate)
                        used_ids.add(candidate["recipe_id"])
                        reasoning_parts.append(f"- {candidate['recipe_name']}: Fallback selection")

            state["selected_meals"] = selected_meals[:num_days]
            state["reasoning"] = "\n".join(reasoning_parts)

            logger.info(f"Selected {len(state['selected_meals'])} meals")

            return state

        except Exception as e:
            logger.error(f"Error in select_meals_node: {e}")
            state["error"] = f"Meal selection failed: {str(e)}"
            return state

    def _get_preferences(self) -> Dict[str, Any]:
        """Load user preferences."""
        prefs = self.db.get_all_preferences()

        # Default preferences
        defaults = {
            "variety_window_weeks": 2,
            "max_weeknight_time": 45,
            "max_weekend_time": 90,
            "preferred_cuisines": ["italian", "mexican", "asian"],
            "min_vegetarian_meals": 1,
        }

        # Merge with stored preferences
        for key, value in prefs.items():
            try:
                if key.endswith("_time") or key.endswith("_weeks") or key.endswith("_meals"):
                    defaults[key] = int(value)
                elif key.endswith("_cuisines"):
                    defaults[key] = value.split(",")
            except (ValueError, AttributeError):
                defaults[key] = value

        return defaults

    def swap_meal(
        self,
        meal_plan_id: str,
        date: str,
        requirements: str,
    ) -> Dict[str, Any]:
        """
        Swap a meal in an existing plan using LLM to find a suitable replacement.

        Args:
            meal_plan_id: ID of meal plan to modify
            date: Date of meal to swap (YYYY-MM-DD)
            requirements: User's requirements for the replacement (e.g., "shellfish dish", "vegetarian")

        Returns:
            Dictionary with swap result
        """
        try:
            # Get the meal plan
            meal_plan = self.db.get_meal_plan(meal_plan_id)
            if not meal_plan:
                return {"success": False, "error": "Meal plan not found"}

            # Find the meal to swap
            meal_to_swap = None
            for meal in meal_plan.meals:
                if meal.date == date:
                    meal_to_swap = meal
                    break

            if not meal_to_swap:
                return {"success": False, "error": f"No meal found for date {date}"}

            # Get day of week info
            date_obj = datetime.fromisoformat(date)
            day_name = date_obj.strftime("%A")
            is_weekend = date_obj.weekday() >= 5

            # Get preferences
            preferences = self._get_preferences()
            max_time = (
                preferences.get("max_weekend_time", 90)
                if is_weekend
                else preferences.get("max_weeknight_time", 45)
            )

            # Emit progress
            if self.progress_callback:
                self.progress_callback("Finding replacement options...")

            # Ask LLM to determine search queries for the replacement
            prompt = f"""You are a meal planning assistant. The user wants to swap a meal in their plan.

Current meal: {meal_to_swap.recipe.name} on {day_name}, {date}
Day type: {'Weekend' if is_weekend else 'Weeknight'}
Max cooking time: {max_time} minutes

User's requirements for replacement: {requirements}

Please provide 3-5 search queries to find suitable replacement recipes.
Each query should be a specific keyword or phrase.

Format as one keyword per line. Examples:
shrimp
garlic butter scallops
seafood pasta
shellfish"""

            response = self.client.messages.create(
                model=self.model,
                max_tokens=512,
                messages=[{"role": "user", "content": prompt}]
            )

            search_queries_text = response.content[0].text
            logger.info(f"LLM swap search queries:\n{search_queries_text}")

            # Execute searches
            candidates = []
            recent_meal_names = {m.recipe.name.lower() for m in meal_plan.meals if m.date != date}

            for line in search_queries_text.split("\n"):
                keyword = line.strip()
                if not keyword or len(keyword) < 3:
                    continue

                # Search recipes
                recipes = self.db.search_recipes(
                    query=keyword,
                    max_time=max_time,
                    limit=10,
                )

                # Filter out meals already in the plan
                for recipe in recipes:
                    if recipe.name.lower() not in recent_meal_names:
                        candidates.append({
                            "recipe_id": recipe.id,
                            "recipe_name": recipe.name,
                            "cuisine": recipe.cuisine,
                            "difficulty": recipe.difficulty,
                            "estimated_time": recipe.estimated_time,
                        })

            if not candidates:
                return {"success": False, "error": "No suitable replacement recipes found"}

            # Deduplicate
            seen_ids = set()
            unique_candidates = []
            for candidate in candidates:
                if candidate["recipe_id"] not in seen_ids:
                    seen_ids.add(candidate["recipe_id"])
                    unique_candidates.append(candidate)

            # Emit progress
            if self.progress_callback:
                self.progress_callback("Selecting best replacement...")

            # Ask LLM to pick the best one
            candidates_text = ""
            for i, candidate in enumerate(unique_candidates[:20]):
                candidates_text += f"{i+1}. {candidate['recipe_name']}\n"
                candidates_text += f"   ID: {candidate['recipe_id']}, "
                candidates_text += f"Cuisine: {candidate.get('cuisine', 'unknown')}, "
                candidates_text += f"Time: {candidate.get('estimated_time', '?')} min\n\n"

            selection_prompt = f"""You are a meal planning assistant. Please select the BEST replacement for:

Original meal: {meal_to_swap.recipe.name}
Day: {day_name} ({'Weekend' if is_weekend else 'Weeknight'})
User wants: {requirements}

Available options:
{candidates_text}

Pick the single best option that matches the user's requirements.

Respond with ONLY the number (1-{len(unique_candidates[:20])}) of your choice, followed by a brief reason.

Format: NUMBER | REASON

Example: 5 | Perfect shellfish dish with quick weeknight prep time"""

            response = self.client.messages.create(
                model=self.model,
                max_tokens=256,
                messages=[{"role": "user", "content": selection_prompt}]
            )

            selection_text = response.content[0].text.strip()
            logger.info(f"LLM selection: {selection_text}")

            # Parse selection
            if "|" not in selection_text:
                # Fallback to first candidate
                selected = unique_candidates[0]
                reason = "Default selection"
            else:
                try:
                    number_str, reason = selection_text.split("|", 1)
                    number = int(number_str.strip()) - 1
                    if 0 <= number < len(unique_candidates):
                        selected = unique_candidates[number]
                        reason = reason.strip()
                    else:
                        selected = unique_candidates[0]
                        reason = "Default selection"
                except (ValueError, IndexError):
                    selected = unique_candidates[0]
                    reason = "Default selection"

            # Perform the swap
            updated_plan = self.db.swap_meal_in_plan(
                meal_plan_id, date, selected["recipe_id"]
            )

            if not updated_plan:
                return {"success": False, "error": "Failed to update meal plan"}

            return {
                "success": True,
                "meal_plan_id": meal_plan_id,
                "date": date,
                "old_recipe": meal_to_swap.recipe.name,
                "new_recipe": selected["recipe_name"],
                "new_recipe_id": selected["recipe_id"],
                "reason": reason,
            }

        except Exception as e:
            logger.error(f"Error swapping meal: {e}", exc_info=True)
            return {"success": False, "error": str(e)}

    def explain_plan(self, meal_plan_id: str) -> str:
        """
        Generate a human-readable explanation of a meal plan using LLM.

        Args:
            meal_plan_id: ID of saved meal plan

        Returns:
            Explanation text
        """
        plan = self.db.get_meal_plan(meal_plan_id)

        if not plan:
            return "Meal plan not found."

        # Format meal plan for LLM
        meals_text = ""
        for meal in plan.meals:
            recipe = meal.recipe
            if recipe:
                date_obj = datetime.fromisoformat(meal.date)
                day_name = date_obj.strftime("%A")
                meals_text += f"{day_name}, {meal.date}: {recipe.name}\n"
                meals_text += f"  ({recipe.estimated_time or '?'} min, {recipe.difficulty}, {recipe.cuisine or 'unknown cuisine'})\n\n"

        # Ask LLM to explain the plan
        prompt = f"""You are a meal planning assistant. Please provide a friendly, conversational explanation of this meal plan:

Week of {plan.week_of}:

{meals_text}

Explain:
1. The overall variety and balance
2. Why this is a good week of meals
3. Any patterns (cuisine diversity, cooking times, etc.)

Keep it concise and friendly - 2-3 short paragraphs."""

        try:
            response = self.client.messages.create(
                model=self.model,
                max_tokens=1024,
                messages=[{"role": "user", "content": prompt}]
            )

            explanation = response.content[0].text

            # Add the meal list
            full_explanation = f"Meal Plan for Week of {plan.week_of}\n{'='*50}\n\n"
            full_explanation += meals_text
            full_explanation += "\n" + explanation

            return full_explanation

        except Exception as e:
            logger.error(f"Error explaining plan: {e}")
            # Fallback to simple list
            return f"Meal Plan for Week of {plan.week_of}\n{'='*50}\n\n{meals_text}"
