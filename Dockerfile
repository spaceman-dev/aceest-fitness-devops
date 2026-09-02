# syntax=docker/dockerfile:1
#
# ACEest Fitness & Gym - multi-stage image.
#   builder : compiles dependencies into a virtualenv (no toolchain in runtime)
#   test    : builder + dev deps + test suite  ->  docker build --target test
#   runtime : slim, non-root production image  ->  docker build .   (default)

# ------------------------------------------------------------------ builder --
FROM python:3.12-slim AS builder

ENV PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /build

# Copied on its own so the dependency layer is cached across code changes.
COPY requirements.txt .
RUN python -m venv /opt/venv \
    && /opt/venv/bin/pip install --upgrade pip \
    && /opt/venv/bin/pip install -r requirements.txt

# --------------------------------------------------------------------- test --
# Quality gate: CI runs the Pytest suite inside this image so the tests execute
# against the exact dependency set the runtime image ships with.
FROM builder AS test

ENV PATH="/opt/venv/bin:$PATH" \
    FLASK_ENV=testing \
    PYTHONDONTWRITEBYTECODE=1

WORKDIR /app
COPY requirements.txt requirements-dev.txt pytest.ini .flake8 ./
RUN pip install -r requirements-dev.txt

COPY app.py ./
COPY aceest ./aceest
COPY tests ./tests

CMD ["pytest"]

# ------------------------------------------------------------------ runtime --
FROM python:3.12-slim AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PATH="/opt/venv/bin:$PATH" \
    FLASK_ENV=production \
    ACEEST_DB=/data/aceest_fitness.db

# Unprivileged runtime account - the container never runs as root.
RUN groupadd --gid 10001 aceest \
    && useradd --uid 10001 --gid aceest --create-home --shell /usr/sbin/nologin aceest

COPY --from=builder /opt/venv /opt/venv

WORKDIR /app
COPY --chown=aceest:aceest app.py ./
COPY --chown=aceest:aceest aceest ./aceest

# Writable volume for the SQLite file; the application directory stays immutable.
RUN mkdir -p /data && chown aceest:aceest /data
VOLUME ["/data"]

USER aceest
EXPOSE 5000

HEALTHCHECK --interval=30s --timeout=3s --start-period=5s --retries=3 \
    CMD python -c "import urllib.request,sys; sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:5000/api/health', timeout=2).status == 200 else 1)"

CMD ["gunicorn", "--bind", "0.0.0.0:5000", "--workers", "2", "--threads", "4", \
     "--timeout", "60", "--access-logfile", "-", "app:app"]
