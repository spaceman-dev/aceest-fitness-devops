"""Shared pytest fixtures for the ACEest Fitness test suite."""

from __future__ import annotations

import pytest

from aceest import create_app


@pytest.fixture()
def app(tmp_path):
    """A Flask app bound to a throwaway SQLite file, fresh for every test."""
    application = create_app(
        "testing",
        overrides={
            "DATABASE": str(tmp_path / "aceest_test.db"),
            "SECRET_KEY": "test-secret-key",
            "WTF_CSRF_ENABLED": False,
        },
    )
    yield application


@pytest.fixture()
def client(app):
    return app.test_client()


@pytest.fixture()
def sample_client_payload():
    return {
        "name": "Ravi Kumar",
        "age": 32,
        "height_cm": 175,
        "weight_kg": 80,
        "program": "MG",
        "target_adherence": 85,
    }


@pytest.fixture()
def enrolled_client(client, sample_client_payload):
    response = client.post("/api/clients", json=sample_client_payload)
    assert response.status_code == 201
    return response.get_json()
