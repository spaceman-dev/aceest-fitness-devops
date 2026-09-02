"""SQLite persistence layer.

Three tables - ``clients`` / ``progress`` / ``workouts`` - hold everything the
service stores. Every statement is parameterised; no string-built SQL.
"""

from __future__ import annotations

import sqlite3
from collections.abc import Mapping
from typing import Any

from flask import Flask, current_app, g

SCHEMA = """
CREATE TABLE IF NOT EXISTS clients (
    id                INTEGER PRIMARY KEY AUTOINCREMENT,
    name              TEXT    NOT NULL UNIQUE COLLATE NOCASE,
    age               INTEGER NOT NULL,
    height_cm         REAL    NOT NULL,
    weight_kg         REAL    NOT NULL,
    program           TEXT    NOT NULL,
    calories          INTEGER NOT NULL,
    bmi               REAL    NOT NULL,
    target_weight_kg  REAL,
    target_adherence  INTEGER NOT NULL DEFAULT 80,
    membership_status TEXT    NOT NULL DEFAULT 'Active',
    created_at        TEXT    NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS progress (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    client_id   INTEGER NOT NULL REFERENCES clients(id) ON DELETE CASCADE,
    week        TEXT    NOT NULL,
    adherence   INTEGER NOT NULL,
    logged_at   TEXT    NOT NULL DEFAULT (datetime('now')),
    UNIQUE (client_id, week)
);

CREATE TABLE IF NOT EXISTS workouts (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    client_id    INTEGER NOT NULL REFERENCES clients(id) ON DELETE CASCADE,
    date         TEXT    NOT NULL,
    workout_type TEXT    NOT NULL,
    duration_min INTEGER NOT NULL,
    notes        TEXT    NOT NULL DEFAULT ''
);
"""


def get_db() -> sqlite3.Connection:
    """Return the request-scoped connection, creating it on first use."""
    if "db" not in g:
        connection = sqlite3.connect(
            current_app.config["DATABASE"],
            detect_types=sqlite3.PARSE_DECLTYPES,
        )
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        g.db = connection
    return g.db


def close_db(_exception: BaseException | None = None) -> None:
    connection = g.pop("db", None)
    if connection is not None:
        connection.close()


def init_db() -> None:
    get_db().executescript(SCHEMA)
    get_db().commit()


def init_app(app: Flask) -> None:
    app.teardown_appcontext(close_db)
    with app.app_context():
        init_db()


def _row_to_dict(row: sqlite3.Row | None) -> dict[str, Any] | None:
    return dict(row) if row is not None else None


# ---------------------------------------------------------------- clients ----


def insert_client(profile: Mapping[str, Any]) -> dict[str, Any]:
    db = get_db()
    cursor = db.execute(
        """
        INSERT INTO clients (
            name, age, height_cm, weight_kg, program, calories, bmi,
            target_weight_kg, target_adherence
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            profile["name"],
            profile["age"],
            profile["height_cm"],
            profile["weight_kg"],
            profile["program"],
            profile["calories"],
            profile["bmi"],
            profile["target_weight_kg"],
            profile["target_adherence"],
        ),
    )
    db.commit()
    return find_client_by_id(cursor.lastrowid)


def update_client(client_id: int, profile: Mapping[str, Any]) -> dict[str, Any]:
    db = get_db()
    db.execute(
        """
        UPDATE clients
           SET name = ?, age = ?, height_cm = ?, weight_kg = ?, program = ?,
               calories = ?, bmi = ?, target_weight_kg = ?, target_adherence = ?
         WHERE id = ?
        """,
        (
            profile["name"],
            profile["age"],
            profile["height_cm"],
            profile["weight_kg"],
            profile["program"],
            profile["calories"],
            profile["bmi"],
            profile["target_weight_kg"],
            profile["target_adherence"],
            client_id,
        ),
    )
    db.commit()
    return find_client_by_id(client_id)


def delete_client(client_id: int) -> None:
    db = get_db()
    db.execute("DELETE FROM clients WHERE id = ?", (client_id,))
    db.commit()


def list_clients() -> list[dict[str, Any]]:
    rows = get_db().execute("SELECT * FROM clients ORDER BY name").fetchall()
    return [dict(row) for row in rows]


def find_client_by_id(client_id: int) -> dict[str, Any] | None:
    row = get_db().execute("SELECT * FROM clients WHERE id = ?", (client_id,)).fetchone()
    return _row_to_dict(row)


def find_client_by_name(name: str) -> dict[str, Any] | None:
    row = (
        get_db()
        .execute("SELECT * FROM clients WHERE name = ? COLLATE NOCASE", (name,))
        .fetchone()
    )
    return _row_to_dict(row)


def count_clients() -> int:
    return int(get_db().execute("SELECT COUNT(*) AS total FROM clients").fetchone()[0])


# --------------------------------------------------------------- progress ----


def upsert_progress(client_id: int, week: str, adherence: int) -> dict[str, Any]:
    db = get_db()
    db.execute(
        """
        INSERT INTO progress (client_id, week, adherence) VALUES (?, ?, ?)
        ON CONFLICT (client_id, week) DO UPDATE SET adherence = excluded.adherence
        """,
        (client_id, week, adherence),
    )
    db.commit()
    row = db.execute(
        "SELECT * FROM progress WHERE client_id = ? AND week = ?", (client_id, week)
    ).fetchone()
    return dict(row)


def list_progress(client_id: int) -> list[dict[str, Any]]:
    rows = (
        get_db()
        .execute(
            """
            SELECT * FROM progress
             WHERE client_id = ?
             ORDER BY CAST(SUBSTR(week, 2) AS INTEGER)
            """,
            (client_id,),
        )
        .fetchall()
    )
    return [dict(row) for row in rows]


# --------------------------------------------------------------- workouts ----


def insert_workout(
    client_id: int, workout_date: str, workout_type: str, duration_min: int, notes: str
) -> dict[str, Any]:
    db = get_db()
    cursor = db.execute(
        """
        INSERT INTO workouts (client_id, date, workout_type, duration_min, notes)
        VALUES (?, ?, ?, ?, ?)
        """,
        (client_id, workout_date, workout_type, duration_min, notes),
    )
    db.commit()
    row = db.execute("SELECT * FROM workouts WHERE id = ?", (cursor.lastrowid,)).fetchone()
    return dict(row)


def list_workouts(client_id: int) -> list[dict[str, Any]]:
    rows = (
        get_db()
        .execute(
            "SELECT * FROM workouts WHERE client_id = ? ORDER BY date DESC, id DESC",
            (client_id,),
        )
        .fetchall()
    )
    return [dict(row) for row in rows]
