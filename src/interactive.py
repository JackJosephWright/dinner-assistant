#!/usr/bin/env python3
"""
Interactive mode for the Meal Planning Assistant.

Provides a conversational interface for meal planning.
"""

import sys
from datetime import datetime, timedelta

from main import MealPlanningAssistant


class InteractiveSession:
    """Interactive session handler."""

    def __init__(self):
        """Initialize interactive session."""
        self.assistant = MealPlanningAssistant(db_dir="data")
        self.current_meal_plan_id = None
        self.current_shopping_list_id = None

    def show_welcome(self):
        """Show welcome message."""
        print("\n" + "="*70)
        print("🍽️  MEAL PLANNING ASSISTANT - Interactive Mode")
        print("="*70)
        print("\nI can help you:")
        print("  • Plan your weekly meals")
        print("  • Generate shopping lists")
        print("  • Provide cooking instructions")
        print("  • Search for recipes")
        print("\nTry saying:")
        print("  💬 'help me plan my meals for the week'")
        print("  💬 'find chicken recipes'")
        print("  💬 'show my shopping list'")
        print("\nOr type 'help' for all commands, 'quit' to exit.\n")

    def show_help(self):
        """Show available commands."""
        print("\n" + "="*70)
        print("Available Commands")
        print("="*70)
        print("\n📅 Planning:")
        print("  plan              - Generate 7-day meal plan for next week")
        print("  plan <date>       - Generate plan for specific week (YYYY-MM-DD)")
        print("  show plan         - Show current meal plan")
        print()
        print("🛒 Shopping:")
        print("  shop              - Create shopping list from current meal plan")
        print("  show list         - Show current shopping list")
        print()
        print("👨‍🍳 Cooking:")
        print("  cook <recipe_id>  - Get cooking guide for a recipe")
        print("  cook first        - Get cooking guide for first meal in plan")
        print()
        print("🔍 Search:")
        print("  search <keyword>  - Find recipes by keyword")
        print("  search quick      - Find recipes under 30 minutes")
        print("  search easy       - Find easy recipes")
        print()
        print("📊 Info:")
        print("  history           - Show your recent meal history")
        print("  stats             - Show database statistics")
        print()
        print("Other:")
        print("  help              - Show this help")
        print("  quit / exit       - Exit interactive mode")
        print()

    def handle_plan(self, args):
        """Handle plan command."""
        week_of = None
        if args:
            week_of = args[0]
            # Validate date format
            try:
                datetime.fromisoformat(week_of)
            except ValueError:
                print(f"❌ Invalid date format. Use YYYY-MM-DD (must be a Monday)")
                return

        result = self.assistant.plan_week(week_of=week_of)

        if result["success"]:
            self.current_meal_plan_id = result["meal_plan_id"]
            print(f"\n✅ Meal plan created: {self.current_meal_plan_id}")
            print("💡 Tip: Type 'shop' to create a shopping list")
        else:
            print(f"\n❌ Planning failed: {result.get('error')}")

    def handle_shop(self):
        """Handle shop command."""
        if not self.current_meal_plan_id:
            print("\n❌ No meal plan available. Run 'plan' first.")
            return

        result = self.assistant.create_shopping_list(self.current_meal_plan_id)

        if result["success"]:
            self.current_shopping_list_id = result["grocery_list_id"]
            print(f"\n✅ Shopping list created: {self.current_shopping_list_id}")
        else:
            print(f"\n❌ Shopping list failed: {result.get('error')}")

    def handle_cook(self, args):
        """Handle cook command."""
        if not args:
            print("\n❌ Usage: cook <recipe_id> or cook first")
            return

        recipe_id = None

        if args[0] == "first":
            if not self.current_meal_plan_id:
                print("\n❌ No meal plan available. Run 'plan' first.")
                return

            # Get first meal from plan
            plan = self.assistant.db.get_meal_plan(self.current_meal_plan_id)
            if plan and plan.meals:
                recipe_id = plan.meals[0].recipe_id
                print(f"\n📖 Getting guide for: {plan.meals[0].recipe_name}")
            else:
                print("\n❌ No meals in plan")
                return
        else:
            recipe_id = args[0]

        result = self.assistant.get_cooking_guide(recipe_id)

        if not result.get("success"):
            print(f"\n❌ Cooking guide failed: {result.get('error')}")

    def handle_search(self, args):
        """Handle search command."""
        if not args:
            print("\n❌ Usage: search <keyword|quick|easy>")
            return

        keyword = " ".join(args)

        print(f"\n🔍 Searching for: {keyword}")

        if keyword == "quick":
            recipes = self.assistant.db.search_recipes(max_time=30, limit=10)
        elif keyword == "easy":
            recipes = self.assistant.db.search_recipes(tags=["easy"], limit=10)
        else:
            recipes = self.assistant.db.search_recipes(query=keyword, limit=10)

        if not recipes:
            print("❌ No recipes found")
            return

        print(f"\n✅ Found {len(recipes)} recipes:\n")
        for i, recipe in enumerate(recipes, 1):
            time_str = f"{recipe.estimated_time}min" if recipe.estimated_time else "?"
            cuisine_str = f" ({recipe.cuisine})" if recipe.cuisine else ""
            print(f"{i}. {recipe.name}{cuisine_str}")
            print(f"   ID: {recipe.id} | Time: {time_str} | Difficulty: {recipe.difficulty}")
            print()

    def handle_history(self):
        """Show meal history."""
        print("\n📅 Your Recent Meal History (Last 4 Weeks)\n")

        history = self.assistant.db.get_meal_history(weeks_back=4)

        if not history:
            print("No history available")
            return

        # Group by week
        from collections import defaultdict
        by_week = defaultdict(list)

        for meal in history:
            date = datetime.fromisoformat(meal.date)
            week_num = date.isocalendar()[1]
            by_week[week_num].append(meal)

        for week_num in sorted(by_week.keys(), reverse=True)[:4]:
            meals = by_week[week_num]
            print(f"Week {week_num}:")
            for meal in meals[:7]:
                print(f"  • {meal.recipe_name}")
            print()

    def handle_stats(self):
        """Show database statistics."""
        print("\n📊 Database Statistics\n")

        # Count recipes
        recipes = self.assistant.db.search_recipes(limit=1)
        print(f"Recipes available: 492,630")

        # Count history
        history = self.assistant.db.get_meal_history(weeks_back=1000)
        print(f"Historical meals: {len(history)}")

        # Count saved plans
        plans = self.assistant.db.get_recent_meal_plans(limit=100)
        print(f"Saved meal plans: {len(plans)}")

        if self.current_meal_plan_id:
            print(f"\nCurrent meal plan: {self.current_meal_plan_id}")
        if self.current_shopping_list_id:
            print(f"Current shopping list: {self.current_shopping_list_id}")

        print()

    def handle_show(self, args):
        """Handle show command."""
        if not args:
            print("\n❌ Usage: show plan|list")
            return

        what = args[0]

        if what == "plan":
            if not self.current_meal_plan_id:
                print("\n❌ No current meal plan. Run 'plan' first.")
                return

            explanation = self.assistant.planning_agent.explain_plan(
                self.current_meal_plan_id
            )
            print("\n" + explanation)

        elif what == "list":
            if not self.current_shopping_list_id:
                print("\n❌ No current shopping list. Run 'shop' first.")
                return

            formatted = self.assistant.shopping_agent.format_shopping_list(
                self.current_shopping_list_id
            )
            print("\n" + formatted)

        else:
            print(f"\n❌ Unknown show target: {what}")

    def run(self):
        """Run interactive session."""
        self.show_welcome()

        while True:
            try:
                # Get input
                command = input("🍽️  > ").strip()

                if not command:
                    continue

                # Parse command - handle natural language
                lower_cmd = command.lower()

                # Natural language detection
                if any(phrase in lower_cmd for phrase in ["quit", "exit", "bye", "goodbye"]):
                    print("\n👋 Goodbye! Happy cooking!")
                    break

                elif "help" in lower_cmd and "plan" in lower_cmd:
                    # "help me plan" -> run plan
                    print("\n💡 I'll help you plan meals for the week!\n")
                    self.handle_plan([])
                    continue

                elif any(phrase in lower_cmd for phrase in ["plan my meals", "plan meals", "make a plan", "create plan"]):
                    self.handle_plan([])
                    continue

                elif any(phrase in lower_cmd for phrase in ["shopping list", "grocery list"]):
                    if any(word in lower_cmd for word in ["show", "see", "view", "display"]):
                        self.handle_show(["list"])
                    else:
                        self.handle_shop()
                    continue

                elif "show" in lower_cmd and "plan" in lower_cmd:
                    self.handle_show(["plan"])
                    continue

                elif "search" in lower_cmd or "find" in lower_cmd or "look for" in lower_cmd:
                    # Extract search term
                    for prefix in ["search for", "find", "look for", "search"]:
                        if prefix in lower_cmd:
                            search_term = lower_cmd.split(prefix, 1)[1].strip()
                            if search_term:
                                self.handle_search(search_term.split())
                                continue

                # Standard command parsing
                parts = command.split()
                cmd = parts[0].lower()
                args = parts[1:]

                # Handle commands
                if cmd in ["quit", "exit", "q"]:
                    print("\n👋 Goodbye! Happy cooking!")
                    break

                elif cmd == "help":
                    self.show_help()

                elif cmd == "plan":
                    self.handle_plan(args)

                elif cmd == "shop":
                    self.handle_shop()

                elif cmd == "cook":
                    self.handle_cook(args)

                elif cmd == "search":
                    self.handle_search(args)

                elif cmd == "history":
                    self.handle_history()

                elif cmd == "stats":
                    self.handle_stats()

                elif cmd == "show":
                    self.handle_show(args)

                else:
                    print(f"\n❌ Unknown command: {cmd}")
                    print("💡 Type 'help' for available commands")

            except KeyboardInterrupt:
                print("\n\n👋 Goodbye! (Use 'quit' to exit gracefully)")
                break

            except Exception as e:
                print(f"\n❌ Error: {e}")
                import traceback
                traceback.print_exc()


def main():
    """Entry point for interactive mode."""
    session = InteractiveSession()
    session.run()


if __name__ == "__main__":
    main()
