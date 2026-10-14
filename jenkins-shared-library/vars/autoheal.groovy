import groovy.json.JsonOutput

/**
 * AutoHeal Jenkins Shared Library.
 *
 * All recovery commands run on the Jenkins agent, not in the
 * Python backend. Actions are allowlisted; arbitrary shell commands
 * supplied by an AI model are never executed.
 *
 * Consumer integration:
 *   autoheal(stage: 'checkout')
 *   autoheal(stage: 'test')
 *   autoheal(stage: 'docker')
 *   autoheal(stage: 'registry')
 *
 * A normal failed build is reported from post { failure { ... } }.
 */

def call(Map config = [:]) {
    String action = (env.AUTOHEAL_ACTION ?: '').trim()
    String stageName = (config.stage ?: '').toString().trim().toLowerCase()

    if (!action || action == 'NONE') {
        if (currentBuild.currentResult == 'FAILURE') {
            try {
                sendFailureWebhook(config)
            } catch (Exception ex) {
                echo "AutoHeal webhook error (not masking original failure): ${ex.message}"
            }
        } else {
            echo 'AutoHeal: normal build; no recovery action.'
        }
        return
    }

    env.AUTOHEAL_RETRY = 'true'

    echo """
========================================
          AutoHeal Recovery
========================================
Action : ${action}
Build  : ${env.BUILD_NUMBER}
Stage  : ${stageName ?: 'unspecified'}
========================================
"""

    String requiredStage = requiredStageFor(action)
    if (requiredStage == 'unsupported') {
        error("AutoHeal: unsupported action '${action}'. Refusing to execute it.")
    }

    if (stageName != requiredStage) {
        echo "AutoHeal: action '${action}' waits for stage '${requiredStage}'."
        return
    }

    if ((env.AUTOHEAL_ACTION_APPLIED ?: '') == 'true') {
        echo 'AutoHeal: recovery already applied in this build; skipping duplicate hook.'
        return
    }

    applyAutoHealAction(action)
    env.AUTOHEAL_ACTION_APPLIED = 'true'
}

private String requiredStageFor(String action) {
    switch (action) {
        case 'CLEAN_WORKSPACE':
            return 'checkout'
        case 'CLEAN_DEPENDENCY_ENV':
            return 'test'
        case 'INVALIDATE_DOCKER_CACHE':
            return 'docker'
        case 'RETRY_REGISTRY':
            return 'registry'
        case 'CONNECTIVITY_CHECK_BACKOFF':
        case 'CONNECTIVITY_CHECK_BACKOFF_AND_RETRY':
            return 'test'
        case 'RETRY':
        case 'RETRY_FLAKY_TEST':
            return 'checkout'
        default:
            return 'unsupported'
    }
}

private void applyAutoHealAction(String action) {
    switch (action) {
        case 'RETRY':
        case 'RETRY_FLAKY_TEST':
        case 'RETRY_REGISTRY':
            echo "AutoHeal: controlled retry requested (${action})."
            break

        case 'CLEAN_WORKSPACE':
            echo 'AutoHeal: removing the current workspace before checkout.'
            deleteDir()
            break

        case 'CLEAN_DEPENDENCY_ENV':
            remediateDependencies()
            break

        case 'INVALIDATE_DOCKER_CACHE':
            remediateDockerCache()
            break

        case 'CONNECTIVITY_CHECK_BACKOFF':
        case 'CONNECTIVITY_CHECK_BACKOFF_AND_RETRY':
            remediateNetworkTransient()
            break

        default:
            error("AutoHeal: action '${action}' is not allowlisted.")
    }
}

/**
 * Rebuild the dependency environment from existing project definitions.
 * Never upgrades package versions or edits lockfiles.
 */
private void remediateDependencies() {
    echo 'AutoHeal: detecting a supported dependency manifest.'

    sh(
        label: 'AutoHeal dependency recovery',
        script: '''
            set -eu

            if [ -f requirements.txt ]; then
                command -v python >/dev/null 2>&1 || {
                    echo "Python is unavailable for requirements.txt recovery" >&2
                    exit 20
                }

                rm -rf .venv
                python -m venv .venv
                .venv/bin/python -m pip install \
                    --disable-pip-version-check \
                    -r requirements.txt

                .venv/bin/python -c \
                    "import sys; print('AutoHeal Python environment ready:', sys.version)"

            elif [ -f package.json ] && [ -f package-lock.json ]; then
                command -v npm >/dev/null 2>&1 || {
                    echo "npm is unavailable" >&2
                    exit 21
                }

                rm -rf node_modules
                npm ci --no-audit --no-fund

            elif [ -f package.json ] && [ -f yarn.lock ]; then
                command -v yarn >/dev/null 2>&1 || {
                    echo "yarn is unavailable" >&2
                    exit 22
                }

                rm -rf node_modules
                yarn install --frozen-lockfile

            elif [ -f package.json ] && [ -f pnpm-lock.yaml ]; then
                command -v pnpm >/dev/null 2>&1 || {
                    echo "pnpm is unavailable" >&2
                    exit 23
                }

                rm -rf node_modules
                pnpm install --frozen-lockfile

            else
                echo "No supported dependency manifest found; refusing unsafe recovery." >&2
                exit 24
            fi
        '''
    )

    if (fileExists('requirements.txt')) {
        env.PATH = "${pwd()}/.venv/bin:${env.PATH}"
    }

    echo 'AutoHeal: dependency installation completed. The pipeline must verify it.'
}

/**
 * Remove only old Docker builder cache.
 * This is NOT a Docker daemon restart.
 */
private void remediateDockerCache() {
    sh(
        label: 'AutoHeal Docker builder-cache cleanup',
        script: '''
            set -eu

            command -v docker >/dev/null 2>&1 || {
                echo "Docker CLI unavailable" >&2
                exit 30
            }

            docker info >/dev/null 2>&1 || {
                echo "Docker daemon unavailable; cache cleanup cannot repair it" >&2
                exit 31
            }

            docker builder prune --force --filter 'until=24h'
        '''
    )

    echo 'AutoHeal: eligible Docker builder cache removed.'
}

/**
 * Bounded connectivity checks. This does not change DNS settings,
 * bypass authentication, or switch registries.
 */
private void remediateNetworkTransient() {
    sh(
        label: 'AutoHeal network backoff',
        script: '''
            set -eu

            command -v curl >/dev/null 2>&1 || {
                echo "curl is unavailable for connectivity verification" >&2
                exit 40
            }

            for delay in 2 4 8; do
                echo "AutoHeal: waiting ${delay}s before connectivity check"
                sleep "$delay"

                if curl \
                    --fail \
                    --silent \
                    --show-error \
                    --max-time 10 \
                    https://github.com >/dev/null; then
                    echo "AutoHeal: outbound HTTPS connectivity is available"
                    exit 0
                fi
            done

            echo "AutoHeal: connectivity check failed after bounded backoff" >&2
            exit 41
        '''
    )
}

/**
 * Notify the AutoHeal backend about a normal failed build.
 * Webhook errors must not overwrite the original pipeline failure.
 */
private void sendFailureWebhook(Map config = [:]) {
    String baseUrl = (
        config.url ?: env.AUTOHEAL_URL ?: 'http://127.0.0.1:8000'
    ).replaceAll('/+$', '')

    String credentialId = (
        config.secretCredentialId ?: 'autoheal-webhook-secret'
    )

    String buildNumber = (env.BUILD_NUMBER ?: '0').toString()
    if (!(buildNumber ==~ /\\d+/)) {
        error('AutoHeal: invalid Jenkins build number.')
    }

    String payload = JsonOutput.toJson([
        job_name: env.JOB_NAME ?: '',
        build_number: buildNumber as Integer,
        build_url: env.BUILD_URL ?: '',
        status: 'FAILURE'
    ])

    withCredentials([
        string(
            credentialsId: credentialId,
            variable: 'AUTOHEAL_WEBHOOK_SECRET'
        )
    ]) {
        withEnv([
            "AUTOHEAL_PAYLOAD=${payload}",
            "AUTOHEAL_WEBHOOK_URL=${baseUrl}/webhook/jenkins"
        ]) {
            sh(
                label: 'Notify AutoHeal',
                script: '''
                    set -eu

                    response_file="$(mktemp)"
                    trap 'rm -f "$response_file"' EXIT

                    status_code=$(curl \
                        --silent \
                        --show-error \
                        --output "$response_file" \
                        --write-out '%{http_code}' \
                        --connect-timeout 5 \
                        --max-time 15 \
                        --request POST \
                        --header 'Content-Type: application/json' \
                        --header "X-AutoHeal-Secret: ${AUTOHEAL_WEBHOOK_SECRET}" \
                        --data "$AUTOHEAL_PAYLOAD" \
                        "$AUTOHEAL_WEBHOOK_URL" || true)

                    case "$status_code" in
                        200|202)
                            echo "AutoHeal webhook accepted."
                            ;;
                        *)
                            echo "AutoHeal webhook failed with HTTP status: ${status_code}"
                            if [ -s "$response_file" ]; then
                                cat "$response_file"
                            fi
                            # Do not fail this notification step: preserve the original build result.
                            ;;
                    esac
                '''
            )
        }
    }
}