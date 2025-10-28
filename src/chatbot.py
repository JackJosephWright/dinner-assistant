#!/usr/bin/env python3
"""
LLM-powered chatbot for Meal Planning Assistant.

Uses Claude via Anthropic API with MCP tool access.
"""

import os
import sys
import json
from typing import List, Dict, Any
from datetime import datetime, timedelta
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

from anthropic import Anthropic

from main import MealPlanningAssistant
from data.models import PlannedMeal, MealPlan


class MealPlanningChatbot:
    """LLM-powered chatbot with MCP tool access."""

    def __init__(self, verbose=False):
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

        # In-memory object store (for follow-up questions)
        self.last_search_results = []  # List[Recipe]
        self.last_meal_plan = None  # MealPlan object

        # Verbose mode for debugging
        self.verbose = verbose

    def _select_recipes_with_llm(self, recipes: List, num_needed: int, recent_meals: List = None) -> List:
        """
        Use LLM to intelligently select recipes considering variety and preferences.

        Args:
            recipes: List of Recipe objects to choose from
            num_needed: Number of recipes to select
            recent_meals: Optional list of recent meal names for variety

        Returns:
            List of selected Recipe objects
        """
        if len(recipes) <= num_needed:
            return recipes

        # Format recipes compactly for LLM
        recipes_text = []
        for i, r in enumerate(recipes, 1):
            ing_count = len(r.get_ingredients()) if r.has_structured_ingredients() else len(r.ingredients_raw)
            recipes_text.append(
                f"{i}. {r.name} (ID: {r.id})\n"
                f"   Ingredients: {ing_count} items\n"
                f"   Tags: {', '.join(r.tags[:5])}"
            )

        recent_text = ""
        if recent_meals:
            recent_text = f"\nRecent meals (avoid similar):\n" + "\n".join(f"- {m}" for m in recent_meals[:10])

        prompt = f"""Select {num_needed} recipes from the candidates below that would make a varied, balanced meal plan.

Goals:
- Add variety (different cuisines, cooking methods, proteins)
- Avoid repeating similar dishes
- Create an appealing week of meals

{recent_text}

Candidates ({len(recipes)} recipes):
{chr(10).join(recipes_text)}

Return ONLY a JSON array of {num_needed} recipe IDs (no other text):
["id1", "id2", ...]"""

        try:
            response = self.client.messages.create(
                model="claude-sonnet-4-5-20250929",
                max_tokens=200,
                messages=[{"role": "user", "content": prompt}]
            )

            # Extract JSON from response
            content = response.content[0].text.strip()
            # Remove markdown code blocks if present
            if content.startswith("```"):
                content = content.split("```")[1]
                if content.startswith("json"):
                    content = content[4:]
            content = content.strip()

            selected_ids = json.loads(content)

            # Return recipes matching selected IDs
            return [r for r in recipes if r.id in selected_ids][:num_needed]

        except Exception as e:
            # Fallback: just return first N recipes
            print(f"LLM selection failed: {e}, using fallback")
            return recipes[:num_needed]

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

When analyzing recipes:
- If asked about ingredients/allergens, use get_cooking_guide to check the ingredients
- ANALYZE the tool results and ANSWER the user's question directly
- Don't just display tool results - use them to answer what was asked

IMPORTANT: Keep responses SHORT and to the point. Users want speed over lengthy explanations. Confirm actions with 1-2 sentences max. BUT ALWAYS answer the user's actual question based on tool results."""

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
                "name": "plan_meals_smart",
                "description": "Create a meal plan using enriched recipe database with smart filtering. Supports allergen filtering, time constraints, and natural language requests. USE THIS for custom planning requests.",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "num_days": {
                            "type": "integer",
                            "description": "Number of days to plan (e.g., 4 for Mon-Thu, 7 for full week)",
                        },
                        "search_query": {
                            "type": "string",
                            "description": "Search keywords (e.g., 'chicken', 'pasta', 'quick dinners')",
                        },
                        "exclude_allergens": {
                            "type": "array",
                            "items": {"type": "string"},
                            "description": "Allergens to avoid: 'dairy', 'gluten', 'nuts', 'shellfish', 'eggs'",
                        },
                        "max_time": {
                            "type": "integer",
                            "description": "Maximum cooking time in minutes",
                        },
                    },
                    "required": ["num_days"],
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

            elif tool_name == "plan_meals_smart":
                # 1. Extract/generate dates
                num_days = tool_input.get("num_days", 7)
                today = datetime.now().date()
                dates = [(today + timedelta(days=i)).isoformat() for i in range(num_days)]

                if self.verbose:
                    print(f"      → Planning {num_days} days starting {dates[0]}")

                # 2. SQL search for candidates
                search_query = tool_input.get("search_query", "")
                candidates = self.assistant.db.search_recipes(
                    query=search_query,
                    max_time=tool_input.get("max_time"),
                    limit=100
                )

                if self.verbose:
                    print(f"      → SQL search found {len(candidates)} candidates for '{search_query}'")

                if not candidates:
                    return f"No recipes found matching '{search_query}'. Try different search terms."

                # 3. Filter by allergens using structured ingredients
                exclude_allergens = tool_input.get("exclude_allergens", [])
                filtered = [
                    r for r in candidates
                    if r.has_structured_ingredients()
                    and not any(r.has_allergen(a) for a in exclude_allergens)
                ]

                if self.verbose:
                    if exclude_allergens:
                        print(f"      → Filtered to {len(filtered)} recipes without {', '.join(exclude_allergens)}")
                    else:
                        print(f"      → All {len(filtered)} have structured ingredients")

                if not filtered:
                    return f"Found {len(candidates)} recipes, but none without {', '.join(exclude_allergens)}. Try relaxing constraints."

                if len(filtered) < num_days:
                    return f"Only found {len(filtered)} recipes matching all constraints, need {num_days}. Try relaxing constraints or reducing days."

                # 4. LLM selects with variety
                recent_meals = self.assistant.db.get_meal_history(weeks_back=2)
                recent_names = [m.recipe_name for m in recent_meals] if recent_meals else []

                if self.verbose:
                    print(f"      → Using LLM to select {num_days} varied recipes from {len(filtered)} options...")

                selected = self._select_recipes_with_llm(filtered, num_days, recent_names)

                if self.verbose:
                    print(f"      → LLM selected: {', '.join([r.name[:30] for r in selected])}")

                # 5. Create PlannedMeal objects with embedded recipes
                meals = [
                    PlannedMeal(
                        date=date,
                        meal_type="dinner",
                        recipe=recipe,
                        servings=4
                    )
                    for date, recipe in zip(dates, selected)
                ]

                # 6. Create and save MealPlan
                plan = MealPlan(
                    week_of=dates[0],
                    meals=meals,
                    preferences_applied=exclude_allergens  # Track what allergens were avoided
                )
                plan_id = self.assistant.db.save_meal_plan(plan)
                self.current_meal_plan_id = plan_id

                # 7. Return summary
                total_ingredients = len(plan.get_all_ingredients())
                all_allergens = plan.get_all_allergens()
                allergen_str = f", allergens: {', '.join(all_allergens)}" if all_allergens else ", allergen-free"

                output = f"✓ Created {num_days}-day meal plan!\n\n"
                output += "Meals:\n"
                for meal in plan.meals:
                    ing_count = len(meal.recipe.get_ingredients()) if meal.recipe.has_structured_ingredients() else "?"
                    output += f"- {meal.date}: {meal.recipe.name} ({ing_count} ingredients)\n"
                output += f"\n📊 {total_ingredients} total ingredients{allergen_str}"

                return output

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

                    # Include allergen info if recipe is enriched
                    if recipe.has_structured_ingredients():
                        allergens = recipe.get_all_allergens()
                        if allergens:
                            output += f"  Allergens: {', '.join(allergens)}\n"
                        else:
                            output += f"  Allergens: none detected\n"

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
                    if self.verbose:
                        print(f"\n🔧 [TOOL] {content_block.name}")
                        print(f"   Input: {json.dumps(content_block.input, indent=2)}")

                    tool_result = self.execute_tool(
                        content_block.name,
                        content_block.input,
                    )

                    if self.verbose:
                        # Truncate long results for readability
                        result_preview = tool_result if len(tool_result) < 200 else tool_result[:200] + "..."
                        print(f"   Result: {result_preview}\n")

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
        print("\nPowered by Claude Sonnet 4.5 with intelligent tools")
        print("Database: 5,000 enriched recipes (100% structured ingredients)")

        if self.verbose:
            print("Mode: VERBOSE (showing tool execution details)")

        print("\n✨ What I can do:")
        print("  • Plan meals with smart recipe selection")
        print("  • Filter by allergens (dairy, gluten, nuts, etc.)")
        print("  • Find recipes by keywords or cooking time")
        print("  • Create shopping lists organized by category")
        print("  • Swap meals in your plan")

        print("\n💡 Try asking:")
        print('  "Plan 4 days of chicken meals"')
        print('  "Plan a week, no dairy or gluten"')
        print('  "Show me quick pasta recipes under 30 minutes"')

        print("\nType 'quit' to exit.\n")

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
