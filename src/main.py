#!/usr/bin/env python3
"""
Main orchestrator for the Meal Planning Assistant.

Coordinates Planning, Shopping, and Cooking agents.
"""

import logging
import argparse
import os
from datetime import datetime, timedelta
from typing import Optional

from data.database import DatabaseInterface

# Try to import agentic agents first (LLM-powered)
try:
    from agents.agentic_planning_agent import AgenticPlanningAgent
    from agents.agentic_shopping_agent import AgenticShoppingAgent
    from agents.agentic_cooking_agent import AgenticCookingAgent
    AGENTIC_AVAILABLE = bool(os.environ.get("ANTHROPIC_API_KEY"))
except ImportError:
    AGENTIC_AVAILABLE = False

# Fallback to algorithmic agents
from agents.enhanced_planning_agent import EnhancedPlanningAgent
from agents.cooking_agent import CookingAgent
# Note: ShoppingAgent was removed - always use AgenticShoppingAgent

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


class MealPlanningAssistant:
    """Main orchestrator for the meal planning system."""

    def __init__(self, db_dir: str = "data", use_agentic: bool = True):
        """
        Initialize the Meal Planning Assistant.

        Args:
            db_dir: Directory containing databases
            use_agentic: Use LLM-powered agents if available (default: True)
        """
        self.db = DatabaseInterface(db_dir=db_dir)

        # Choose agent implementation
        if use_agentic and AGENTIC_AVAILABLE:
            logger.info("Initializing with LLM-powered agentic agents")
            self.planning_agent = AgenticPlanningAgent(self.db)
            self.shopping_agent = AgenticShoppingAgent(self.db)
            self.cooking_agent = AgenticCookingAgent(self.db)
            self.is_agentic = True
        else:
            if use_agentic and not AGENTIC_AVAILABLE:
                logger.warning("ANTHROPIC_API_KEY not set - falling back to algorithmic agents")
            logger.info("Initializing with algorithmic agents")
            self.planning_agent = EnhancedPlanningAgent(self.db)
            self.shopping_agent = AgenticShoppingAgent(self.db)  # Always use LLM-powered
            self.cooking_agent = CookingAgent(self.db)
            self.is_agentic = False

        logger.info(f"Meal Planning Assistant initialized (agentic={self.is_agentic})")

    def plan_week(self, week_of: Optional[str] = None, num_days: int = 7):
        """
        Plan meals for a week.

        Args:
            week_of: ISO date for Monday (defaults to next week)
            num_days: Number of days to plan

        Returns:
            Meal plan result dictionary
        """
        if week_of is None:
            # Default to next Monday
            today = datetime.now()
            days_until_monday = (7 - today.weekday()) % 7
            if days_until_monday == 0:
                days_until_monday = 7
            next_monday = today + timedelta(days=days_until_monday)
            week_of = next_monday.strftime("%Y-%m-%d")

        logger.info(f"Planning meals for week of {week_of}")

        result = self.planning_agent.plan_week(week_of=week_of, num_days=num_days)

        if result["success"]:
            # Print explanation
            explanation = self.planning_agent.explain_plan(result["meal_plan_id"])
            print("\n" + explanation)
            print(f"\n✓ Meal plan saved: {result['meal_plan_id']}")

        return result

    def create_shopping_list(
        self,
        meal_plan_id: str,
        scaling_instructions: Optional[str] = None
    ):
        """
        Create a shopping list from a meal plan.

        Args:
            meal_plan_id: ID of the meal plan
            scaling_instructions: Optional natural language instructions for scaling
                                 specific recipes (e.g., "double the Italian sandwiches")

        Returns:
            Shopping list result dictionary
        """
        logger.info(f"Creating shopping list for meal plan {meal_plan_id}")
        if scaling_instructions:
            logger.info(f"Scaling instructions: {scaling_instructions}")

        result = self.shopping_agent.create_grocery_list(
            meal_plan_id,
            scaling_instructions=scaling_instructions
        )

        if result["success"]:
            # Print formatted list only if running as CLI script (not imported)
            if __name__ == "__main__":
                formatted = self.shopping_agent.format_shopping_list(result["grocery_list_id"])
                print("\n" + formatted)
                print(f"\n✓ Shopping list saved: {result['grocery_list_id']}")

        return result

    def get_cooking_guide(self, recipe_id: str):
        """
        Get cooking instructions for a recipe.

        Args:
            recipe_id: Recipe ID

        Returns:
            Cooking guide result dictionary
        """
        logger.info(f"Getting cooking guide for recipe {recipe_id}")

        result = self.cooking_agent.get_cooking_guide(recipe_id)

        if result["success"]:
            # Print formatted instructions
            formatted = self.cooking_agent.format_cooking_instructions(recipe_id)
            print("\n" + formatted)

        return result

    def complete_workflow(self, week_of: Optional[str] = None):
        """
        Run complete plan → shop → cook workflow.

        Args:
            week_of: ISO date for Monday (defaults to next week)

        Returns:
            Dictionary with all results
        """
        print("\n" + "="*70)
        print("MEAL PLANNING ASSISTANT - Complete Workflow")
        print("="*70)

        # Step 1: Plan meals
        print("\n📅 Step 1: Planning Meals...")
        print("-"*70)
        plan_result = self.plan_week(week_of=week_of)

        if not plan_result["success"]:
            print(f"❌ Planning failed: {plan_result.get('error')}")
            return {"success": False, "step": "planning", "error": plan_result.get("error")}

        meal_plan_id = plan_result["meal_plan_id"]

        # Step 2: Generate shopping list
        print("\n🛒 Step 2: Generating Shopping List...")
        print("-"*70)
        shop_result = self.create_shopping_list(meal_plan_id)

        if not shop_result["success"]:
            print(f"❌ Shopping list failed: {shop_result.get('error')}")
            return {"success": False, "step": "shopping", "error": shop_result.get("error")}

        # Step 3: Show cooking guide for first meal
        print("\n👨‍🍳 Step 3: Cooking Guide (First Meal)...")
        print("-"*70)

        first_meal = plan_result["meals"][0]
        cook_result = self.get_cooking_guide(first_meal["recipe_id"])

        if not cook_result["success"]:
            print(f"❌ Cooking guide failed: {cook_result.get('error')}")

        # Summary
        print("\n" + "="*70)
        print("✅ WORKFLOW COMPLETE!")
        print("="*70)
        print(f"\n📋 Summary:")
        print(f"   • Meal Plan: {meal_plan_id}")
        print(f"   • Shopping List: {shop_result['grocery_list_id']}")
        print(f"   • Total Meals: {len(plan_result['meals'])}")
        print(f"   • Shopping Items: {shop_result['num_items']}")

        return {
            "success": True,
            "meal_plan_id": meal_plan_id,
            "shopping_list_id": shop_result["grocery_list_id"],
            "plan_result": plan_result,
            "shop_result": shop_result,
            "cook_result": cook_result,
        }


def main():
    """CLI entry point."""
    parser = argparse.ArgumentParser(description="Meal Planning Assistant")
    parser.add_argument(
        "command",
        choices=["plan", "shop", "cook", "workflow"],
        help="Command to run",
    )
    parser.add_argument(
        "--week",
        type=str,
        help="Week date (YYYY-MM-DD) for planning",
    )
    parser.add_argument(
        "--meal-plan-id",
        type=str,
        help="Meal plan ID for shopping",
    )
    parser.add_argument(
        "--recipe-id",
        type=str,
        help="Recipe ID for cooking guide",
    )
    parser.add_argument(
        "--db-dir",
        type=str,
        default="data",
        help="Database directory (default: data)",
    )

    args = parser.parse_args()

    assistant = MealPlanningAssistant(db_dir=args.db_dir)

    if args.command == "plan":
        assistant.plan_week(week_of=args.week)

    elif args.command == "shop":
        if not args.meal_plan_id:
            print("❌ Error: --meal-plan-id required for 'shop' command")
            return

        assistant.create_shopping_list(args.meal_plan_id)

    elif args.command == "cook":
        if not args.recipe_id:
            print("❌ Error: --recipe-id required for 'cook' command")
            return

        assistant.get_cooking_guide(args.recipe_id)

    elif args.command == "workflow":
        assistant.complete_workflow(week_of=args.week)


if __name__ == "__main__":
    main()
