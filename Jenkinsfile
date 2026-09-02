// ACEest Fitness & Gym - Jenkins BUILD pipeline.
//
// Purpose: a controlled, reproducible BUILD environment that acts as the
// secondary quality gate after GitHub Actions. Any failing stage aborts the
// build, so a red Jenkins job means the commit is not fit to promote.

pipeline {
    agent any

    options {
        timestamps()
        timeout(time: 20, unit: 'MINUTES')
        buildDiscarder(logRotator(numToKeepStr: '15'))
        disableConcurrentBuilds()
    }

    environment {
        IMAGE_NAME  = 'aceest-fitness'
        IMAGE_TAG   = "${env.BUILD_NUMBER}"
        VENV        = '.venv-ci'
        PYTHONDONTWRITEBYTECODE = '1'
        PIP_DISABLE_PIP_VERSION_CHECK = '1'
    }

    stages {

        stage('Checkout') {
            steps {
                checkout scm
                sh 'git --no-pager log -1 --pretty="Building %h - %s (%an)"'
            }
        }

        stage('Install Dependencies') {
            steps {
                sh '''
                    set -eu
                    python3 -m venv "$VENV"
                    "$VENV"/bin/pip install --upgrade pip
                    "$VENV"/bin/pip install -r requirements-dev.txt
                '''
            }
        }

        stage('Lint') {
            steps {
                sh '"$VENV"/bin/flake8 .'
            }
        }

        stage('Unit Tests') {
            steps {
                sh '"$VENV"/bin/pytest --junitxml=reports/junit.xml --cov-report=xml:reports/coverage.xml'
            }
            post {
                always {
                    junit allowEmptyResults: true, testResults: 'reports/junit.xml'
                }
            }
        }

        stage('Docker Build') {
            steps {
                sh '''
                    set -eu
                    docker build --target runtime -t "$IMAGE_NAME:$IMAGE_TAG" -t "$IMAGE_NAME:latest" .
                '''
            }
        }

        stage('Container Smoke Test') {
            steps {
                // Probes run inside the container, so this works whether the
                // Jenkins agent is the host or itself a container.
                sh '''
                    set -eu
                    CONTAINER=$(docker run -d "$IMAGE_NAME:$IMAGE_TAG")
                    trap 'docker rm -f "$CONTAINER" >/dev/null 2>&1 || true' EXIT

                    for attempt in $(seq 1 30); do
                        STATE=$(docker inspect --format '{{.State.Health.Status}}' "$CONTAINER")
                        if [ "$STATE" = "healthy" ]; then
                            echo "Container reported healthy on attempt $attempt"
                            break
                        fi
                        if [ "$attempt" -eq 30 ]; then
                            echo "Container never became healthy (last state: $STATE)"
                            docker logs "$CONTAINER"
                            exit 1
                        fi
                        sleep 2
                    done

                    echo "Verifying the calorie endpoint returns the baseline value..."
                    docker exec "$CONTAINER" python -c "
import json, urllib.request
req = urllib.request.Request(
    'http://127.0.0.1:5000/api/calories',
    data=json.dumps({'weight_kg': 80, 'program': 'MG'}).encode(),
    headers={'Content-Type': 'application/json'})
body = json.load(urllib.request.urlopen(req, timeout=5))
assert body['calories'] == 2800, body
print('calorie endpoint OK:', body)
"
                '''
            }
        }
    }

    post {
        success {
            echo "BUILD PASSED - ${env.IMAGE_NAME}:${env.IMAGE_TAG} is ready to promote."
        }
        failure {
            echo 'BUILD FAILED - quality gate blocked this commit.'
        }
        cleanup {
            sh 'docker image rm -f "$IMAGE_NAME:$IMAGE_TAG" >/dev/null 2>&1 || true'
            cleanWs()
        }
    }
}
