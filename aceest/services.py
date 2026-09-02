"""Pure business logic for ACEest Fitness & Gym.

Every function here is free of Flask and SQLite so that it can be unit tested in
isolation. The rules are the ones defined by the desktop baselines:

* daily calorie target  = weight (kg) x program factor  (``Aceestver-1.1.py``)
* BMI                   = weight (kg) / height (m)^2    (``Aceestver-2.2.4.py``)
* adherence             = weekly percentage, 0-100      (``Aceestver-2.2.1.py``)
"""

from __future__ import annotations

import re
from collections.abc import Iterable, Mapping
from datetime import date, datetime
from typing import Any

from .errors import ValidationError
from .programs import WORKOUT_TYPES, get_program

NAME_PATTERN = re.compile(r"^[A-Za-z][A-Za-z0-9 .'\-]{1,49}$")
WEEK_PATTERN = re.compile(r"^(?:W|w)?(\d{1,3})$")

MIN_AGE, MAX_AGE = 10, 100
MIN_HEIGHT_CM, MAX_HEIGHT_CM = 90.0, 250.0
MIN_WEIGHT_KG, MAX_WEIGHT_KG = 25.0, 300.0
MAX_SESSION_MINUTES = 480


def _require(payload: Mapping[str, Any], field: str) -> Any:
    if field not in payload or payload[field] is None or payload[field] == "":
        raise ValidationError(f"'{field}' is required", field=field)
    return payload[field]


def _as_number(value: Any, field: str) -> float:
    if isinstance(value, bool):
        raise ValidationError(f"'{field}' must be a number", field=field)
    try:
        return float(value)
    except (TypeError, ValueError):
        raise ValidationError(f"'{field}' must be a number", field=field) from None


def _as_int(value: Any, field: str) -> int:
    number = _as_number(value, field)
    if number != int(number):
        raise ValidationError(f"'{field}' must be a whole number", field=field)
    return int(number)


def validate_name(value: Any) -> str:
    if not isinstance(value, str):
        raise ValidationError("'name' must be text", field="name")
    name = " ".join(value.split())
    if not NAME_PATTERN.match(name):
        raise ValidationError(
            "'name' must be 2-50 characters and start with a letter", field="name"
        )
    return name


def validate_age(value: Any) -> int:
    age = _as_int(value, "age")
    if not MIN_AGE <= age <= MAX_AGE:
        raise ValidationError(
            f"'age' must be between {MIN_AGE} and {MAX_AGE}", field="age"
        )
    return age


def validate_height_cm(value: Any) -> float:
    height = _as_number(value, "height_cm")
    if not MIN_HEIGHT_CM <= height <= MAX_HEIGHT_CM:
        raise ValidationError(
            f"'height_cm' must be between {MIN_HEIGHT_CM} and {MAX_HEIGHT_CM}",
            field="height_cm",
        )
    return round(height, 1)


def validate_weight_kg(value: Any) -> float:
    weight = _as_number(value, "weight_kg")
    if not MIN_WEIGHT_KG <= weight <= MAX_WEIGHT_KG:
        raise ValidationError(
            f"'weight_kg' must be between {MIN_WEIGHT_KG} and {MAX_WEIGHT_KG}",
            field="weight_kg",
        )
    return round(weight, 1)


def validate_program(value: Any) -> dict[str, Any]:
    program = get_program(value) if isinstance(value, str) else None
    if program is None:
        raise ValidationError(f"unknown program '{value}'", field="program")
    return program


def validate_adherence(value: Any, field: str = "adherence") -> int:
    adherence = _as_int(value, field)
    if not 0 <= adherence <= 100:
        raise ValidationError(f"'{field}' must be between 0 and 100", field=field)
    return adherence


def validate_week(value: Any) -> str:
    if not isinstance(value, (str, int)):
        raise ValidationError("'week' must be text such as 'W1'", field="week")
    match = WEEK_PATTERN.match(str(value).strip())
    if not match:
        raise ValidationError("'week' must look like 'W1' or '1'", field="week")
    week_number = int(match.group(1))
    if not 1 <= week_number <= 520:
        raise ValidationError("'week' must be between 1 and 520", field="week")
    return f"W{week_number}"


def validate_iso_date(value: Any, field: str = "date") -> str:
    if value in (None, ""):
        return date.today().isoformat()
    if not isinstance(value, str):
        raise ValidationError(f"'{field}' must be an ISO date (YYYY-MM-DD)", field=field)
    try:
        return datetime.strptime(value.strip(), "%Y-%m-%d").date().isoformat()
    except ValueError:
        raise ValidationError(
            f"'{field}' must be an ISO date (YYYY-MM-DD)", field=field
        ) from None


def validate_workout_type(value: Any) -> str:
    if not isinstance(value, str):
        raise ValidationError("'workout_type' must be text", field="workout_type")
    for allowed in WORKOUT_TYPES:
        if allowed.lower() == value.strip().lower():
            return allowed
    raise ValidationError(
        f"'workout_type' must be one of {', '.join(WORKOUT_TYPES)}",
        field="workout_type",
    )


def validate_duration(value: Any) -> int:
    duration = _as_int(value, "duration_min")
    if not 1 <= duration <= MAX_SESSION_MINUTES:
        raise ValidationError(
            f"'duration_min' must be between 1 and {MAX_SESSION_MINUTES}",
            field="duration_min",
        )
    return duration


def calculate_calories(weight_kg: Any, program: Any) -> int:
    """Daily calorie target: ``weight x program factor`` (baseline formula)."""
    weight = validate_weight_kg(weight_kg)
    factor = validate_program(program)["factor"]
    return int(weight * factor)


def calculate_bmi(weight_kg: Any, height_cm: Any) -> float:
    weight = validate_weight_kg(weight_kg)
    height_m = validate_height_cm(height_cm) / 100.0
    return round(weight / (height_m * height_m), 1)


def classify_bmi(bmi: float) -> dict[str, str]:
    """BMI band + risk note, matching the baseline ``show_bmi_info`` thresholds."""
    if bmi < 18.5:
        return {
            "category": "Underweight",
            "risk": "Potential nutrient deficiency, low energy.",
        }
    if bmi < 25:
        return {"category": "Normal", "risk": "Low risk if active and strong."}
    if bmi < 30:
        return {
            "category": "Overweight",
            "risk": "Moderate risk; focus on adherence and progressive activity.",
        }
    return {
        "category": "Obese",
        "risk": "Higher risk; prioritize fat loss, consistency, and supervision.",
    }


def bmi_report(weight_kg: Any, height_cm: Any) -> dict[str, Any]:
    bmi = calculate_bmi(weight_kg, height_cm)
    return {"bmi": bmi, **classify_bmi(bmi)}


def target_weight_delta(current_weight_kg: Any, target_weight_kg: Any) -> float:
    """Kilograms still to lose (positive) or gain (negative)."""
    current = validate_weight_kg(current_weight_kg)
    target = validate_weight_kg(target_weight_kg)
    return round(current - target, 1)


def summarise_adherence(entries: Iterable[Mapping[str, Any]]) -> dict[str, Any]:
    """Aggregate weekly adherence records into a coaching summary."""
    values = [int(entry["adherence"]) for entry in entries]
    if not values:
        return {
            "weeks_logged": 0,
            "average_adherence": 0.0,
            "best_week": None,
            "latest_adherence": None,
            "trend": "no-data",
            "status": "No progress logged yet",
        }

    average = round(sum(values) / len(values), 1)
    if len(values) < 2:
        trend = "steady"
    elif values[-1] > values[-2]:
        trend = "improving"
    elif values[-1] < values[-2]:
        trend = "declining"
    else:
        trend = "steady"

    if average >= 90:
        status = "Elite consistency"
    elif average >= 75:
        status = "On track"
    elif average >= 50:
        status = "Needs attention"
    else:
        status = "At risk"

    return {
        "weeks_logged": len(values),
        "average_adherence": average,
        "best_week": max(values),
        "latest_adherence": values[-1],
        "trend": trend,
        "status": status,
    }


def build_client_profile(payload: Mapping[str, Any]) -> dict[str, Any]:
    """Validate an inbound client payload and derive its computed fields."""
    if not isinstance(payload, Mapping):
        raise ValidationError("request body must be a JSON object")

    name = validate_name(_require(payload, "name"))
    age = validate_age(_require(payload, "age"))
    height_cm = validate_height_cm(_require(payload, "height_cm"))
    weight_kg = validate_weight_kg(_require(payload, "weight_kg"))
    program = validate_program(_require(payload, "program"))

    target_weight = payload.get("target_weight_kg")
    target_weight_kg = (
        validate_weight_kg(target_weight) if target_weight not in (None, "") else None
    )

    target_adherence = payload.get("target_adherence")
    target_adherence_pct = (
        validate_adherence(target_adherence, field="target_adherence")
        if target_adherence not in (None, "")
        else 80
    )

    bmi = calculate_bmi(weight_kg, height_cm)
    return {
        "name": name,
        "age": age,
        "height_cm": height_cm,
        "weight_kg": weight_kg,
        "program": program["code"],
        "program_name": program["name"],
        "calories": int(weight_kg * program["factor"]),
        "bmi": bmi,
        "bmi_category": classify_bmi(bmi)["category"],
        "target_weight_kg": target_weight_kg,
        "target_adherence": target_adherence_pct,
    }
