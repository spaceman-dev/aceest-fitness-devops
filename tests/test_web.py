"""Tests for the server-rendered dashboard and the app factory wiring."""

from __future__ import annotations

from aceest import create_app
from aceest.config import DevelopmentConfig, ProductionConfig, TestingConfig, get_config


class TestAppFactory:
    def test_testing_config_is_applied(self, app):
        assert app.config["TESTING"] is True

    def test_factory_resolves_named_configs(self):
        assert get_config("development") is DevelopmentConfig
        assert get_config("testing") is TestingConfig
        assert get_config("production") is ProductionConfig
        assert get_config("nonsense") is ProductionConfig

    def test_two_apps_are_independent(self, tmp_path):
        first = create_app("testing", overrides={"DATABASE": str(tmp_path / "a.db")})
        second = create_app("testing", overrides={"DATABASE": str(tmp_path / "b.db")})
        assert first is not second
        assert first.config["DATABASE"] != second.config["DATABASE"]


class TestDashboard:
    def test_dashboard_renders(self, client):
        response = client.get("/")
        assert response.status_code == 200
        assert b"ACEest FUNCTIONAL FITNESS" in response.data
        assert b"Program catalogue" in response.data

    def test_dashboard_lists_enrolled_clients(self, client, enrolled_client):
        response = client.get("/")
        assert b"Ravi Kumar" in response.data

    def test_web_health_endpoint(self, client):
        response = client.get("/health")
        assert response.status_code == 200
        assert response.get_json()["status"] == "healthy"

    def test_static_stylesheet_is_served(self, client):
        assert client.get("/static/css/style.css").status_code == 200


class TestClientForm:
    def test_form_submission_creates_client_and_redirects(self, client):
        response = client.post(
            "/clients",
            data={
                "name": "Meera Nair",
                "age": "28",
                "height_cm": "162",
                "weight_kg": "58",
                "program": "FL3",
            },
        )
        assert response.status_code == 303
        assert "/clients/Meera%20Nair" in response.headers["Location"]

        detail = client.get("/clients/Meera Nair")
        assert detail.status_code == 200
        assert b"1276" in detail.data  # 58 kg x 22 kcal/kg

    def test_invalid_form_redirects_back_with_error_flash(self, client):
        response = client.post(
            "/clients",
            data={"name": "X", "age": "28", "height_cm": "162",
                  "weight_kg": "58", "program": "FL3"},
            follow_redirects=True,
        )
        assert response.status_code == 200
        assert b"must be 2-50 characters" in response.data

    def test_missing_client_page_returns_404(self, client):
        assert client.get("/clients/Nobody").status_code == 404


class TestProgressForm:
    def test_logging_progress_from_the_ui(self, client, enrolled_client):
        response = client.post(
            "/clients/Ravi Kumar/progress",
            data={"week": "W1", "adherence": "90"},
            follow_redirects=True,
        )
        assert response.status_code == 200
        assert b"Weekly adherence recorded" in response.data
        assert b"90%" in response.data

    def test_invalid_progress_shows_error_flash(self, client, enrolled_client):
        response = client.post(
            "/clients/Ravi Kumar/progress",
            data={"week": "later", "adherence": "90"},
            follow_redirects=True,
        )
        assert b"must look like" in response.data

    def test_progress_for_unknown_client_is_404(self, client):
        response = client.post(
            "/clients/Ghost/progress", data={"week": "W1", "adherence": "90"}
        )
        assert response.status_code == 404
