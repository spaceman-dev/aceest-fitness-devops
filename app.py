"""WSGI entrypoint for the ACEest Fitness & Gym service.

Local dev:   python app.py
Production:  gunicorn "app:app" --bind 0.0.0.0:5000
"""

from __future__ import annotations

import os

from aceest import create_app

app = create_app()

if __name__ == "__main__":
    app.run(
        host=os.environ.get("HOST", "127.0.0.1"),
        port=int(os.environ.get("PORT", "5000")),
        debug=os.environ.get("FLASK_ENV") == "development",
    )
