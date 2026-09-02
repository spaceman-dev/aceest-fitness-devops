"""Environment driven configuration objects."""

from __future__ import annotations

import os
import tempfile


class BaseConfig:
    """Defaults shared by every environment."""

    # Never ships a hard-coded production secret: fall back to a random value.
    SECRET_KEY = os.environ.get("SECRET_KEY") or os.urandom(32).hex()
    DATABASE = os.environ.get("ACEEST_DB", "/tmp/aceest_fitness.db")
    TESTING = False
    DEBUG = False


class DevelopmentConfig(BaseConfig):
    DEBUG = True
    DATABASE = os.environ.get("ACEEST_DB", "aceest_fitness.db")


class TestingConfig(BaseConfig):
    TESTING = True
    # A file (not ``:memory:``) so every request-scoped connection sees the
    # same data during a test run.
    DATABASE = os.environ.get(
        "ACEEST_DB", os.path.join(tempfile.gettempdir(), "aceest_test.db")
    )


class ProductionConfig(BaseConfig):
    DEBUG = False


CONFIGS = {
    "development": DevelopmentConfig,
    "testing": TestingConfig,
    "production": ProductionConfig,
}


def get_config(name: str | None = None) -> type[BaseConfig]:
    key = (name or os.environ.get("FLASK_ENV") or "production").strip().lower()
    return CONFIGS.get(key, ProductionConfig)
