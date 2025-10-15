"""
LLM-Powered Cooking Agent using LangGraph.

This agent uses Claude to provide conversational cooking guidance,
replacing the dictionary-based substitution logic with true agentic reasoning.
"""

import logging
import os
from typing import Dict, List, Any, Optional, TypedDict

from langgraph.graph import StateGraph, END
from anthropic import Anthropic

import sys
from pathlib import Path

# Add src to path if needed
if __name__ == "__main__":
    sys.path.insert(0, str(Path(__file__).parent.parent))

from data.database import DatabaseInterface

logger = logging.getLogger(__name__)


class CookingState(TypedDict):
    """State for the cooking agent."""
    recipe_id: str

    # Recipe details
    recipe_name: str
    ingredients: List[str]
    steps: List[str]
    estimated_time: Optional[int]
    difficulty: str
    servings: int

    # LLM-generated guidance
    cooking_tips: List[str]
    timing_breakdown: Dict[str, Any]
    formatted_instructions: str

    # Error handling
    error: Optional[str]


class AgenticCookingAgent:
    """LLM-powered agent for providing cooking guidance."""

    def __init__(self, db: DatabaseInterface, api_key: Optional[str] = None):
        """
        Initialize Cooking Agent with LLM.

        Args:
            db: Database interface instance
            api_key: Anthropic API key (or from env)
        """
        self.db = db

        # Initialize Anthropic client
        api_key = api_key or os.environ.get("ANTHROPIC_API_KEY")
        if not api_key:
            raise ValueError(
                "ANTHROPIC_API_KEY required for agentic cooking. "
                "Set environment variable or pass api_key parameter."
            )

        self.client = Anthropic(api_key=api_key)
        self.model = "claude-sonnet-4-5-20250929"

        # Build the LangGraph workflow
        self.graph = self._build_graph()

        logger.info("Agentic Cooking Agent initialized with LLM")

    def _build_graph(self) -> StateGraph:
        """Build the LangGraph state graph for cooking guidance workflow."""

        workflow = StateGraph(CookingState)

        # Add nodes
        workflow.add_node("load_recipe", self._load_recipe_node)
        workflow.add_node("generate_tips", self._generate_tips_node)
        workflow.add_node("analyze_timing", self._analyze_timing_node)
        workflow.add_node("format_instructions", self._format_instructions_node)

        # Define edges
        workflow.set_entry_point("load_recipe")
        workflow.add_edge("load_recipe", "generate_tips")
        workflow.add_edge("generate_tips", "analyze_timing")
        workflow.add_edge("analyze_timing", "format_instructions")
        workflow.add_edge("format_instructions", END)

        return workflow.compile()

    def get_cooking_guide(self, recipe_id: str) -> Dict[str, Any]:
        """
        Get a complete cooking guide for a recipe using LLM reasoning.

        Uses a cache to avoid regenerating guides for the same recipe.

        Args:
            recipe_id: Recipe ID

        Returns:
            Cooking guide dictionary
        """
        try:
            # Check cache first
            cached_guide = self.db.get_cached_cooking_guide(recipe_id, self.model)
            if cached_guide:
                logger.info(f"Using cached cooking guide for recipe {recipe_id}")
                return cached_guide

            # Generate new guide
            logger.info(f"Generating new cooking guide for recipe {recipe_id}")

            # Initialize state
            initial_state = CookingState(
                recipe_id=recipe_id,
                recipe_name="",
                ingredients=[],
                steps=[],
                estimated_time=None,
                difficulty="",
                servings=0,
                cooking_tips=[],
                timing_breakdown={},
                formatted_instructions="",
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

            guide = {
                "success": True,
                "recipe_name": final_state["recipe_name"],
                "servings": final_state["servings"],
                "estimated_time": final_state["estimated_time"],
                "difficulty": final_state["difficulty"],
                "ingredients": final_state["ingredients"],
                "steps": final_state["steps"],
                "tips": final_state["cooking_tips"],
                "timing_breakdown": final_state["timing_breakdown"],
            }

            # Cache the guide for future use
            self.db.save_cooking_guide(recipe_id, self.model, guide)

            return guide

        except Exception as e:
            logger.error(f"Error getting cooking guide: {e}", exc_info=True)
            return {
                "success": False,
                "error": str(e),
            }

    def _load_recipe_node(self, state: CookingState) -> CookingState:
        """
        LangGraph node: Load recipe details from database.
        """
        try:
            recipe = self.db.get_recipe(state["recipe_id"])

            if not recipe:
                state["error"] = "Recipe not found"
                return state

            state["recipe_name"] = recipe.name
            state["ingredients"] = recipe.ingredients_raw
            state["steps"] = recipe.steps
            state["estimated_time"] = recipe.estimated_time
            state["difficulty"] = recipe.difficulty
            state["servings"] = recipe.servings

            logger.info(f"Loaded recipe: {recipe.name}")

            return state

        except Exception as e:
            logger.error(f"Error in load_recipe_node: {e}")
            state["error"] = f"Recipe loading failed: {str(e)}"
            return state

    def _generate_tips_node(self, state: CookingState) -> CookingState:
        """
        LangGraph node: Use LLM to generate contextual cooking tips.

        The LLM provides tips based on difficulty, ingredients, and cooking methods.
        """
        try:
            # Format recipe for LLM
            ingredients_text = "\n".join([f"- {ing}" for ing in state["ingredients"][:20]])
            steps_text = "\n".join([f"{i+1}. {step}" for i, step in enumerate(state["steps"][:10])])

            prompt = f"""You are an experienced cooking instructor. Please provide 3-5 helpful cooking tips for this recipe:

Recipe: {state['recipe_name']}
Difficulty: {state['difficulty']}
Estimated Time: {state['estimated_time'] or '?'} minutes
Servings: {state['servings']}

Ingredients:
{ingredients_text}

Steps (preview):
{steps_text}

Please provide practical tips that will help someone successfully cook this dish. Consider:
- Important techniques or timing
- Common mistakes to avoid
- Tips specific to the difficulty level
- Advice about key ingredients
- Prep work recommendations

Format as a simple list, one tip per line."""

            response = self.client.messages.create(
                model=self.model,
                max_tokens=1024,
                messages=[{"role": "user", "content": prompt}]
            )

            tips_text = response.content[0].text

            # Parse tips (each line is a tip)
            tips = []
            for line in tips_text.split("\n"):
                line = line.strip()
                # Remove leading bullets/numbers
                line = line.lstrip("- •*0123456789. ")
                if line and len(line) > 10:  # Avoid empty or too-short lines
                    tips.append(line)

            state["cooking_tips"] = tips[:5]  # Max 5 tips
            logger.info(f"Generated {len(tips)} cooking tips")

            return state

        except Exception as e:
            logger.error(f"Error in generate_tips_node: {e}")
            state["cooking_tips"] = ["Follow the recipe steps carefully"]
            return state

    def _analyze_timing_node(self, state: CookingState) -> CookingState:
        """
        LangGraph node: Use LLM to analyze timing breakdown.

        The LLM provides intelligent timing estimates for prep vs cook.
        """
        try:
            steps_text = "\n".join([f"{i+1}. {step}" for i, step in enumerate(state["steps"])])

            prompt = f"""You are a cooking instructor analyzing timing for this recipe:

Recipe: {state['recipe_name']}
Total Estimated Time: {state['estimated_time'] or '?'} minutes

Steps:
{steps_text}

Please analyze the timing and provide:
1. Estimated prep time (in minutes)
2. Estimated active cooking time (in minutes)
3. Any passive/waiting time (e.g., marinating, baking)

Format your response as:
PREP: X minutes
COOK: X minutes
PASSIVE: X minutes (if any)

Be practical and realistic based on the steps described."""

            response = self.client.messages.create(
                model=self.model,
                max_tokens=512,
                messages=[{"role": "user", "content": prompt}]
            )

            timing_text = response.content[0].text

            # Parse timing
            timing_breakdown = {
                "total_time": state["estimated_time"] or 30,
                "prep_time": 0,
                "cook_time": 0,
                "passive_time": 0,
            }

            for line in timing_text.split("\n"):
                line = line.upper().strip()
                if "PREP:" in line:
                    try:
                        timing_breakdown["prep_time"] = int(line.split(":")[1].split()[0])
                    except (ValueError, IndexError):
                        pass
                elif "COOK:" in line:
                    try:
                        timing_breakdown["cook_time"] = int(line.split(":")[1].split()[0])
                    except (ValueError, IndexError):
                        pass
                elif "PASSIVE:" in line:
                    try:
                        timing_breakdown["passive_time"] = int(line.split(":")[1].split()[0])
                    except (ValueError, IndexError):
                        pass

            state["timing_breakdown"] = timing_breakdown
            logger.info(f"Analyzed timing: {timing_breakdown}")

            return state

        except Exception as e:
            logger.error(f"Error in analyze_timing_node: {e}")
            state["timing_breakdown"] = {
                "total_time": state["estimated_time"] or 30,
                "prep_time": 10,
                "cook_time": 20,
                "passive_time": 0,
            }
            return state

    def _format_instructions_node(self, state: CookingState) -> CookingState:
        """
        LangGraph node: Format instructions for display (simple formatting).
        """
        # This node just stores a flag - actual formatting is done by format_cooking_instructions
        state["formatted_instructions"] = "ready"
        return state

    def get_substitutions(self, ingredient: str, reason: Optional[str] = None) -> Dict[str, Any]:
        """
        Get ingredient substitution suggestions using LLM reasoning.

        Args:
            ingredient: Ingredient name
            reason: Optional reason for substitution

        Returns:
            Substitution suggestions
        """
        try:
            reason_text = f" (reason: {reason})" if reason else ""

            prompt = f"""You are a cooking expert. Please suggest 3-5 practical substitutions for this ingredient:

Ingredient: {ingredient}{reason_text}

Provide substitutions that:
1. Work well in most recipes
2. Are commonly available
3. Match the reason if provided (e.g., dairy-free, vegan, allergy)
4. Maintain similar cooking properties

Format as a simple list, one substitution per line with a brief note.

Example format:
- coconut milk (1:1 ratio, works well in most recipes)
- almond milk (slightly thinner, good for baking)"""

            response = self.client.messages.create(
                model=self.model,
                max_tokens=512,
                messages=[{"role": "user", "content": prompt}]
            )

            substitutions_text = response.content[0].text

            # Parse substitutions
            substitutions = []
            for line in substitutions_text.split("\n"):
                line = line.strip().lstrip("- •*0123456789. ")
                if line and len(line) > 5:
                    substitutions.append(line)

            return {
                "success": True,
                "ingredient": ingredient,
                "substitutions": substitutions[:5],
                "reason": reason,
            }

        except Exception as e:
            logger.error(f"Error getting substitutions: {e}")
            return {
                "success": False,
                "error": str(e),
            }

    def format_cooking_instructions(self, recipe_id: str) -> str:
        """
        Format recipe as step-by-step cooking instructions using LLM.

        Args:
            recipe_id: Recipe ID

        Returns:
            Formatted cooking instructions
        """
        guide = self.get_cooking_guide(recipe_id)

        if not guide.get("success"):
            return f"Error: {guide.get('error')}"

        # Ask LLM to format nicely
        try:
            ingredients_text = "\n".join(guide["ingredients"])
            steps_text = "\n".join([f"{i+1}. {step}" for i, step in enumerate(guide["steps"])])
            tips_text = "\n".join([f"- {tip}" for tip in guide["tips"]])

            timing = guide.get("timing_breakdown", {})
            timing_text = f"""
Total Time: {timing.get('total_time', '?')} minutes
  - Prep: {timing.get('prep_time', '?')} min
  - Cook: {timing.get('cook_time', '?')} min
  - Passive: {timing.get('passive_time', 0)} min
"""

            prompt = f"""You are a cooking instructor. Please format these recipe instructions in a clear, friendly, and easy-to-follow way:

Recipe: {guide['recipe_name']}
Servings: {guide['servings']}
Difficulty: {guide['difficulty'].title()}

{timing_text}

Tips:
{tips_text}

Ingredients:
{ingredients_text}

Instructions:
{steps_text}

Please create a well-formatted recipe guide that's easy to follow while cooking. Use clear headers, emojis for visual interest, and organize the information logically. Keep it concise and scannable."""

            response = self.client.messages.create(
                model=self.model,
                max_tokens=2048,
                messages=[{"role": "user", "content": prompt}]
            )

            formatted_instructions = response.content[0].text

            return formatted_instructions

        except Exception as e:
            logger.error(f"Error formatting with LLM: {e}")

            # Fallback to simple format
            lines = [
                f"🍳 {guide['recipe_name']}",
                f"{'='*60}",
                f"⏱️  Time: {guide['estimated_time'] or '?'} minutes",
                f"🍽️  Servings: {guide['servings']}",
                f"📊 Difficulty: {guide['difficulty'].title()}",
                "",
            ]

            # Tips
            if guide.get("tips"):
                lines.append("💡 Tips:")
                for tip in guide["tips"]:
                    lines.append(f"   {tip}")
                lines.append("")

            # Ingredients
            lines.append("📋 Ingredients:")
            for i, ingredient in enumerate(guide["ingredients"], 1):
                lines.append(f"   {i}. {ingredient}")
            lines.append("")

            # Steps
            lines.append("👨‍🍳 Instructions:")
            for i, step in enumerate(guide["steps"], 1):
                lines.append(f"   Step {i}:")
                lines.append(f"   {step}")
                lines.append("")

            return "\n".join(lines)
