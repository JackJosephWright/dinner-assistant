"""
Integration tests for onboarding flow.

Tests the complete onboarding workflow from start to finish.
These tests will FAIL until we implement the integration.
"""

import pytest
from datetime import datetime

from src.onboarding import OnboardingFlow, check_onboarding_status, run_onboarding
from src.data.database import DatabaseInterface


class TestOnboardingFlowIntegration:
    """Test complete onboarding flow with database."""

    def test_onboarding_creates_profile_in_database(self, db):
        """Test that completing onboarding saves profile to database."""
        # Arrange - Start onboarding
        flow = OnboardingFlow(db)
        welcome = flow.start()

        # Act - Answer all questions
        # Q1: Household size
        is_done, msg = flow.process_answer("4 people (2 adults, 2 kids)")
        assert not is_done

        # Q2: Dietary restrictions
        is_done, msg = flow.process_answer("dairy-free and peanut allergies")
        assert not is_done

        # Q3: Cuisines
        is_done, msg = flow.process_answer("Italian, Mexican, and Thai")
        assert not is_done

        # Q4: Cooking time
        is_done, msg = flow.process_answer("B")  # 30-45 minutes
        assert not is_done

        # Q5: Dislikes
        is_done, msg = flow.process_answer("olives, anchovies")
        assert not is_done

        # Q6: Spice tolerance
        is_done, msg = flow.process_answer("medium")
        assert not is_done  # Should show summary

        # Q7: Confirm
        is_done, msg = flow.process_answer("yes")

        # Assert - Profile saved and onboarding complete
        assert is_done
        assert "all set" in msg.lower() or "ready" in msg.lower()

        profile = db.get_user_profile()
        assert profile is not None
        assert profile.household_size == 4
        assert profile.onboarding_completed is True
        assert "dairy-free" in profile.dietary_restrictions
        assert "peanuts" in profile.allergens

    def test_onboarding_status_check(self, db):
        """Test checking if user needs onboarding."""
        # Before onboarding
        assert check_onboarding_status(db) is False

        # Complete onboarding
        flow = OnboardingFlow(db)
        flow.start()
        flow.process_answer("2 people")
        flow.process_answer("none")
        flow.process_answer("italian")
        flow.process_answer("A")
        flow.process_answer("skip")
        flow.process_answer("skip")
        flow.process_answer("yes")

        # After onboarding
        assert check_onboarding_status(db) is True

    def test_onboarding_restart_on_no(self, db):
        """Test that answering 'no' restarts onboarding."""
        # Arrange
        flow = OnboardingFlow(db)
        flow.start()

        # Answer through all questions
        flow.process_answer("4 people")
        flow.process_answer("none")
        flow.process_answer("italian")
        flow.process_answer("A")
        flow.process_answer("skip")
        flow.process_answer("skip")

        # Act - Say no to summary
        is_done, msg = flow.process_answer("no")

        # Assert - Should restart
        assert not is_done
        assert "welcome" in msg.lower() or "q1" in msg.lower()

    def test_onboarding_minimal_answers(self, db):
        """Test onboarding with minimal answers (quick setup)."""
        # Arrange
        flow = OnboardingFlow(db)
        flow.start()

        # Act - Give minimal answers
        flow.process_answer("1 person")  # Changed from "just me" to parseable number
        flow.process_answer("none")
        flow.process_answer("anything")  # Should default
        flow.process_answer("B")
        flow.process_answer("skip")
        flow.process_answer("skip")
        is_done, msg = flow.process_answer("yes")

        # Assert - Profile created with defaults
        assert is_done
        profile = db.get_user_profile()
        assert profile is not None
        assert profile.household_size >= 1
        assert profile.onboarding_completed is True

    def test_run_onboarding_helper(self, db):
        """Test the run_onboarding() helper function."""
        # Act
        flow = run_onboarding(db)

        # Assert
        assert isinstance(flow, OnboardingFlow)
        assert flow.db == db
        assert flow.current_step == 0


class TestOnboardingEdgeCases:
    """Test edge cases and error handling."""

    def test_onboarding_invalid_household_size(self, db):
        """Test handling of invalid household size input."""
        flow = OnboardingFlow(db)
        flow.start()

        # Try invalid input
        is_done, msg = flow.process_answer("abc invalid")

        # Should ask again or use default
        assert not is_done
        # Either re-asks or continues with default

    def test_onboarding_step_out_of_order(self, db):
        """Test that steps happen in correct order."""
        flow = OnboardingFlow(db)
        flow.start()

        # Step 1
        assert "q1" in flow.get_current_question().lower() or "how many" in flow.get_current_question().lower()

        flow.process_answer("4 people")

        # Step 2
        assert "q2" in flow.get_current_question().lower() or "dietary" in flow.get_current_question().lower()

    def test_onboarding_multiple_runs_updates_profile(self, db):
        """Test that running onboarding again updates existing profile."""
        # First onboarding
        flow1 = OnboardingFlow(db)
        flow1.start()
        flow1.process_answer("2 people")
        flow1.process_answer("vegetarian")
        flow1.process_answer("italian")
        flow1.process_answer("A")
        flow1.process_answer("skip")
        flow1.process_answer("skip")
        flow1.process_answer("yes")

        profile1 = db.get_user_profile()
        assert profile1.household_size == 2

        # Second onboarding (update)
        flow2 = OnboardingFlow(db)
        flow2.start()
        flow2.process_answer("4 people")
        flow2.process_answer("none")
        flow2.process_answer("mexican")
        flow2.process_answer("B")
        flow2.process_answer("skip")
        flow2.process_answer("skip")
        flow2.process_answer("yes")

        profile2 = db.get_user_profile()
        assert profile2.household_size == 4
        assert profile2.id == 1  # Still same profile
