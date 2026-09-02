# ACEest Fitness & Gym — DevOps Assignment 1

A containerised Flask service for **ACEest Fitness & Gym** with a complete CI/CD
toolchain: Git/GitHub for version control, Pytest for validation, Docker for
packaging, **Jenkins** for the controlled BUILD gate and **GitHub Actions** for
continuous integration on every push and pull request.

> **Origin of the business logic.** The baseline scripts supplied with the
> assignment (`Aceestver-*.py`) are Tkinter desktop applications, not web
> services. Their *domain rules* — the per-program calorie factor, the BMI bands,
> the weekly adherence tracking, the client/workout schema — were ported into
> stateless HTTP endpoints. The rules are preserved verbatim; only the delivery
> mechanism changed.

---

## Table of contents

1. [Features](#features)
2. [Domain rules ported from the baseline](#domain-rules-ported-from-the-baseline)
3. [Project layout](#project-layout)
4. [Local setup and execution](#local-setup-and-execution)
5. [Running the tests manually](#running-the-tests-manually)
6. [API reference](#api-reference)
7. [Docker](#docker)
8. [Jenkins BUILD gate](#jenkins-build-gate)
9. [GitHub Actions CI/CD](#github-actions-cicd)
10. [How Jenkins and GitHub Actions fit together](#how-jenkins-and-github-actions-fit-together)
11. [Branching and commit conventions](#branching-and-commit-conventions)

---

## Features

- **Client management** — enroll, read, update and delete gym clients with
  server-side validation on every field.
- **Program catalogue** — the four training programs from the baseline, each with
  its calorie factor, weekly workout chart and nutrition plan.
- **Calorie targeting** — `daily kcal = body weight (kg) × program factor`.
- **BMI and risk classification** — Underweight / Normal / Overweight / Obese.
- **Weekly adherence tracking** — per-week percentages plus a derived summary
  (average, best week, trend, coaching status).
- **Workout logging** — typed, duration-validated training sessions per client.
- **Two interfaces over one domain layer** — a JSON REST API under `/api` and a
  server-rendered dashboard at `/`.

## Domain rules ported from the baseline

| Rule | Formula / values | Baseline source |
| --- | --- | --- |
| Daily calorie target | `int(weight_kg × factor)` | `Aceestver-1.1.py`, `Aceestver-2.2.1.py` |
| Program factors | FL3 = 22, FL5 = 24, MG = 35, BG = 26 kcal/kg | `Aceestver-2.2.4.py` |
| BMI | `weight_kg ÷ (height_m)²`, rounded to 1 dp | `Aceestver-2.2.4.py` |
| BMI bands | `< 18.5` Underweight, `< 25` Normal, `< 30` Overweight, else Obese | `Aceestver-2.2.4.py` |
| Adherence | integer percentage `0–100`, one record per week | `Aceestver-2.1.2.py` |
| Workout types | Strength, Hypertrophy, Cardio, Mobility | `Aceestver-3.2.4.py` |
| Site metrics | 150 user capacity, 10 000 sq ft, 250 break-even members | `Aceestver-1.0.py` |

## Project layout

```
aceest-fitness-devops/
├── app.py                       # WSGI entrypoint (gunicorn "app:app")
├── aceest/
│   ├── __init__.py              # application factory + error handlers
│   ├── config.py                # environment-driven configuration objects
│   ├── db.py                    # SQLite persistence (parameterised SQL only)
│   ├── errors.py                # domain exceptions -> HTTP status codes
│   ├── programs.py              # training program catalogue
│   ├── services.py              # pure business logic + validation
│   ├── routes/
│   │   ├── api.py               # JSON REST blueprint  (/api)
│   │   └── web.py               # server-rendered dashboard blueprint
│   ├── templates/               # Jinja2 templates
│   └── static/css/style.css
├── tests/
│   ├── conftest.py              # fixtures: isolated app, client, sample data
│   ├── test_services.py         # unit tests for the domain logic
│   ├── test_api.py              # endpoint tests for the REST API
│   └── test_web.py              # dashboard + app-factory tests
├── Dockerfile                   # multi-stage: builder / test / runtime
├── .dockerignore
├── Jenkinsfile                  # declarative BUILD pipeline
├── .github/workflows/main.yml   # GitHub Actions CI/CD
├── requirements.txt             # runtime dependencies
├── requirements-dev.txt         # runtime + pytest + flake8
├── pytest.ini                   # test + coverage configuration
└── .flake8
```

The application is deliberately **modular**: `services.py` contains no Flask or
SQLite imports, so the business rules are unit-testable in isolation, and the
blueprints stay thin.

## Local setup and execution

Requires Python 3.11 or newer.

```bash
git clone https://github.com/<your-username>/aceest-fitness-devops.git
cd aceest-fitness-devops

python3 -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
pip install -r requirements-dev.txt

# Development server (auto-reload, debug pages)
FLASK_ENV=development python app.py
```

The dashboard is served at <http://127.0.0.1:5000/> and the API at
<http://127.0.0.1:5000/api/health>.

To run it the way the container does:

```bash
gunicorn "app:app" --bind 127.0.0.1:5000 --workers 2
```

### Configuration

| Variable | Default | Purpose |
| --- | --- | --- |
| `FLASK_ENV` | `production` | Selects `development` / `testing` / `production` config. |
| `ACEEST_DB` | `/tmp/aceest_fitness.db` (`/data/...` in Docker) | SQLite file path. |
| `SECRET_KEY` | random per process | Flask session/flash signing key. Set it explicitly in production. |
| `HOST` / `PORT` | `127.0.0.1` / `5000` | Bind address for `python app.py`. |

No secret is ever hard-coded: when `SECRET_KEY` is unset a random key is
generated at start-up.

## Running the tests manually

```bash
source .venv/bin/activate

pytest                    # full suite + coverage gate (fails under 90%)
pytest -v                 # verbose, one line per test
pytest tests/test_api.py  # a single module
pytest -k calorie         # a single topic
flake8 .                  # lint gate
```

`pytest.ini` enables `pytest-cov` with `--cov-fail-under=90`, so a drop in
coverage fails the build exactly like a failing assertion.

Inside a container, exactly as CI does it:

```bash
docker build --target test -t aceest-fitness:test .
docker run --rm aceest-fitness:test pytest
```

### What the suite covers

| Layer | File | Focus |
| --- | --- | --- |
| Domain | `tests/test_services.py` | Calorie formula per program, BMI boundaries, validators, adherence trends and status bands, profile derivation. |
| API | `tests/test_api.py` | Every route, happy paths, 400/404/409 responses, duplicate handling, week ordering, aggregation, SQL-injection and HTML-injection attempts. |
| Web | `tests/test_web.py` | Dashboard rendering, form submission and redirects, flash messaging, static assets, app-factory isolation. |

## API reference

| Method | Path | Description |
| --- | --- | --- |
| `GET` | `/api/health` | Liveness probe used by Docker, Jenkins and CI. |
| `GET` | `/api/programs` | List the training program catalogue. |
| `GET` | `/api/programs/<code>` | One program (`FL3`, `FL5`, `MG`, `BG`). |
| `POST` | `/api/calories` | `{"weight_kg", "program"}` → daily calorie target. |
| `POST` | `/api/bmi` | `{"weight_kg", "height_cm"}` → BMI, category, risk note. |
| `GET` | `/api/clients` | Client roster. |
| `POST` | `/api/clients` | Enroll a client (201, or 409 if the name exists). |
| `GET` | `/api/clients/<name>` | Full profile with progress and workouts. |
| `PUT` | `/api/clients/<name>` | Replace a profile; calories and BMI are recomputed. |
| `DELETE` | `/api/clients/<name>` | Remove a client and cascade their records. |
| `GET` | `/api/clients/<name>/progress` | Weekly adherence plus derived summary. |
| `POST` | `/api/clients/<name>/progress` | Log or overwrite one week. |
| `GET` | `/api/clients/<name>/workouts` | Session history and total minutes. |
| `POST` | `/api/clients/<name>/workouts` | Log a session. |
| `GET` | `/api/stats` | Gym-wide aggregates and capacity utilisation. |

Example:

```bash
curl -X POST http://127.0.0.1:5000/api/clients \
  -H 'Content-Type: application/json' \
  -d '{"name":"Ravi Kumar","age":32,"height_cm":175,"weight_kg":80,"program":"MG"}'
```

```json
{
  "name": "Ravi Kumar",
  "program": "MG",
  "program_name": "Muscle Gain (MG) - PPL",
  "calories": 2800,
  "bmi": 26.1
}
```

Errors are always JSON and carry the offending field:

```json
{ "error": "ValidationError", "message": "'weight_kg' must be a number", "field": "weight_kg" }
```

## Docker

The image is **multi-stage** with three targets:

| Target | Purpose |
| --- | --- |
| `builder` | Installs runtime dependencies into `/opt/venv`. No compiler or pip cache reaches the final image. |
| `test` | `builder` + dev dependencies + the test suite. Used by CI to run Pytest against the exact dependency set the runtime ships. |
| `runtime` | Default target. `python:3.12-slim`, no build tools, non-root user, health check, gunicorn. |

Efficiency and security choices:

- `requirements.txt` is copied **before** the source, so the dependency layer is
  cached and only re-built when dependencies actually change.
- The runtime stage copies just `app.py` and the `aceest/` package — no tests,
  no `.git`, no virtualenv (see `.dockerignore`).
- The process runs as the unprivileged `aceest` user (UID 10001), never root.
  CI asserts this.
- SQLite lives on the `/data` volume, keeping the application directory
  immutable.
- A `HEALTHCHECK` polls `/api/health` so orchestrators can detect a sick
  container.

```bash
# Build and run
docker build -t aceest-fitness:latest .
docker run -d --name aceest -p 5000:5000 -v aceest-data:/data aceest-fitness:latest

curl http://127.0.0.1:5000/api/health
docker logs -f aceest
docker rm -f aceest
```

## Jenkins BUILD gate

`Jenkinsfile` is a declarative pipeline with five stages, each an abort point:

| Stage | Action |
| --- | --- |
| Checkout | Pulls the latest commit from GitHub via the job's SCM configuration. |
| Install Dependencies | Creates a clean virtualenv and installs `requirements-dev.txt`. |
| Lint | `flake8 .` — style and syntax gate. |
| Unit Tests | `pytest` with JUnit XML and coverage reports published to the build. |
| Docker Build | Builds the `runtime` image tagged with the Jenkins build number. |
| Container Smoke Test | Starts the image and polls `/api/health` before passing. |

### Setting up the job

```bash
docker run -d --name jenkins -p 8080:8080 -p 50000:50000 \
  -v jenkins_home:/var/jenkins_home \
  -v /var/run/docker.sock:/var/run/docker.sock \
  jenkins/jenkins:lts

docker exec jenkins cat /var/jenkins_home/secrets/initialAdminPassword
```

1. Open <http://localhost:8080>, unlock with the password above and install the
   suggested plugins (Git and Pipeline are required).
2. **New Item → Pipeline**, name it `aceest-fitness-build`.
3. Under **Pipeline**, choose *Pipeline script from SCM* → *Git*, enter the
   repository URL, set the branch to `*/main` and the script path to
   `Jenkinsfile`.
4. Optionally tick **GitHub hook trigger for GITScm polling** (or *Poll SCM*
   `H/5 * * * *` if the server is not reachable from GitHub).
5. **Build Now** — the console output shows every stage; a green run means the
   commit passed the BUILD gate.

The agent needs `python3`, `docker` and `curl` on its `PATH`. Mounting the Docker
socket (as above) lets the containerised controller build images.

## GitHub Actions CI/CD

`.github/workflows/main.yml` runs on **every push** and **every pull request to
`main`**, in three dependent jobs:

```
build-and-lint  ──►  docker-build  ──►  containerized-tests
```

| Job | Steps |
| --- | --- |
| **Build & Lint** | Set up Python 3.12 with pip caching → install dev dependencies → `compileall` (syntax gate) → `flake8` → `pytest` on the host → upload JUnit/coverage artefacts. |
| **Docker Image Assembly** | Build the `runtime` target with Buildx and GitHub Actions layer caching → assert the image runs as `aceest`, not root → export the image as an artefact. |
| **Automated Testing** | Build the `test` target → run `pytest` **inside** the container → load the runtime image → start it, poll `/api/health`, and assert the live calorie endpoint returns 2800 kcal for 80 kg on the MG program. |

Failure at any step marks the commit red and blocks the pull request.

## How Jenkins and GitHub Actions fit together

They deliberately overlap, and that redundancy is the point.

**GitHub Actions is the fast, broad feedback loop.** It is hosted, it triggers on
every push and pull request across all branches, and it runs on a clean
`ubuntu-latest` runner. Its job is to tell a developer *within minutes* that a
change lints, tests, containerises and actually serves traffic. Because it is
attached to pull requests, it is what protects `main` from bad merges.

**Jenkins is the controlled, authoritative BUILD environment.** It runs on
infrastructure the organisation owns, with pinned tool versions, real Docker
access and archived artefacts and reports. Its job is to prove the code builds in
*the* build environment — not just on somebody's laptop and not just on an
ephemeral cloud runner. This is the environment a release would actually be cut
from, and it is where build history, JUnit trends and coverage trends live.

The practical division of labour:

| Concern | GitHub Actions | Jenkins |
| --- | --- | --- |
| Trigger | Every push and PR | Latest `main` (webhook or poll) |
| Speed | Minutes, per-commit | Slower, per-integration |
| Environment | Ephemeral, cloud-hosted | Persistent, organisation-controlled |
| Primary role | Continuous Integration gate | BUILD gate and artefact source |
| Blocks what | The pull request merge | The promotion of a build |

A change therefore has to survive two independent verdicts — a hosted CI run and
a controlled BUILD — before it is considered releasable. If the two ever
disagree, the disagreement itself is the signal: the code depends on something
about its environment that has not been captured in the `Dockerfile`.

## Branching and commit conventions

Feature branches merge into `main` through pull requests, so CI has to pass
before any change lands:

| Branch | Scope |
| --- | --- |
| `main` | Protected, always green, always deployable |
| `feature/flask-app` | Application and domain layer |
| `feature/pytest-suite` | Test suite |
| `feature/docker` | Containerisation |
| `feature/cicd-pipeline` | Jenkinsfile and GitHub Actions |
| `docs/readme` | Documentation |

Commits follow [Conventional Commits](https://www.conventionalcommits.org/):

```
feat:  add Flask client management endpoints
test:  add pytest coverage for the calorie formula
build: add multi-stage Dockerfile with non-root runtime
ci:    add GitHub Actions build, docker and test jobs
docs:  document Jenkins and GitHub Actions integration
fix:   report target_adherence as the failing field
```
