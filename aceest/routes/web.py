"""Server-rendered dashboard - the HTML face of the same domain services."""

from __future__ import annotations

from typing import Any

from flask import Blueprint, flash, redirect, render_template, request, url_for

from .. import db
from ..errors import ACEestError, ConflictError, NotFoundError
from ..programs import SITE_METRICS, WORKOUT_TYPES, get_program, list_programs
from ..services import (
    build_client_profile,
    summarise_adherence,
    validate_adherence,
    validate_week,
)

web_bp = Blueprint("web", __name__)


@web_bp.get("/")
def dashboard() -> Any:
    clients = db.list_clients()
    total = len(clients)
    return render_template(
        "dashboard.html",
        clients=clients,
        programs=list_programs(),
        metrics=SITE_METRICS,
        total_clients=total,
        capacity_pct=round(total / SITE_METRICS["capacity_users"] * 100, 1),
    )


@web_bp.post("/clients")
def add_client() -> Any:
    try:
        profile = build_client_profile(request.form.to_dict())
        if db.find_client_by_name(profile["name"]) is not None:
            raise ConflictError(f"client '{profile['name']}' already exists")
        db.insert_client(profile)
    except ACEestError as error:
        flash(error.message, "error")
        return redirect(url_for("web.dashboard")), 303

    flash(f"Client {profile['name']} enrolled on {profile['program_name']}", "success")
    return redirect(url_for("web.client_detail", name=profile["name"])), 303


@web_bp.get("/clients/<name>")
def client_detail(name: str) -> Any:
    client = db.find_client_by_name(name)
    if client is None:
        raise NotFoundError(f"client '{name}' not found")

    entries = db.list_progress(client["id"])
    return render_template(
        "client.html",
        client=client,
        program=get_program(client["program"]),
        progress=entries,
        summary=summarise_adherence(entries),
        workouts=db.list_workouts(client["id"]),
        workout_types=WORKOUT_TYPES,
    )


@web_bp.post("/clients/<name>/progress")
def add_progress(name: str) -> Any:
    client = db.find_client_by_name(name)
    if client is None:
        raise NotFoundError(f"client '{name}' not found")

    try:
        db.upsert_progress(
            client["id"],
            validate_week(request.form.get("week")),
            validate_adherence(request.form.get("adherence")),
        )
        flash("Weekly adherence recorded", "success")
    except ACEestError as error:
        flash(error.message, "error")

    return redirect(url_for("web.client_detail", name=client["name"])), 303


@web_bp.get("/health")
def health() -> Any:
    from .. import __version__

    return {"status": "healthy", "version": __version__}
