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
                sh '''
                    set -eu
                    CONTAINER=$(docker run -d -p 0:5000 "$IMAGE_NAME:$IMAGE_TAG")
                    trap 'docker rm -f "$CONTAINER" >/dev/null 2>&1 || true' EXIT
                    PORT=$(docker port "$CONTAINER" 5000/tcp | head -1 | cut -d: -f2)

                    for attempt in $(seq 1 20); do
                        if curl -fsS "http://127.0.0.1:$PORT/api/health" >/dev/null; then
                            echo "Health check passed on attempt $attempt"
                            exit 0
                        fi
                        sleep 2
                    done

                    echo "Container failed health check"
                    docker logs "$CONTAINER"
                    exit 1
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
