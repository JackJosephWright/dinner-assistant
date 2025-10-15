"""
Onboarding flow for new users.

Collects user preferences through a conversational 6-step process:
1. Household size
2. Dietary restrictions
3. Cuisine preferences
4. Cooking time
5. Dislikes (optional)
6. Spice tolerance (optional)
"""

import logging
from typing import Dict, List, Optional, Tuple
from datetime import datetime

from src.data.database import DatabaseInterface
from src.data.models import UserProfile

logger = logging.getLogger(__name__)


class OnboardingFlow:
    """Manages the onboarding conversation flow."""

    def __init__(self, db: DatabaseInterface):
        """
        Initialize onboarding flow.

        Args:
            db: Database interface
        """
        self.db = db
        self.current_step = 0
        self.profile_data = {}

        # Onboarding steps
        self.steps = [
            self.step_household,
            self.step_dietary,
            self.step_cuisines,
            self.step_cooking_time,
            self.step_dislikes,
            self.step_spice_tolerance,
        ]

    def start(self) -> str:
        """
        Start the onboarding flow.

        Returns:
            Welcome message
        """
        self.current_step = 0
        self.profile_data = {}

        welcome = """
🍽️ Welcome to Meal Planning Assistant!

I'm your personal cooking companion. Let's get you set up with a few quick questions
so I can plan meals that work perfectly for you.

This will take about 2 minutes. Ready?
"""
        # Return welcome + first question
        return welcome.strip() + "\n\n" + self.get_current_question()

    def get_current_question(self) -> str:
        """
        Get the question for the current step.

        Returns:
            Question text
        """
        if self.current_step >= len(self.steps):
            return self._summary_and_confirm()

        step_func = self.steps[self.current_step]
        return step_func()

    def process_answer(self, user_input: str) -> Tuple[bool, str]:
        """
        Process user's answer and advance to next step.

        Args:
            user_input: User's response

        Returns:
            Tuple of (is_complete, next_message)
        """
        # Handle summary/confirmation step
        if self.current_step >= len(self.steps):
            return self._handle_confirmation(user_input)

        # Process answer for current step
        step_func = self.steps[self.current_step]
        success = step_func(user_input)

        if not success:
            return False, "I didn't quite understand that. " + self.get_current_question()

        # Move to next step
        self.current_step += 1

        # Check if we're done
        if self.current_step >= len(self.steps):
            # Show summary
            return False, self._summary_and_confirm()

        # Return next question
        return False, self.get_current_question()

    # ==================== Step 1: Household ====================

    def step_household(self, user_input: Optional[str] = None) -> str | bool:
        """Step 1: Ask about household size."""
        if user_input is None:
            return """
**Q1: Tell me about your household**

How many adults and kids are you cooking for?

Examples:
- "2 adults and 2 kids"
- "Just me" (1 adult)
- "2 adults, no kids"
- "Family of 4 with 2 children"

Your answer:
""".strip()

        # Parse answer
        try:
            # Look for numbers in the input
            import re

            numbers = re.findall(r"\d+", user_input)

            if not numbers:
                return False

            household_size = int(numbers[0])

            # Try to parse adults/kids breakdown
            cooking_for = {"adults": household_size, "kids": 0}

            if "adult" in user_input.lower() and "kid" in user_input.lower():
                if len(numbers) >= 2:
                    cooking_for["adults"] = int(numbers[0])
                    cooking_for["kids"] = int(numbers[1])

            self.profile_data["household_size"] = household_size
            self.profile_data["cooking_for"] = cooking_for

            return True

        except Exception as e:
            logger.warning(f"Error parsing household answer: {e}")
            return False

    # ==================== Step 2: Dietary ====================

    def step_dietary(self, user_input: Optional[str] = None) -> str | bool:
        """Step 2: Ask about dietary restrictions and allergies."""
        if user_input is None:
            return """
**Q2: Any dietary restrictions or allergies I should know about?**

Examples:
- "Dairy-free and nut allergies"
- "Vegetarian"
- "None"

Your answer:
""".strip()

        # Parse answer
        user_input_lower = user_input.lower()

        if "none" in user_input_lower or "no" in user_input_lower:
            self.profile_data["dietary_restrictions"] = []
            self.profile_data["allergens"] = []
            return True

        # Common restrictions
        restrictions = []
        allergens = []

        restriction_keywords = {
            "vegetarian": "vegetarian",
            "vegan": "vegan",
            "dairy-free": "dairy-free",
            "gluten-free": "gluten-free",
            "low-carb": "low-carb",
            "keto": "keto",
            "paleo": "paleo",
        }

        allergen_keywords = {
            "nut": "nuts",
            "peanut": "peanuts",
            "shellfish": "shellfish",
            "dairy": "dairy",
            "egg": "eggs",
            "soy": "soy",
            "wheat": "wheat",
            "fish": "fish",
        }

        for keyword, value in restriction_keywords.items():
            if keyword in user_input_lower:
                restrictions.append(value)

        for keyword, value in allergen_keywords.items():
            if keyword in user_input_lower:
                allergens.append(value)

        self.profile_data["dietary_restrictions"] = restrictions
        self.profile_data["allergens"] = allergens

        return True

    # ==================== Step 3: Cuisines ====================

    def step_cuisines(self, user_input: Optional[str] = None) -> str | bool:
        """Step 3: Ask about cuisine preferences."""
        if user_input is None:
            return """
**Q3: What cuisines do you enjoy?**

Pick any that appeal to you:
☐ Italian  ☐ Mexican  ☐ Asian (Chinese/Thai/Japanese)
☐ American ☐ Mediterranean ☐ Indian

Or just tell me (e.g., "Italian, Mexican, and Thai"):
""".strip()

        # Parse answer
        cuisines = []
        cuisine_keywords = {
            "italian": "italian",
            "mexican": "mexican",
            "asian": "asian",
            "chinese": "chinese",
            "thai": "thai",
            "japanese": "japanese",
            "american": "american",
            "mediterranean": "mediterranean",
            "indian": "indian",
            "greek": "greek",
            "korean": "korean",
            "french": "french",
        }

        user_input_lower = user_input.lower()

        for keyword, value in cuisine_keywords.items():
            if keyword in user_input_lower:
                cuisines.append(value)

        # If no cuisines found, default to a few popular ones
        if not cuisines:
            cuisines = ["italian", "mexican", "american"]

        self.profile_data["favorite_cuisines"] = cuisines

        return True

    # ==================== Step 4: Cooking Time ====================

    def step_cooking_time(self, user_input: Optional[str] = None) -> str | bool:
        """Step 4: Ask about available cooking time."""
        if user_input is None:
            return """
**Q4: How much time do you have for cooking on weeknights?**

A) 15-30 minutes (quick meals)
B) 30-45 minutes (moderate)
C) 45-60 minutes (I enjoy cooking)
D) 60+ minutes (I love spending time in the kitchen)

Your answer (A/B/C/D or tell me in your own words):
""".strip()

        # Parse answer
        user_input_lower = user_input.lower()

        time_mapping = {
            "a": (30, 60),
            "b": (45, 90),
            "c": (60, 120),
            "d": (90, 180),
        }

        # Check for letter choice
        for letter, (weeknight, weekend) in time_mapping.items():
            if letter in user_input_lower or f"option {letter}" in user_input_lower:
                self.profile_data["max_weeknight_cooking_time"] = weeknight
                self.profile_data["max_weekend_cooking_time"] = weekend
                return True

        # Try to parse numbers
        import re

        numbers = re.findall(r"\d+", user_input)
        if numbers:
            time = int(numbers[0])
            self.profile_data["max_weeknight_cooking_time"] = time
            self.profile_data["max_weekend_cooking_time"] = time * 2
            return True

        # Default to moderate
        self.profile_data["max_weeknight_cooking_time"] = 45
        self.profile_data["max_weekend_cooking_time"] = 90
        return True

    # ==================== Step 5: Dislikes (Optional) ====================

    def step_dislikes(self, user_input: Optional[str] = None) -> str | bool:
        """Step 5: Ask about disliked ingredients (optional)."""
        if user_input is None:
            return """
**Q5: Any ingredients you really dislike?** (optional)

Examples: "olives, anchovies, cilantro"

Your answer (or type "skip"):
""".strip()

        # Parse answer
        user_input_lower = user_input.lower()

        if "skip" in user_input_lower or "none" in user_input_lower or "no" in user_input_lower:
            self.profile_data["disliked_ingredients"] = []
            return True

        # Split by commas and clean up
        dislikes = [ingredient.strip() for ingredient in user_input.split(",")]
        self.profile_data["disliked_ingredients"] = dislikes

        return True

    # ==================== Step 6: Spice Tolerance (Optional) ====================

    def step_spice_tolerance(self, user_input: Optional[str] = None) -> str | bool:
        """Step 6: Ask about spice tolerance (optional)."""
        if user_input is None:
            return """
**Q6: How do you feel about spicy food?** (optional)

A) Mild - I prefer mild flavors
B) Medium - Some heat is good
C) Spicy - Bring on the heat!

Your answer (A/B/C or type "skip"):
""".strip()

        # Parse answer
        user_input_lower = user_input.lower()

        if "skip" in user_input_lower:
            self.profile_data["spice_tolerance"] = "medium"
            return True

        spice_mapping = {
            "a": "mild",
            "b": "medium",
            "c": "spicy",
            "mild": "mild",
            "medium": "medium",
            "spicy": "spicy",
        }

        for keyword, value in spice_mapping.items():
            if keyword in user_input_lower:
                self.profile_data["spice_tolerance"] = value
                return True

        # Default to medium
        self.profile_data["spice_tolerance"] = "medium"
        return True

    # ==================== Summary & Confirmation ====================

    def _summary_and_confirm(self) -> str:
        """Generate summary of collected data."""
        household = self.profile_data.get("household_size", 4)
        cooking_for = self.profile_data.get("cooking_for", {"adults": 2, "kids": 2})
        restrictions = self.profile_data.get("dietary_restrictions", [])
        allergens = self.profile_data.get("allergens", [])
        cuisines = self.profile_data.get("favorite_cuisines", [])
        weeknight_time = self.profile_data.get("max_weeknight_cooking_time", 45)
        dislikes = self.profile_data.get("disliked_ingredients", [])
        spice = self.profile_data.get("spice_tolerance", "medium")

        # Format dietary
        dietary_text = "None"
        if restrictions or allergens:
            dietary_parts = []
            if restrictions:
                dietary_parts.append(", ".join(restrictions))
            if allergens:
                dietary_parts.append(f"Allergies: {', '.join(allergens)}")
            dietary_text = " | ".join(dietary_parts)

        # Format dislikes
        dislikes_text = "None" if not dislikes else ", ".join(dislikes)

        summary = f"""
**Perfect! Here's your profile:**

👥 Cooking for: {household} people ({cooking_for['adults']} adults, {cooking_for['kids']} kids)
🚫 Dietary: {dietary_text}
🌍 Favorite cuisines: {", ".join(c.title() for c in cuisines)}
⏱️ Weeknight cooking: {weeknight_time} minutes max
👎 Dislikes: {dislikes_text}
🌶️ Spice: {spice.title()} heat

Does this look right? Type "yes" to confirm, "no" to start over, or "edit" to make changes.
""".strip()

        return summary

    def _handle_confirmation(self, user_input: str) -> Tuple[bool, str]:
        """Handle user's confirmation response."""
        user_input_lower = user_input.lower()

        if "yes" in user_input_lower or "confirm" in user_input_lower or "correct" in user_input_lower:
            # Save profile to database
            profile = UserProfile(
                household_size=self.profile_data.get("household_size", 4),
                cooking_for=self.profile_data.get("cooking_for", {"adults": 2, "kids": 2}),
                dietary_restrictions=self.profile_data.get("dietary_restrictions", []),
                allergens=self.profile_data.get("allergens", []),
                favorite_cuisines=self.profile_data.get("favorite_cuisines", []),
                disliked_ingredients=self.profile_data.get("disliked_ingredients", []),
                preferred_proteins=self.profile_data.get("preferred_proteins", []),
                spice_tolerance=self.profile_data.get("spice_tolerance", "medium"),
                max_weeknight_cooking_time=self.profile_data.get("max_weeknight_cooking_time", 45),
                max_weekend_cooking_time=self.profile_data.get("max_weekend_cooking_time", 90),
                budget_per_week=self.profile_data.get("budget_per_week"),
                variety_preference="high",
                health_focus=None,
                onboarding_completed=True,
                created_at=datetime.now(),
                updated_at=datetime.now(),
            )

            self.db.save_user_profile(profile)

            success_message = """
✅ Great! Your profile has been saved.

You're all set! I can now help you:
- Plan weekly meals tailored to your preferences
- Generate smart shopping lists
- Get cooking guidance with tips and substitutions

What would you like to do first?
- "Plan this week's meals"
- "Show me dinner ideas"
- "Help me with tonight's cooking"
""".strip()

            return True, success_message

        elif "no" in user_input_lower or "start over" in user_input_lower:
            # Restart onboarding
            return False, self.start()

        elif "edit" in user_input_lower:
            # TODO: Implement editing specific fields
            return False, "Editing not yet implemented. Type 'yes' to confirm or 'no' to start over."

        else:
            # Didn't understand
            return False, self._summary_and_confirm() + "\n\nPlease type 'yes', 'no', or 'edit'."


def check_onboarding_status(db: DatabaseInterface) -> bool:
    """
    Check if user needs onboarding.

    Args:
        db: Database interface

    Returns:
        True if onboarding is complete
    """
    return db.is_onboarded()


def run_onboarding(db: DatabaseInterface) -> OnboardingFlow:
    """
    Start a new onboarding flow.

    Args:
        db: Database interface

    Returns:
        OnboardingFlow instance
    """
    flow = OnboardingFlow(db)
    logger.info("Starting onboarding flow")
    return flow
