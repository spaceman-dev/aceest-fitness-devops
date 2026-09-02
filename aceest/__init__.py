"""ACEest Fitness & Gym - Flask application factory."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from flask import Flask, jsonify, request
from werkzeug.exceptions import HTTPException

from . import db
from .config import get_config
from .errors import ACEestError

__version__ = "1.0.0"


def create_app(config_name: str | None = None,
               overrides: Mapping[str, Any] | None = None) -> Flask:
    """Build and configure a Flask application instance."""
    app = Flask(__name__, instance_relative_config=False)
    app.config.from_object(get_config(config_name))
    if overrides:
        app.config.update(overrides)
    app.json.sort_keys = False

    db.init_app(app)
    _register_blueprints(app)
    _register_error_handlers(app)

    return app


def _register_blueprints(app: Flask) -> None:
    from .routes.api import api_bp
    from .routes.web import web_bp

    app.register_blueprint(api_bp)
    app.register_blueprint(web_bp)


def _wants_json() -> bool:
    if request.path.startswith("/api"):
        return True
    return request.accept_mimetypes.best == "application/json"


def _register_error_handlers(app: Flask) -> None:
    @app.errorhandler(ACEestError)
    def handle_domain_error(error: ACEestError):
        return jsonify(error.to_dict()), error.status_code

    @app.errorhandler(HTTPException)
    def handle_http_error(error: HTTPException):
        if _wants_json():
            payload = {"error": error.name, "message": error.description}
            return jsonify(payload), error.code or 500
        return error

    @app.errorhandler(Exception)
    def handle_unexpected_error(error: Exception):  # pragma: no cover - safety net
        app.logger.exception("Unhandled error: %s", error)
        return jsonify({"error": "InternalServerError",
                        "message": "An unexpected error occurred"}), 500
