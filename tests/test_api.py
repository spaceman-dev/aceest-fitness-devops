"""Endpoint tests for the JSON API using Flask's test client."""

from __future__ import annotations

import pytest


class TestHealthAndCatalogue:
    def test_health_reports_healthy(self, client):
        response = client.get("/api/health")
        assert response.status_code == 200
        body = response.get_json()
        assert body["status"] == "healthy"
        assert body["service"] == "aceest-fitness"

    def test_programs_listing(self, client):
        response = client.get("/api/programs")
        assert response.status_code == 200
        body = response.get_json()
        assert body["count"] == 4
        assert {p["code"] for p in body["programs"]} == {"FL3", "FL5", "MG", "BG"}

    def test_program_detail(self, client):
        response = client.get("/api/programs/mg")
        assert response.status_code == 200
        assert response.get_json()["factor"] == 35

    def test_unknown_program_returns_404_json(self, client):
        response = client.get("/api/programs/nope")
        assert response.status_code == 404
        assert response.get_json()["error"] == "NotFoundError"

    def test_unknown_api_route_returns_json_not_html(self, client):
        response = client.get("/api/does-not-exist")
        assert response.status_code == 404
        assert response.is_json


class TestCalculators:
    def test_calorie_endpoint(self, client):
        response = client.post("/api/calories", json={"weight_kg": 80, "program": "MG"})
        assert response.status_code == 200
        body = response.get_json()
        assert body["calories"] == 2800
        assert body["factor"] == 35

    @pytest.mark.parametrize(
        "payload",
        [
            {},
            {"weight_kg": 80},
            {"program": "MG"},
            {"weight_kg": -1, "program": "MG"},
            {"weight_kg": 80, "program": "UNKNOWN"},
        ],
    )
    def test_calorie_endpoint_rejects_bad_input(self, client, payload):
        response = client.post("/api/calories", json=payload)
        assert response.status_code == 400
        assert "message" in response.get_json()

    def test_calorie_endpoint_rejects_non_json_body(self, client):
        response = client.post("/api/calories", data="weight=80")
        assert response.status_code == 400

    def test_bmi_endpoint(self, client):
        response = client.post("/api/bmi", json={"weight_kg": 80, "height_cm": 180})
        assert response.status_code == 200
        body = response.get_json()
        assert body["bmi"] == 24.7
        assert body["category"] == "Normal"

    def test_bmi_endpoint_requires_height(self, client):
        response = client.post("/api/bmi", json={"weight_kg": 80})
        assert response.status_code == 400
        assert response.get_json()["field"] == "height_cm"


class TestClientLifecycle:
    def test_roster_starts_empty(self, client):
        body = client.get("/api/clients").get_json()
        assert body == {"clients": [], "count": 0}

    def test_create_client_returns_201_with_derived_fields(self, enrolled_client):
        assert enrolled_client["name"] == "Ravi Kumar"
        assert enrolled_client["calories"] == 2800
        assert enrolled_client["bmi"] == 26.1
        assert enrolled_client["program_name"] == "Muscle Gain (MG) - PPL"
        assert enrolled_client["workout_plan"].startswith("Mon: Squat 5x5")

    def test_created_client_appears_in_roster(self, client, enrolled_client):
        body = client.get("/api/clients").get_json()
        assert body["count"] == 1
        assert body["clients"][0]["name"] == enrolled_client["name"]

    def test_duplicate_name_returns_409(self, client, enrolled_client, sample_client_payload):
        response = client.post("/api/clients", json=sample_client_payload)
        assert response.status_code == 409
        assert response.get_json()["error"] == "ConflictError"

    def test_duplicate_check_is_case_insensitive(
        self, client, enrolled_client, sample_client_payload
    ):
        sample_client_payload["name"] = "ravi kumar"
        assert client.post("/api/clients", json=sample_client_payload).status_code == 409

    def test_fetch_single_client_includes_progress_and_workouts(self, client, enrolled_client):
        response = client.get("/api/clients/Ravi Kumar")
        assert response.status_code == 200
        body = response.get_json()
        assert body["progress"] == []
        assert body["workouts"] == []
        assert body["progress_summary"]["weeks_logged"] == 0

    def test_fetch_missing_client_returns_404(self, client):
        response = client.get("/api/clients/Nobody")
        assert response.status_code == 404
        assert response.get_json()["error"] == "NotFoundError"

    def test_update_client_recomputes_calories(self, client, enrolled_client, sample_client_payload):
        sample_client_payload["weight_kg"] = 90
        sample_client_payload["program"] = "FL3"
        response = client.put("/api/clients/Ravi Kumar", json=sample_client_payload)
        assert response.status_code == 200
        assert response.get_json()["calories"] == 90 * 22

    def test_update_missing_client_returns_404(self, client, sample_client_payload):
        assert client.put("/api/clients/Ghost", json=sample_client_payload).status_code == 404

    def test_delete_client(self, client, enrolled_client):
        assert client.delete("/api/clients/Ravi Kumar").status_code == 204
        assert client.get("/api/clients/Ravi Kumar").status_code == 404

    @pytest.mark.parametrize(
        ("field", "value"),
        [
            ("name", ""),
            ("age", 5),
            ("height_cm", 300),
            ("weight_kg", 0),
            ("program", "ZUMBA"),
            ("target_adherence", 150),
        ],
    )
    def test_invalid_field_returns_400(self, client, sample_client_payload, field, value):
        sample_client_payload[field] = value
        response = client.post("/api/clients", json=sample_client_payload)
        assert response.status_code == 400
        assert response.get_json()["field"] == field


class TestProgressTracking:
    def test_log_and_read_back_progress(self, client, enrolled_client):
        created = client.post(
            "/api/clients/Ravi Kumar/progress", json={"week": "W1", "adherence": 90}
        )
        assert created.status_code == 201
        assert created.get_json()["entry"]["adherence"] == 90

        client.post("/api/clients/Ravi Kumar/progress", json={"week": "2", "adherence": 95})
        body = client.get("/api/clients/Ravi Kumar/progress").get_json()
        assert [entry["week"] for entry in body["entries"]] == ["W1", "W2"]
        assert body["summary"]["average_adherence"] == 92.5
        assert body["summary"]["trend"] == "improving"

    def test_relogging_a_week_overwrites_it(self, client, enrolled_client):
        client.post("/api/clients/Ravi Kumar/progress", json={"week": "W1", "adherence": 50})
        client.post("/api/clients/Ravi Kumar/progress", json={"week": "W1", "adherence": 88})
        body = client.get("/api/clients/Ravi Kumar/progress").get_json()
        assert len(body["entries"]) == 1
        assert body["entries"][0]["adherence"] == 88

    def test_weeks_are_ordered_numerically_not_lexically(self, client, enrolled_client):
        for week in ("W10", "W2", "W1"):
            client.post(
                f"/api/clients/{enrolled_client['name']}/progress",
                json={"week": week, "adherence": 70},
            )
        body = client.get("/api/clients/Ravi Kumar/progress").get_json()
        assert [entry["week"] for entry in body["entries"]] == ["W1", "W2", "W10"]

    @pytest.mark.parametrize(
        "payload", [{}, {"week": "W1"}, {"adherence": 50}, {"week": "W1", "adherence": 120}]
    )
    def test_bad_progress_payload_returns_400(self, client, enrolled_client, payload):
        response = client.post("/api/clients/Ravi Kumar/progress", json=payload)
        assert response.status_code == 400

    def test_progress_for_missing_client_returns_404(self, client):
        response = client.post("/api/clients/Ghost/progress", json={"week": "W1", "adherence": 50})
        assert response.status_code == 404


class TestWorkoutLogging:
    def test_log_workout(self, client, enrolled_client):
        response = client.post(
            "/api/clients/Ravi Kumar/workouts",
            json={
                "date": "2026-09-01",
                "workout_type": "strength",
                "duration_min": 75,
                "notes": "Squat PR",
            },
        )
        assert response.status_code == 201
        body = response.get_json()
        assert body["workout_type"] == "Strength"
        assert body["duration_min"] == 75

    def test_workout_listing_totals_minutes(self, client, enrolled_client):
        for minutes in (60, 45):
            client.post(
                "/api/clients/Ravi Kumar/workouts",
                json={"workout_type": "Cardio", "duration_min": minutes},
            )
        body = client.get("/api/clients/Ravi Kumar/workouts").get_json()
        assert body["count"] == 2
        assert body["total_minutes"] == 105

    @pytest.mark.parametrize(
        "payload",
        [
            {},
            {"workout_type": "Cardio"},
            {"duration_min": 60},
            {"workout_type": "Yoga", "duration_min": 60},
            {"workout_type": "Cardio", "duration_min": 0},
            {"workout_type": "Cardio", "duration_min": 60, "date": "not-a-date"},
            {"workout_type": "Cardio", "duration_min": 60, "notes": "x" * 500},
        ],
    )
    def test_bad_workout_payload_returns_400(self, client, enrolled_client, payload):
        response = client.post("/api/clients/Ravi Kumar/workouts", json=payload)
        assert response.status_code == 400


class TestStats:
    def test_stats_on_empty_gym(self, client):
        body = client.get("/api/stats").get_json()
        assert body["total_clients"] == 0
        assert body["average_calorie_target"] == 0.0
        assert body["site_metrics"]["capacity_users"] == 150

    def test_stats_aggregate_by_program(self, client, sample_client_payload):
        client.post("/api/clients", json=sample_client_payload)
        client.post(
            "/api/clients",
            json={**sample_client_payload, "name": "Anita Rao", "program": "FL3", "weight_kg": 60},
        )
        body = client.get("/api/stats").get_json()
        assert body["total_clients"] == 2
        assert body["clients_by_program"] == {"MG": 1, "FL3": 1}
        assert body["average_calorie_target"] == round((2800 + 1320) / 2, 1)


class TestSecurityBoundaries:
    def test_sql_injection_attempt_is_treated_as_data(self, client, enrolled_client):
        response = client.get("/api/clients/Ravi'; DROP TABLE clients;--")
        assert response.status_code == 404
        # The roster must still be intact.
        assert client.get("/api/clients").get_json()["count"] == 1

    def test_html_in_name_is_rejected_by_validation(self, client, sample_client_payload):
        sample_client_payload["name"] = "<script>alert(1)</script>"
        assert client.post("/api/clients", json=sample_client_payload).status_code == 400
