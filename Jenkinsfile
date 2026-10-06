// ACEest Fitness & Gym - Jenkins BUILD and DEPLOY pipeline.
//
// Purpose: a controlled, reproducible BUILD environment that acts as the
// secondary quality gate after GitHub Actions. Any failing stage aborts the
// build, so a red Jenkins job means the commit is not fit to promote.
//
// A green build is then delivered to two long-lived environments on this host:
// staging first, and production only once staging has verified itself.

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

        STAGING_NAME = 'aceest-staging'
        STAGING_PORT = '5001'
        STAGING_URL  = 'http://localhost:5001'

        PROD_NAME    = 'aceest-prod'
        PROD_PORT    = '5000'
        PROD_URL     = 'http://localhost:5000'
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

                    echo "Verifying the calorie endpoint returns the expected value..."
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

        stage('Deploy to Staging') {
            steps {
                deployAndVerify(env.STAGING_NAME, env.STAGING_PORT)
                echo "Staging is live at ${env.STAGING_URL}"
            }
        }

        stage('Promote to Production') {
            // Production only ever receives a build that staging has already
            // verified, and only from the mainline.
            when {
                expression { return !env.GIT_BRANCH || env.GIT_BRANCH.endsWith('main') }
            }
            steps {
                deployAndVerify(env.PROD_NAME, env.PROD_PORT)
                echo "Production is live at ${env.PROD_URL}"
            }
        }
    }

    post {
        success {
            echo """BUILD PASSED - ${env.IMAGE_NAME}:${env.IMAGE_TAG} deployed.
  Staging    : ${env.STAGING_URL}
  Production : ${env.PROD_URL}"""
        }
        failure {
            echo 'BUILD FAILED - quality gate blocked this commit.'
        }
        cleanup {
            // The build image is a deployed artefact now, so only dangling layers go.
            sh 'docker image prune -f >/dev/null 2>&1 || true'
            cleanWs()
        }
    }
}

// Replaces the named environment with the freshly built image, then refuses to
// return until that environment reports healthy and serves a correct result.
void deployAndVerify(String name, String port) {
    withEnv(["DEPLOY_NAME=${name}", "DEPLOY_PORT=${port}"]) {
        sh '''
            set -eu

            docker rm -f "$DEPLOY_NAME" >/dev/null 2>&1 || true
            # Free the port if an ad-hoc container is squatting on it.
            docker ps -q --filter "publish=$DEPLOY_PORT" | xargs -r docker rm -f >/dev/null 2>&1 || true

            docker run -d --name "$DEPLOY_NAME" --restart unless-stopped -p "$DEPLOY_PORT":5000 -v "${DEPLOY_NAME}-data":/data "$IMAGE_NAME:$IMAGE_TAG"

            for attempt in $(seq 1 30); do
                STATE=$(docker inspect --format '{{.State.Health.Status}}' "$DEPLOY_NAME")
                if [ "$STATE" = "healthy" ]; then
                    echo "$DEPLOY_NAME reported healthy on attempt $attempt"
                    break
                fi
                if [ "$attempt" -eq 30 ]; then
                    echo "$DEPLOY_NAME never became healthy (last state: $STATE)"
                    docker logs "$DEPLOY_NAME"
                    exit 1
                fi
                sleep 2
            done

            echo "Verifying $DEPLOY_NAME on port $DEPLOY_PORT..."
            docker exec "$DEPLOY_NAME" python -c "
import json, urllib.request
req = urllib.request.Request(
    'http://127.0.0.1:5000/api/calories',
    data=json.dumps({'weight_kg': 80, 'program': 'MG'}).encode(),
    headers={'Content-Type': 'application/json'})
body = json.load(urllib.request.urlopen(req, timeout=5))
assert body['calories'] == 2800, body
print('post-deploy verification OK:', body)
"
        '''
    }
}
