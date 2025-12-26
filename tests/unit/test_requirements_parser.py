"""
Unit tests for requirements_parser.py

Tests the Python-first parser for multi-requirement meal planning requests.
"""

import pytest
import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "src"))

from requirements_parser import parse_requirements, DayRequirement


# Sample dates for testing
@pytest.fixture
def five_dates():
    """5 consecutive dates for testing."""
    return ["2025-01-06", "2025-01-07", "2025-01-08", "2025-01-09", "2025-01-10"]


@pytest.fixture
def four_dates():
    """4 consecutive dates for testing."""
    return ["2025-12-29", "2025-12-30", "2025-12-31", "2026-01-01"]


class TestSingleCuisinePerDay:
    """Test parsing single cuisine per day."""

    def test_monday_italian_tuesday_irish(self, five_dates):
        """Per-day cuisine assignment."""
        result = parse_requirements("monday italian, tuesday irish", five_dates)

        assert len(result) == 5
        assert result[0].cuisine == "italian"
        assert result[1].cuisine == "irish"
        assert result[2].cuisine is None  # Wednesday unspecified

    def test_abbreviated_days(self, five_dates):
        """Support abbreviated day names."""
        result = parse_requirements("mon mexican, tue thai, wed chinese", five_dates)

        assert result[0].cuisine == "mexican"
        assert result[1].cuisine == "thai"
        assert result[2].cuisine == "chinese"

    def test_surprise_me(self, four_dates):
        """Thursday surprise me."""
        result = parse_requirements("thursday surprise me", four_dates)

        # Thursday = index 3
        assert result[3].surprise is True
        assert result[3].cuisine is None


class TestAllDaysPattern:
    """Test 'all X' patterns that apply to every day."""

    def test_all_vegetarian(self, five_dates):
        """All days vegetarian."""
        result = parse_requirements("all vegetarian", five_dates)

        assert len(result) == 5
        for req in result:
            assert "vegetarian" in req.dietary_hard

    def test_all_italian(self, five_dates):
        """All days Italian."""
        result = parse_requirements("all italian", five_dates)

        for req in result:
            assert req.cuisine == "italian"


class TestGlobalCuisineWithoutDays:
    """Test implicit all-days when no day specified."""

    def test_italian_meals(self, five_dates):
        """'plan me italian meals' -> all days italian."""
        result = parse_requirements("plan me italian meals", five_dates)

        for req in result:
            assert req.cuisine == "italian"

    def test_mexican_food(self, five_dates):
        """'mexican food' -> all days mexican."""
        result = parse_requirements("mexican food", five_dates)

        for req in result:
            assert req.cuisine == "mexican"

    def test_make_me_a_meal_plan(self, five_dates):
        """Generic request with no constraints."""
        result = parse_requirements("make me a meal plan", five_dates)

        for req in result:
            assert req.cuisine is None
            assert req.dietary_hard == []
            assert req.dietary_soft == []


class TestDietaryConstraints:
    """Test dietary constraint parsing."""

    def test_vegetarian_hard_constraint(self, five_dates):
        """Vegetarian is a hard constraint."""
        result = parse_requirements("all vegetarian", five_dates)

        for req in result:
            assert "vegetarian" in req.dietary_hard
            assert "vegetarian" not in req.dietary_soft

    def test_vegan_hard_constraint(self, five_dates):
        """Vegan is a hard constraint."""
        result = parse_requirements("vegan meals", five_dates)

        for req in result:
            assert "vegan" in req.dietary_hard

    def test_kid_friendly_soft_constraint(self, five_dates):
        """Kid-friendly is a soft constraint."""
        result = parse_requirements("kid friendly meals", five_dates)

        for req in result:
            assert "kid-friendly" in req.dietary_soft
            assert "kid-friendly" not in req.dietary_hard

    def test_vegetarian_for_kids(self, four_dates):
        """Vegetarian (hard) + kid-friendly (soft)."""
        result = parse_requirements("wednesday vegetarian for kids", four_dates)

        # Wednesday = index 2
        assert "vegetarian" in result[2].dietary_hard
        assert "kid-friendly" in result[2].dietary_soft


class TestMultiDayRanges:
    """Test multi-day cuisine specifications."""

    def test_italian_monday_and_tuesday(self, five_dates):
        """Italian for Monday AND Tuesday."""
        result = parse_requirements("italian monday and tuesday", five_dates)

        assert result[0].cuisine == "italian"
        assert result[1].cuisine == "italian"
        assert result[2].cuisine is None  # Wednesday not specified


class TestMixedRequirements:
    """Test complex mixed requirements."""

    def test_full_week_mixed(self, four_dates):
        """Monday italian, tuesday irish, wednesday vegetarian for kids, thursday surprise."""
        result = parse_requirements(
            "monday italian, tuesday irish, wednesday vegetarian for kids, thursday surprise me",
            four_dates
        )

        # Monday = index 0
        assert result[0].cuisine == "italian"

        # Tuesday = index 1
        assert result[1].cuisine == "irish"

        # Wednesday = index 2
        assert "vegetarian" in result[2].dietary_hard
        assert "kid-friendly" in result[2].dietary_soft

        # Thursday = index 3
        assert result[3].surprise is True


class TestSynonymNormalization:
    """Test that synonyms are normalized correctly."""

    def test_veggie_to_vegetarian(self, five_dates):
        """'veggie' normalizes to 'vegetarian'."""
        result = parse_requirements("veggie meals", five_dates)

        for req in result:
            assert "vegetarian" in req.dietary_hard

    def test_kid_friendly_variants(self, five_dates):
        """Various kid-friendly spellings."""
        for phrase in ["kid friendly", "kid-friendly", "for kids"]:
            result = parse_requirements(f"{phrase} meals", five_dates)
            assert "kid-friendly" in result[0].dietary_soft, f"Failed for: {phrase}"


class TestUnhandledConstraints:
    """Test that unrecognized constraints are logged."""

    def test_unrecognized_ingredient_constraint(self, five_dates):
        """'pasta with red meat' -> unhandled logged."""
        result = parse_requirements("pasta with red meat", five_dates)

        # "pasta", "red", "meat" should be unhandled (not in canonical tags)
        # Note: some stop words are filtered
        assert any("pasta" in r.unhandled or "meat" in r.unhandled for r in result)

    def test_no_unhandled_for_known_tags(self, five_dates):
        """Known tags shouldn't be in unhandled."""
        result = parse_requirements("italian vegetarian", five_dates)

        for req in result:
            assert "italian" not in req.unhandled
            assert "vegetarian" not in req.unhandled


class TestEdgeCases:
    """Test edge cases and error handling."""

    def test_empty_dates(self):
        """Empty dates list returns empty requirements."""
        result = parse_requirements("italian", [])
        assert result == []

    def test_empty_message(self, five_dates):
        """Empty message returns default requirements."""
        result = parse_requirements("", five_dates)

        assert len(result) == 5
        for req in result:
            assert req.cuisine is None

    def test_more_days_than_dates(self, four_dates):
        """Day references beyond available dates are ignored."""
        result = parse_requirements("monday italian, friday japanese", four_dates)

        # Only 4 dates available (indices 0-3)
        # Friday = index 4, which is out of range
        assert result[0].cuisine == "italian"
        # Friday request ignored since we only have 4 dates
