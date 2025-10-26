#!/usr/bin/env python3
"""
LLM-powered chatbot for Meal Planning Assistant.

Uses Claude via Anthropic API with MCP tool access.
"""

import os
import sys
import json
import requests
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

        # Progress callback for showing status to user
        self.progress_callback = None

    def get_system_prompt(self) -> str:
        """Get system prompt for the LLM."""
        context = []
        if self.current_meal_plan_id:
            context.append(f"Current meal plan ID: {self.current_meal_plan_id}")
        if self.current_shopping_list_id:
            context.append(f"Current shopping list ID: {self.current_shopping_list_id}")

        context_str = "\n".join(context) if context else "No active plans yet."

        return f"""You are a helpful, conversational meal planning assistant. You chat naturally with users about their meal needs.

You have access to:
- A database of 492,630 Food.com recipes (for structured meal planning)
- Web search (for finding recipes from any source online)

Current context:
{context_str}

CONVERSATION STYLE:
- Be natural and conversational, like ChatGPT
- Extract meal preferences from casual conversation
- Don't require users to use specific commands or phrases
- Proactively offer to help with planning, shopping lists, or finding recipes

TOOL USAGE:

**When user casually mentions needing recipes** (e.g., "I need ramen soup, chicken, tacos"):
→ Use search_web_recipes to find recipes from the web with links
→ Show results quickly with URLs so they can explore
→ Examples: "need recipes for chicken", "looking for taco recipes", "want to make salmon"

**For structured meal planning** (when they want a full week planned):
→ Use plan_meals to create a complete 7-day plan from the database
→ This pulls from your 492k recipe database and considers variety

**For recipe search in database** (when browsing internal options):
→ Use search_recipes for Food.com database recipes
→ Good for when they want your curated options

**For meal swaps**:
→ Use swap_meal to replace one meal in their plan

**For shopping lists**:
→ Use create_shopping_list from their meal plan

**For cooking instructions**:
→ Use get_cooking_guide for detailed steps

IMPORTANT: Keep responses SHORT and conversational. Focus on being helpful, not verbose."""

    def get_tools(self) -> List[Dict[str, Any]]:
        """Define tools available to the LLM."""
        return [
            {
                "name": "search_web_recipes",
                "description": "Search the web for recipes and return results with links. Use this when user casually mentions recipes they want to find (e.g., 'I need recipes for chicken soup, tacos, salmon'). Returns recipe names with URLs from various recipe sites.",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "recipes": {
                            "type": "array",
                            "items": {"type": "string"},
                            "description": "List of recipe types to search for (e.g., ['ramen soup', 'chicken soup', 'tacos', 'salmon with rice'])",
                        },
                    },
                    "required": ["recipes"],
                },
            },
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

    def _search_web_for_recipe(self, recipe_name: str) -> Dict[str, Any]:
        """Search web for a recipe and return link + recipe details.

        Returns both an active link AND recipe details (ingredients, steps).
        This allows the chatbot to provide immediate value while also
        populating the meal plan structure in the background.
        """
        try:
            # First, search our internal database for similar recipes
            # Extract key terms from recipe name for better matching
            search_terms = recipe_name.lower()

            # Try to find main ingredient/dish type
            keywords = []
            if "ramen" in search_terms or "noodle" in search_terms:
                keywords = ["ramen", "noodle", "asian"]
            elif "chicken" in search_terms and "soup" in search_terms:
                keywords = ["chicken", "soup"]
            elif "taco" in search_terms:
                keywords = ["taco", "mexican"]
            elif "salmon" in search_terms:
                keywords = ["salmon", "fish"]
            elif "pasta" in search_terms:
                keywords = ["pasta", "italian"]
            else:
                # Extract first two words as search terms
                words = search_terms.split()
                keywords = words[:2] if len(words) >= 2 else words

            # Search with the first keyword
            internal_recipes = self.assistant.db.search_recipes(
                query=keywords[0] if keywords else recipe_name,
                limit=3,
                max_time=45  # Prefer quick recipes
            )

            # Build web search URL
            search_query = recipe_name.replace(" ", "+")
            web_url = f"https://www.google.com/search?q={search_query}+recipe"

            # If we found a similar recipe in our database, use the best match
            if internal_recipes:
                recipe = internal_recipes[0]
                return {
                    "name": recipe_name,
                    "web_url": web_url,
                    "recipe_id": recipe.id,
                    "recipe_name": recipe.name,
                    "time": recipe.estimated_time,
                    "difficulty": recipe.difficulty,
                    "has_details": True
                }
            else:
                # No internal match - return just the web link
                return {
                    "name": recipe_name,
                    "web_url": web_url,
                    "recipe_id": None,
                    "recipe_name": recipe_name,
                    "time": None,
                    "difficulty": None,
                    "has_details": False
                }

        except Exception as e:
            # Fallback to just web search
            search_query = recipe_name.replace(" ", "+")
            return {
                "name": recipe_name,
                "web_url": f"https://www.google.com/search?q={search_query}+recipe",
                "recipe_id": None,
                "recipe_name": recipe_name,
                "time": None,
                "difficulty": None,
                "has_details": False
            }

    def execute_tool(self, tool_name: str, tool_input: Dict[str, Any]) -> str:
        """Execute a tool and return results."""
        try:
            if tool_name == "search_web_recipes":
                if self.progress_callback:
                    self.progress_callback("🔍 Searching for recipes...")

                recipes = tool_input.get("recipes", [])
                if not recipes:
                    return "No recipes specified. What would you like to find?"

                output = f"Here are recipes I found:\n\n"
                found_recipe_ids = []

                for recipe_name in recipes:
                    result = self._search_web_for_recipe(recipe_name)

                    output += f"**{recipe_name.title()}:**\n"
                    output += f"🔗 {result['web_url']}\n"

                    if result['has_details']:
                        # Show recipe details from our database
                        time_str = f"{result['time']} min" if result['time'] else "?"
                        output += f"📋 {result['recipe_name']}\n"
                        output += f"⏱️  {time_str} | {result['difficulty']}\n"
                        found_recipe_ids.append(result['recipe_id'])
                    else:
                        output += f"💡 Click link to browse web recipes\n"

                    output += "\n"

                # BACKGROUND POPULATION: If user searched for 4-7 recipes, auto-create meal plan
                if 4 <= len(found_recipe_ids) <= 7:
                    try:
                        if self.progress_callback:
                            self.progress_callback("📅 Creating meal plan from your recipes...")

                        # Create a meal plan from these recipes in the background
                        from datetime import datetime, timedelta

                        # Get next Monday
                        today = datetime.now().date()
                        days_ahead = 0 - today.weekday()  # Monday = 0
                        if days_ahead <= 0:
                            days_ahead += 7
                        next_monday = today + timedelta(days=days_ahead)

                        # Create meal plan ID
                        plan_id = f"mp_{next_monday.isoformat()}_{datetime.now().strftime('%Y%m%d%H%M%S')}"

                        # Save meals to database
                        meals = []
                        for i, recipe_id in enumerate(found_recipe_ids):
                            meal_date = next_monday + timedelta(days=i)
                            recipe = self.assistant.db.get_recipe(recipe_id)
                            meals.append({
                                'date': meal_date.isoformat(),
                                'recipe_id': recipe_id,
                                'recipe_name': recipe.name
                            })

                        # Save to database
                        self.assistant.db.save_meal_plan(
                            plan_id=plan_id,
                            week_of=next_monday.isoformat(),
                            meals=meals
                        )

                        # Update chatbot state
                        self.current_meal_plan_id = plan_id

                        output += f"✨ **Bonus**: I've automatically created a meal plan for you with these {len(meals)} recipes!\n"
                        output += f"   Week of {next_monday.strftime('%b %d')} - Plan ID: {plan_id}\n"

                    except Exception as e:
                        # Don't fail the whole request if background population fails
                        pass

                return output.strip()

            elif tool_name == "plan_meals":
                if self.progress_callback:
                    num_days = tool_input.get("num_days", 7)
                    self.progress_callback(f"🍽️ Planning your {num_days}-day meal plan...")

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
                if self.progress_callback:
                    self.progress_callback("🛒 Generating shopping list...")

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
                if self.progress_callback:
                    self.progress_callback("🔄 Finding a better recipe for that day...")

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
        try:
            response = self.client.messages.create(
                model="claude-sonnet-4-5-20250929",
                max_tokens=512,  # Reduced from 4096 for faster, more concise responses
                system=self.get_system_prompt(),
                tools=self.get_tools(),
                messages=self.conversation_history,
            )
        except Exception as e:
            # If conversation history is corrupted, reset and try again
            if "tool_use" in str(e) and "tool_result" in str(e):
                print(f"⚠️ Conversation history corrupted, resetting: {e}")
                self.conversation_history = [{
                    "role": "user",
                    "content": user_message,
                }]
                response = self.client.messages.create(
                    model="claude-sonnet-4-5-20250929",
                    max_tokens=512,
                    system=self.get_system_prompt(),
                    tools=self.get_tools(),
                    messages=self.conversation_history,
                )
            else:
                raise

        # Process response
        while response.stop_reason == "tool_use":
            # Build assistant content with all blocks (text + tool_use)
            assistant_content = []
            tool_results = []

            for content_block in response.content:
                # Add all content blocks to assistant message
                if content_block.type == "text":
                    assistant_content.append({
                        "type": "text",
                        "text": content_block.text
                    })
                elif content_block.type == "tool_use":
                    assistant_content.append({
                        "type": "tool_use",
                        "id": content_block.id,
                        "name": content_block.name,
                        "input": content_block.input
                    })

                    # Execute tool and collect result
                    tool_result = self.execute_tool(
                        content_block.name,
                        content_block.input,
                    )

                    tool_results.append({
                        "type": "tool_result",
                        "tool_use_id": content_block.id,
                        "content": tool_result,
                    })

            # Add assistant's response with all content blocks to history
            self.conversation_history.append({
                "role": "assistant",
                "content": assistant_content,
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
