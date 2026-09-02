"""Training program catalogue for ACEest Fitness & Gym.

Ported verbatim (business rules only) from the desktop baselines supplied with
the assignment: ``Aceestver-1.1.py`` (workout/diet charts + ``calorie_factor``)
and ``Aceestver-2.2.4.py`` (extended 5-day fat-loss and PPL variants).
"""

from __future__ import annotations

from typing import Any

PROGRAMS: dict[str, dict[str, Any]] = {
    "FL3": {
        "code": "FL3",
        "name": "Fat Loss (FL) - 3 day",
        "factor": 22,
        "description": "3-day full-body fat loss",
        "workout": (
            "Mon: Back Squat 5x5 + Core\n"
            "Tue: EMOM 20min Assault Bike\n"
            "Wed: Bench Press + 21-15-9\n"
            "Thu: Deadlift + Box Jumps\n"
            "Fri: Zone 2 Cardio 30min"
        ),
        "diet": (
            "Breakfast: Egg Whites + Oats\n"
            "Lunch: Grilled Chicken + Brown Rice\n"
            "Dinner: Fish Curry + Millet Roti\n"
            "Target: ~2000 kcal"
        ),
        "colour": "#e74c3c",
    },
    "FL5": {
        "code": "FL5",
        "name": "Fat Loss (FL) - 5 day",
        "factor": 24,
        "description": "5-day split, higher volume fat loss",
        "workout": (
            "Mon: Lower Strength + Intervals\n"
            "Tue: Upper Push + Conditioning\n"
            "Wed: Steady State 40min\n"
            "Thu: Upper Pull + Core\n"
            "Fri: Full Body Metcon"
        ),
        "diet": (
            "Breakfast: Oats Idli + Egg Whites\n"
            "Lunch: Grilled Fish + Quinoa\n"
            "Dinner: Chicken Curry + Millet Roti\n"
            "Target: ~2200 kcal"
        ),
        "colour": "#e67e22",
    },
    "MG": {
        "code": "MG",
        "name": "Muscle Gain (MG) - PPL",
        "factor": 35,
        "description": "Push/Pull/Legs hypertrophy",
        "workout": (
            "Mon: Squat 5x5\n"
            "Tue: Bench 5x5\n"
            "Wed: Deadlift 4x6\n"
            "Thu: Front Squat 4x8\n"
            "Fri: Incline Press 4x10\n"
            "Sat: Barbell Rows 4x10"
        ),
        "diet": (
            "Breakfast: Eggs + Peanut Butter Oats\n"
            "Lunch: Chicken Biryani\n"
            "Dinner: Mutton Curry + Rice\n"
            "Target: ~3200 kcal"
        ),
        "colour": "#2ecc71",
    },
    "BG": {
        "code": "BG",
        "name": "Beginner (BG)",
        "factor": 26,
        "description": "3-day simple beginner full-body",
        "workout": (
            "Full Body Circuit:\n"
            "- Air Squats\n"
            "- Ring Rows\n"
            "- Push-ups\n"
            "Focus: Technique & Consistency"
        ),
        "diet": (
            "Balanced Tamil Meals\n"
            "Idli / Dosa / Rice + Dal\n"
            "Protein Target: 120g/day"
        ),
        "colour": "#3498db",
    },
}

WORKOUT_TYPES = ("Strength", "Hypertrophy", "Cardio", "Mobility")

# Site metrics carried over from the baseline dashboard.
SITE_METRICS = {
    "capacity_users": 150,
    "area_sq_ft": 10000,
    "break_even_members": 250,
}


def list_programs() -> list[dict[str, Any]]:
    """Return the catalogue as a stable, ordered list."""
    return [PROGRAMS[code] for code in PROGRAMS]


def get_program(code: str) -> dict[str, Any] | None:
    """Look up a program by its code, case-insensitively."""
    if not isinstance(code, str):
        return None
    return PROGRAMS.get(code.strip().upper())
