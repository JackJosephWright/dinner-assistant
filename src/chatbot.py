#!/usr/bin/env python3
"""
LLM-powered chatbot for Meal Planning Assistant.

Uses Claude via Anthropic API with MCP tool access.
"""

import os
import sys
import json
import logging
from typing import List, Dict, Any, Tuple, Optional
from datetime import datetime
from dotenv import load_dotenv

logger = logging.getLogger(__name__)

# Load environment variables from .env file
load_dotenv()

from anthropic import Anthropic

from main import MealPlanningAssistant
from chatbot_modules.recipe_selector import validate_plan, ValidationFailure
from chatbot_modules.swap_matcher import check_backup_match
from chatbot_modules.tools_config import build_system_prompt, get_tools as get_tool_definitions
from chatbot_modules.tool_registry import execute_tool as registry_execute_tool


class MealPlanningChatbot:
    """LLM-powered chatbot with MCP tool access."""

    def __init__(self, verbose=False, verbose_callback=None, user_id: int = 1):
        """Initialize chatbot with LLM and tools.

        Args:
            verbose: If True, print tool execution details
            verbose_callback: Optional callback function(message: str) for streaming verbose output to web UI
            user_id: User ID for multi-user support (defaults to 1)
        """
        # Check for API key
        api_key = os.environ.get("ANTHROPIC_API_KEY")
        if not api_key:
            print("❌ Error: ANTHROPIC_API_KEY environment variable not set")
            print("\nTo use the chatbot, set your API key:")
            print("  export ANTHROPIC_API_KEY='your-key-here'")
            print("\nOr use command mode instead:")
            print("  ./run.sh workflow")
            sys.exit(1)

        self.client = Anthropic(api_key=api_key)
        # Use agentic agents (API key is available)
        self.assistant = MealPlanningAssistant(db_dir="data", use_agentic=True)
        self.conversation_history = []

        # User ID for multi-user support
        self.user_id = user_id

        # Current context
        self.current_meal_plan_id = None
        self.current_shopping_list_id = None

        # In-memory object store (for follow-up questions)
        self.last_search_results = []  # List[Recipe]
        self.last_meal_plan = None  # MealPlan object
        self.pending_swap_options = None  # Pending swap confirmation

        # Verbose mode for debugging
        self.verbose = verbose
        self._verbose_callback = verbose_callback
        # Wire verbose callback to planning agent
        self._sync_verbose_callback()

        # Auto-load most recent plan
        self._load_most_recent_plan()

    @property
    def verbose_callback(self):
        """Get the verbose callback."""
        return self._verbose_callback

    @verbose_callback.setter
    def verbose_callback(self, callback):
        """Set verbose callback and sync to planning agent."""
        self._verbose_callback = callback
        self._sync_verbose_callback()

    def _sync_verbose_callback(self):
        """Sync verbose callback to the assistant's planning agent."""
        if hasattr(self.assistant, 'planning_agent'):
            self.assistant.planning_agent.verbose_callback = self._verbose_callback

    def _verbose_output(self, message: str, end: str = "\n", flush: bool = False):
        """
        Output verbose message to both console and callback if available.

        Args:
            message: Verbose message to output
            end: String appended after the message (default: newline)
            flush: Whether to forcibly flush the stream (default: False)
        """
        print(message, end=end, flush=flush)
        if self.verbose_callback:
            try:
                self.verbose_callback(message)
            except Exception as e:
                # Don't let callback errors break the chatbot
                print(f"Warning: verbose_callback failed: {e}")

    def _load_most_recent_plan(self):
        """Load the most recent meal plan automatically on startup."""
        try:
            recent_plans = self.assistant.db.get_recent_meal_plans(user_id=self.user_id, limit=1)
            if recent_plans:
                self.last_meal_plan = recent_plans[0]
                self.current_meal_plan_id = recent_plans[0].id
                # Note: snapshot_id == meal_plan_id in this codebase
                self.current_snapshot_id = recent_plans[0].id
                if self.verbose:
                    self._verbose_output(f"📋 Resumed plan for week of {recent_plans[0].week_of}")
        except Exception as e:
            if self.verbose:
                self._verbose_output(f"Note: Could not load recent plan: {e}")

    # Wrapper methods for backwards compatibility with tests
    def validate_plan(self, selected_recipes: List, day_requirements: List) -> Tuple[List, List]:
        """Wrapper for standalone validate_plan function."""
        return validate_plan(selected_recipes, day_requirements)

    def _check_backup_match(self, requirements: str, category: str) -> str:
        """Wrapper for standalone check_backup_match function."""
        return check_backup_match(
            client=self.client,
            requirements=requirements,
            category=category,
            verbose=self.verbose,
            verbose_callback=self._verbose_output,
        )

    def get_system_prompt(self) -> str:
        """Get system prompt for the LLM."""
        # Get selected_dates if set by UI
        selected_dates = getattr(self, 'selected_dates', None)
        return build_system_prompt(
            current_meal_plan_id=self.current_meal_plan_id,
            current_shopping_list_id=self.current_shopping_list_id,
            last_meal_plan=self.last_meal_plan,
            selected_dates=selected_dates,
        )

    def get_tools(self) -> List[Dict[str, Any]]:
        """Define tools available to the LLM."""
        return get_tool_definitions()

    def execute_tool(self, tool_name: str, tool_input: Dict[str, Any]) -> str:
        """Execute a tool and return results.

        Delegates to the tool registry for actual execution.
        """
        return registry_execute_tool(self, tool_name, tool_input)

    def chat(self, user_message: str) -> str:
        """Send a message and get response."""
        # Add user message to history
        self.conversation_history.append({
            "role": "user",
            "content": user_message,
        })

        # Call Claude with tools
        response = self.client.messages.create(
            model="claude-sonnet-4-5-20250929",
            max_tokens=2048,  # Increased to prevent truncation causing duplicate tool calls
            system=self.get_system_prompt(),
            tools=self.get_tools(),
            messages=self.conversation_history,
        )

        # Process response
        assistant_content = []

        while response.stop_reason == "tool_use":
            # Add assistant's response with tool_use blocks to history
            self.conversation_history.append({
                "role": "assistant",
                "content": response.content,
            })

            # Execute all tools and collect results
            tool_results = []
            for content_block in response.content:
                if content_block.type == "tool_use":
                    # Always emit user-friendly progress for tools (keeps UI responsive)
                    tool_friendly_names = {
                        "plan_meals": "Creating your meal plan...",
                        "plan_meals_smart": "Finding recipes for your meal plan...",
                        "create_shopping_list": "Building your shopping list...",
                        "search_recipes": "Searching recipes...",
                        "swap_meal": "Finding a replacement meal...",
                        "swap_meal_fast": "Swapping meal...",
                        "get_cooking_guide": "Loading recipe details...",
                        "check_allergens": "Checking allergens...",
                        "show_current_plan": "Loading your meal plan...",
                        "modify_recipe": "Modifying recipe...",
                        "clear_recipe_modifications": "Reverting to original recipe...",
                    }
                    friendly_msg = tool_friendly_names.get(content_block.name, f"Running {content_block.name}...")
                    self._verbose_output(friendly_msg)

                    if self.verbose:
                        self._verbose_output(f"\n🔧 [TOOL] {content_block.name}")
                        self._verbose_output(f"   Input: {json.dumps(content_block.input, indent=2)}")

                    tool_result = self.execute_tool(
                        content_block.name,
                        content_block.input,
                    )

                    if self.verbose:
                        # Truncate long results for readability
                        result_preview = tool_result if len(tool_result) < 200 else tool_result[:200] + "..."
                        self._verbose_output(f"   Result: {result_preview}\n")

                    tool_results.append({
                        "type": "tool_result",
                        "tool_use_id": content_block.id,
                        "content": tool_result,
                    })

            # Add all tool results in a single user message
            self.conversation_history.append({
                "role": "user",
                "content": tool_results,
            })

            # Emit progress before next LLM call
            self._verbose_output("Preparing your response...")

            # Get next response
            response = self.client.messages.create(
                model="claude-sonnet-4-5-20250929",
                max_tokens=2048,  # Increased to prevent truncation causing duplicate tool calls
                system=self.get_system_prompt(),
                tools=self.get_tools(),
                messages=self.conversation_history,
            )

        # Extract final text response
        final_response = ""
        for content_block in response.content:
            if hasattr(content_block, "text"):
                final_response += content_block.text

        # Add to history
        self.conversation_history.append({
            "role": "assistant",
            "content": final_response,
        })

        return final_response

    def _display_current_plan_verbose(self):
        """Display current meal plan state in verbose mode."""
        if not self.verbose:
            return

        self._verbose_output("\n" + "="*70)
        self._verbose_output("📋 CURRENT MEAL PLAN STATE")
        self._verbose_output("="*70)

        if self.last_meal_plan is None or not self.last_meal_plan.meals:
            self._verbose_output("No active meal plan")
        else:
            self._verbose_output(f"Week of: {self.last_meal_plan.week_of}")
            self._verbose_output(f"Number of meals: {len(self.last_meal_plan.meals)}")
            self._verbose_output(f"\nMeals:")
            for meal in self.last_meal_plan.meals:
                day_name = meal.date.strftime("%a %m/%d") if isinstance(meal.date, datetime) else meal.date
                self._verbose_output(f"  • {day_name}: {meal.recipe.name}")
                self._verbose_output(f"    ({len(meal.recipe.ingredients)} ingredients)")

            # Show backup recipes available
            if self.last_meal_plan.backup_recipes:
                total_backups = sum(len(recipes) for recipes in self.last_meal_plan.backup_recipes.values())
                self._verbose_output(f"\n🔄 Backup recipes: {total_backups} cached")
                for category, recipes in self.last_meal_plan.backup_recipes.items():
                    self._verbose_output(f"   • {category}: {len(recipes)} recipes")

        self._verbose_output("="*70 + "\n")

    def run(self):
        """Run interactive chat loop."""
        self._verbose_output("\n" + "="*70)
        self._verbose_output("🍽️  MEAL PLANNING ASSISTANT - AI Chatbot")
        self._verbose_output("="*70)
        self._verbose_output("\nPowered by Claude Sonnet 4.5 with intelligent tools")
        self._verbose_output("Database: 5,000 enriched recipes (100% structured ingredients)")

        if self.verbose:
            self._verbose_output("Mode: VERBOSE (showing tool execution details)")

        self._verbose_output("\n✨ What I can do:")
        self._verbose_output("  • Plan meals with smart recipe selection")
        self._verbose_output("  • Filter by allergens (dairy, gluten, nuts, etc.)")
        self._verbose_output("  • Find recipes by keywords or cooking time")
        self._verbose_output("  • Create shopping lists organized by category")
        self._verbose_output("  • Swap meals in your plan")

        self._verbose_output("\n💡 Try asking:")
        self._verbose_output('  "Plan 4 days of chicken meals"')
        self._verbose_output('  "Plan a week, no dairy or gluten"')
        self._verbose_output('  "Show me quick pasta recipes under 30 minutes"')

        self._verbose_output("\nType 'quit' to exit.\n")

        while True:
            try:
                user_input = input("You: ").strip()

                if not user_input:
                    continue

                if user_input.lower() in ["quit", "exit", "bye"]:
                    self._verbose_output("\n🍽️  Assistant: Goodbye! Happy cooking!")
                    break

                # Get response
                self._verbose_output("\n🍽️  Assistant: ", end="", flush=True)
                response = self.chat(user_input)
                self._verbose_output(response + "\n")

                # Display current meal plan state in verbose mode
                self._display_current_plan_verbose()

            except KeyboardInterrupt:
                self._verbose_output("\n\n🍽️  Assistant: Goodbye!")
                break
            except Exception as e:
                self._verbose_output(f"\n❌ Error: {e}\n")


def main():
    """Entry point."""
    import argparse

    parser = argparse.ArgumentParser(
        description="Meal Planning Assistant - AI-powered chat interface"
    )
    parser.add_argument(
        "-v", "--verbose",
        action="store_true",
        help="Show tool execution details for debugging"
    )

    args = parser.parse_args()

    chatbot = MealPlanningChatbot(verbose=args.verbose)
    chatbot.run()


if __name__ == "__main__":
    main()
