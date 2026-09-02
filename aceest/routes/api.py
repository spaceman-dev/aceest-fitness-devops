"""JSON REST API for ACEest Fitness & Gym."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from flask import Blueprint, jsonify, request

from .. import db
from ..errors import ConflictError, NotFoundError, ValidationError
from ..programs import SITE_METRICS, WORKOUT_TYPES, get_program, list_programs
from ..services import (
    bmi_report,
    build_client_profile,
    calculate_calories,
    summarise_adherence,
    validate_adherence,
    validate_duration,
    validate_iso_date,
    validate_program,
    validate_week,
    validate_weight_kg,
    validate_workout_type,
)

api_bp = Blueprint("api", __name__, url_prefix="/api")

MAX_NOTE_LENGTH = 280


def _json_body() -> Mapping[str, Any]:
    body = request.get_json(silent=True)
    if body is None:
        raise ValidationError("request body must be valid JSON")
    if not isinstance(body, Mapping):
        raise ValidationError("request body must be a JSON object")
    return body


def _client_or_404(name: str) -> dict[str, Any]:
    client = db.find_client_by_name(name)
    if client is None:
        raise NotFoundError(f"client '{name}' not found")
    return client


def _decorate(client: Mapping[str, Any]) -> dict[str, Any]:
    """Attach catalogue details that are derived, not stored."""
    program = get_program(client["program"]) or {}
    enriched = dict(client)
    enriched["program_name"] = program.get("name", client["program"])
    enriched["workout_plan"] = program.get("workout", "")
    enriched["diet_plan"] = program.get("diet", "")
    return enriched


@api_bp.get("/health")
def health() -> Any:
    from .. import __version__

    return jsonify({"status": "healthy", "service": "aceest-fitness", "version": __version__})


@api_bp.get("/programs")
def programs() -> Any:
    return jsonify({"programs": list_programs(), "count": len(list_programs())})


@api_bp.get("/programs/<code>")
def program_detail(code: str) -> Any:
    program = get_program(code)
    if program is None:
        raise NotFoundError(f"program '{code}' not found")
    return jsonify(program)


@api_bp.post("/calories")
def calories() -> Any:
    body = _json_body()
    if "weight_kg" not in body:
        raise ValidationError("'weight_kg' is required", field="weight_kg")
    if "program" not in body:
        raise ValidationError("'program' is required", field="program")

    weight = validate_weight_kg(body["weight_kg"])
    program = validate_program(body["program"])
    return jsonify(
        {
            "weight_kg": weight,
            "program": program["code"],
            "program_name": program["name"],
            "factor": program["factor"],
            "calories": calculate_calories(weight, program["code"]),
        }
    )


@api_bp.post("/bmi")
def bmi() -> Any:
    body = _json_body()
    if "weight_kg" not in body:
        raise ValidationError("'weight_kg' is required", field="weight_kg")
    if "height_cm" not in body:
        raise ValidationError("'height_cm' is required", field="height_cm")
    return jsonify(bmi_report(body["weight_kg"], body["height_cm"]))


@api_bp.get("/clients")
def get_clients() -> Any:
    clients = [_decorate(client) for client in db.list_clients()]
    return jsonify({"clients": clients, "count": len(clients)})


@api_bp.post("/clients")
def create_client() -> Any:
    profile = build_client_profile(_json_body())
    if db.find_client_by_name(profile["name"]) is not None:
        raise ConflictError(f"client '{profile['name']}' already exists")
    created = db.insert_client(profile)
    return jsonify(_decorate(created)), 201


@api_bp.get("/clients/<name>")
def get_client(name: str) -> Any:
    client = _client_or_404(name)
    entries = db.list_progress(client["id"])
    payload = _decorate(client)
    payload["progress"] = entries
    payload["progress_summary"] = summarise_adherence(entries)
    payload["workouts"] = db.list_workouts(client["id"])
    return jsonify(payload)


@api_bp.put("/clients/<name>")
def replace_client(name: str) -> Any:
    client = _client_or_404(name)
    body = dict(_json_body())
    body.setdefault("name", client["name"])
    profile = build_client_profile(body)

    clash = db.find_client_by_name(profile["name"])
    if clash is not None and clash["id"] != client["id"]:
        raise ConflictError(f"client '{profile['name']}' already exists")

    return jsonify(_decorate(db.update_client(client["id"], profile)))


@api_bp.delete("/clients/<name>")
def remove_client(name: str) -> Any:
    client = _client_or_404(name)
    db.delete_client(client["id"])
    return "", 204


@api_bp.get("/clients/<name>/progress")
def get_progress(name: str) -> Any:
    client = _client_or_404(name)
    entries = db.list_progress(client["id"])
    return jsonify(
        {
            "client": client["name"],
            "entries": entries,
            "summary": summarise_adherence(entries),
        }
    )


@api_bp.post("/clients/<name>/progress")
def log_progress(name: str) -> Any:
    client = _client_or_404(name)
    body = _json_body()
    if "week" not in body:
        raise ValidationError("'week' is required", field="week")
    if "adherence" not in body:
        raise ValidationError("'adherence' is required", field="adherence")

    entry = db.upsert_progress(
        client["id"], validate_week(body["week"]), validate_adherence(body["adherence"])
    )
    entries = db.list_progress(client["id"])
    return jsonify({"entry": entry, "summary": summarise_adherence(entries)}), 201


@api_bp.get("/clients/<name>/workouts")
def get_workouts(name: str) -> Any:
    client = _client_or_404(name)
    workouts = db.list_workouts(client["id"])
    total_minutes = sum(item["duration_min"] for item in workouts)
    return jsonify(
        {
            "client": client["name"],
            "workouts": workouts,
            "count": len(workouts),
            "total_minutes": total_minutes,
        }
    )


@api_bp.post("/clients/<name>/workouts")
def log_workout(name: str) -> Any:
    client = _client_or_404(name)
    body = _json_body()
    if "workout_type" not in body:
        raise ValidationError("'workout_type' is required", field="workout_type")
    if "duration_min" not in body:
        raise ValidationError("'duration_min' is required", field="duration_min")

    notes = body.get("notes", "")
    if not isinstance(notes, str):
        raise ValidationError("'notes' must be text", field="notes")
    if len(notes) > MAX_NOTE_LENGTH:
        raise ValidationError(
            f"'notes' must be {MAX_NOTE_LENGTH} characters or fewer", field="notes"
        )

    workout = db.insert_workout(
        client["id"],
        validate_iso_date(body.get("date")),
        validate_workout_type(body["workout_type"]),
        validate_duration(body["duration_min"]),
        notes.strip(),
    )
    return jsonify(workout), 201


@api_bp.get("/stats")
def stats() -> Any:
    clients = db.list_clients()
    total = len(clients)
    average_calories = (
        round(sum(client["calories"] for client in clients) / total, 1) if total else 0.0
    )
    by_program: dict[str, int] = {}
    for client in clients:
        by_program[client["program"]] = by_program.get(client["program"], 0) + 1

    return jsonify(
        {
            "total_clients": total,
            "average_calorie_target": average_calories,
            "clients_by_program": by_program,
            "workout_types": list(WORKOUT_TYPES),
            "site_metrics": SITE_METRICS,
            "capacity_used_pct": round(total / SITE_METRICS["capacity_users"] * 100, 1),
        }
    )
