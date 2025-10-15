#!/usr/bin/env python3
"""
LLM-powered chatbot for Meal Planning Assistant.

Uses Claude via Anthropic API with MCP tool access.
"""

import os
import sys
import json
from typing import List, Dict, Any

from anthropic import Anthropic

from main import MealPlanningAssistant


class MealPlanningChatbot:
    """LLM-powered chatbot with MCP tool access."""

    def __init__(self):
        """Initialize chatbot with LLM and tools."""
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

        # Current context
        self.current_meal_plan_id = None
        self.current_shopping_list_id = None

    def get_system_prompt(self) -> str:
        """Get system prompt for the LLM."""
        context = []
        if self.current_meal_plan_id:
            context.append(f"Current meal plan ID: {self.current_meal_plan_id}")
        if self.current_shopping_list_id:
            context.append(f"Current shopping list ID: {self.current_shopping_list_id}")

        context_str = "\n".join(context) if context else "No active plans yet."

        return f"""You are a helpful meal planning assistant. You help users plan their weekly meals, create shopping lists, and provide cooking guidance.

You have access to a database of 492,630 recipes and can search, plan meals, generate shopping lists, and provide cooking instructions.

Current context:
{context_str}

When users ask about meal planning:
- Offer to plan their week
- Ask about preferences if needed
- Use the plan_meals tool to generate plans

When users want to change a meal:
- Use show_current_plan to see the current plan if needed
- Use swap_meal to replace a specific meal with a different recipe
- The swap_meal tool will intelligently find a good replacement based on the user's requirements

When users want shopping lists:
- Check if they have a meal plan first
- Use the create_shopping_list tool

For cooking help:
- Use get_cooking_guide to provide instructions
- Suggest substitutions when asked

IMPORTANT: Keep responses SHORT and to the point. Users want speed over lengthy explanations. Confirm actions with 1-2 sentences max."""

    def get_tools(self) -> List[Dict[str, Any]]:
        """Define tools available to the LLM."""
        return [
            {
                "name": "plan_meals",
                "description": "Generate a 7-day meal plan with variety and balanced nutrition. Returns a meal plan with recipe names, IDs, and variety summary.",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "week_of": {
                            "type": "string",
                            "description": "ISO date for Monday of the week (YYYY-MM-DD). Optional, defaults to next week.",
                        },
                        "num_days": {
                            "type": "integer",
                            "description": "Number of days to plan (default: 7)",
                            "default": 7,
                        },
                    },
                },
            },
            {
                "name": "create_shopping_list",
                "description": "Create a consolidated shopping list from the current meal plan. Organizes ingredients by store section. Can apply scaling instructions to specific recipes.",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "meal_plan_id": {
                            "type": "string",
                            "description": "ID of the meal plan (use current if available)",
                        },
                        "scaling_instructions": {
                            "type": "string",
                            "description": "Optional natural language instructions for scaling specific recipes (e.g., 'double the Italian sandwiches', 'triple the chicken for meal prep', 'reduce pasta by half')",
                        },
                    },
                    "required": ["meal_plan_id"],
                },
            },
            {
                "name": "search_recipes",
                "description": "Search for recipes by keyword, cooking time, or tags. Returns recipe IDs, names, and details.",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "query": {
                            "type": "string",
                            "description": "Search keyword (e.g., 'chicken', 'salmon')",
                        },
                        "max_time": {
                            "type": "integer",
                            "description": "Maximum cooking time in minutes",
                        },
                        "tags": {
                            "type": "array",
                            "items": {"type": "string"},
                            "description": "Required tags like 'easy', 'vegetarian'",
                        },
                        "limit": {
                            "type": "integer",
                            "description": "Maximum results (default: 10)",
                            "default": 10,
                        },
                    },
                },
            },
            {
                "name": "get_cooking_guide",
                "description": "Get detailed cooking instructions for a specific recipe including ingredients, steps, and tips.",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "recipe_id": {
                            "type": "string",
                            "description": "Recipe ID",
                        },
                    },
                    "required": ["recipe_id"],
                },
            },
            {
                "name": "get_meal_history",
                "description": "Show the user's recent meal history to understand their preferences.",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "weeks_back": {
                            "type": "integer",
                            "description": "Number of weeks to look back (default: 4)",
                            "default": 4,
                        },
                    },
                },
            },
            {
                "name": "show_current_plan",
                "description": "Display the current meal plan details.",
                "input_schema": {
                    "type": "object",
                    "properties": {},
                },
            },
            {
                "name": "show_shopping_list",
                "description": "Display the current shopping list.",
                "input_schema": {
                    "type": "object",
                    "properties": {},
                },
            },
            {
                "name": "swap_meal",
                "description": "Swap a meal in the current meal plan with a different recipe. Use when user wants to replace a specific meal.",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "date": {
                            "type": "string",
                            "description": "Date of meal to swap (YYYY-MM-DD)",
                        },
                        "requirements": {
                            "type": "string",
                            "description": "User's requirements for the replacement (e.g., 'shellfish dish', 'vegetarian pasta', 'quick chicken')",
                        },
                    },
                    "required": ["date", "requirements"],
                },
            },
        ]

    def execute_tool(self, tool_name: str, tool_input: Dict[str, Any]) -> str:
        """Execute a tool and return results."""
        try:
            if tool_name == "plan_meals":
                result = self.assistant.plan_week(
                    week_of=tool_input.get("week_of"),
                    num_days=tool_input.get("num_days", 7),
                )
                if result["success"]:
                    self.current_meal_plan_id = result["meal_plan_id"]
                    # Format nicely
                    output = f"Created meal plan: {result['meal_plan_id']}\n\n"
                    output += "Meals:\n"
                    for meal in result["meals"]:
                        output += f"- {meal['date']}: {meal['recipe_name']}\n"
                    return output
                else:
                    return f"Error: {result.get('error')}"

            elif tool_name == "create_shopping_list":
                meal_plan_id = tool_input.get("meal_plan_id") or self.current_meal_plan_id
                if not meal_plan_id:
                    return "Error: No meal plan available. Please plan meals first."

                scaling_instructions = tool_input.get("scaling_instructions")
                result = self.assistant.create_shopping_list(
                    meal_plan_id,
                    scaling_instructions=scaling_instructions
                )
                if result["success"]:
                    self.current_shopping_list_id = result["grocery_list_id"]
                    scaling_note = f" (with scaling: {scaling_instructions})" if scaling_instructions else ""
                    return f"Created shopping list with {result['num_items']} items, organized by store section{scaling_note}."
                else:
                    return f"Error: {result.get('error')}"

            elif tool_name == "search_recipes":
                recipes = self.assistant.db.search_recipes(
                    query=tool_input.get("query"),
                    max_time=tool_input.get("max_time"),
                    tags=tool_input.get("tags"),
                    limit=tool_input.get("limit", 10),
                )
                if not recipes:
                    return "No recipes found matching your criteria."

                output = f"Found {len(recipes)} recipes:\n\n"
                for recipe in recipes[:10]:
                    time_str = f"{recipe.estimated_time} min" if recipe.estimated_time else "?"
                    output += f"- {recipe.name} (ID: {recipe.id})\n"
                    output += f"  Time: {time_str}, Difficulty: {recipe.difficulty}\n"
                return output

            elif tool_name == "get_cooking_guide":
                result = self.assistant.get_cooking_guide(tool_input["recipe_id"])
                if result["success"]:
                    output = f"Recipe: {result['recipe_name']}\n"
                    output += f"Time: {result['estimated_time']} min, Servings: {result['servings']}\n\n"
                    output += "Ingredients:\n"
                    for ing in result["ingredients"][:10]:
                        output += f"- {ing}\n"
                    if len(result["ingredients"]) > 10:
                        output += f"... and {len(result['ingredients']) - 10} more\n"
                    output += f"\nSteps: {len(result['steps'])} steps total"
                    return output
                else:
                    return f"Error: {result.get('error')}"

            elif tool_name == "get_meal_history":
                history = self.assistant.db.get_meal_history(
                    weeks_back=tool_input.get("weeks_back", 4)
                )
                if not history:
                    return "No meal history available."

                output = f"Recent meals (last {tool_input.get('weeks_back', 4)} weeks):\n"
                for meal in history[:20]:
                    output += f"- {meal.recipe_name}\n"
                return output

            elif tool_name == "show_current_plan":
                if not self.current_meal_plan_id:
                    return "No active meal plan. Would you like me to create one?"

                explanation = self.assistant.planning_agent.explain_plan(
                    self.current_meal_plan_id
                )
                return explanation

            elif tool_name == "show_shopping_list":
                if not self.current_shopping_list_id:
                    return "No shopping list created yet. Would you like me to create one?"

                formatted = self.assistant.shopping_agent.format_shopping_list(
                    self.current_shopping_list_id
                )
                return formatted

            elif tool_name == "swap_meal":
                if not self.current_meal_plan_id:
                    return "No active meal plan. Please create a meal plan first."

                result = self.assistant.planning_agent.swap_meal(
                    meal_plan_id=self.current_meal_plan_id,
                    date=tool_input["date"],
                    requirements=tool_input["requirements"],
                )

                if result["success"]:
                    output = f"✓ Swapped meal on {result['date']}\n"
                    output += f"  Old: {result['old_recipe']}\n"
                    output += f"  New: {result['new_recipe']}\n"
                    output += f"  Why: {result['reason']}"
                    return output
                else:
                    return f"Error: {result.get('error')}"

            else:
                return f"Unknown tool: {tool_name}"

        except Exception as e:
            return f"Error executing {tool_name}: {str(e)}"

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
            max_tokens=512,  # Reduced from 4096 for faster, more concise responses
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
                    tool_result = self.execute_tool(
                        content_block.name,
                        content_block.input,
                    )

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

            # Get next response
            response = self.client.messages.create(
                model="claude-sonnet-4-5-20250929",
                max_tokens=512,  # Reduced from 4096 for faster, more concise responses
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

    def run(self):
        """Run interactive chat loop."""
        print("\n" + "="*70)
        print("🍽️  MEAL PLANNING ASSISTANT - AI Chatbot")
        print("="*70)
        print("\nPowered by Claude with MCP tools")
        print("I can help you plan meals, create shopping lists, and find recipes!")
        print("\nJust chat naturally - I'll use tools as needed.")
        print("Type 'quit' to exit.\n")

        while True:
            try:
                user_input = input("You: ").strip()

                if not user_input:
                    continue

                if user_input.lower() in ["quit", "exit", "bye"]:
                    print("\n🍽️  Assistant: Goodbye! Happy cooking!")
                    break

                # Get response
                print("\n🍽️  Assistant: ", end="", flush=True)
                response = self.chat(user_input)
                print(response + "\n")

            except KeyboardInterrupt:
                print("\n\n🍽️  Assistant: Goodbye!")
                break
            except Exception as e:
                print(f"\n❌ Error: {e}\n")


def main():
    """Entry point."""
    chatbot = MealPlanningChatbot()
    chatbot.run()


if __name__ == "__main__":
    main()
