import groovy.json.JsonOutput

/**
 * AutoHeal Jenkins integration.
 *
 * Normal build:
 *   autoheal() is a no-op.
 *
 * Failed build:
 *   autoheal() in post { failure { ... } } sends the
 *   failed build to the AutoHeal backend.
 *
 * Retry build:
 *   AutoHeal supplies AUTOHEAL_ACTION as an internal
 *   Jenkins parameter. This step applies the requested
 *   Jenkins-side preparation and prevents recursive webhooks.
 *
 * AutoHeal Shared Library intentionally contains only
 * AutoHeal integration logic.
 */

def call(Map config = [:]) {

    String action = (
        env.AUTOHEAL_ACTION ?: ''
    ).trim()


    // =========================================================
    // FAILED BUILD
    // =========================================================

    if (currentBuild.currentResult == 'FAILURE') {

        /*
         * Retry builds already belong to an AutoHeal incident.
         * Do not create a second incident for the retry build.
         */
        if (action) {

            echo(
                'AutoHeal: retry build failed; '
                + 'backend will handle verification and escalation.'
            )

            return
        }


        notifyAutoHeal(config)

        return
    }


    // =========================================================
    // NORMAL BUILD
    // =========================================================

    if (!action) {

        echo(
            'AutoHeal: normal build; '
            + 'no recovery action requested.'
        )

        return
    }


    /*
     * Internal environment flag used by the consumer
     * pipeline/test logic. This is NOT a user-facing
     * AutoHeal configuration parameter.
     */
    env.AUTOHEAL_RETRY = 'true'


    // =========================================================
    // AUTOHEAL ACTIONS
    // =========================================================

    switch (action) {


        case 'RETRY':

            echo(
                'AutoHeal: controlled retry requested.'
            )

            break


        case 'CLEAN_WORKSPACE':

            echo(
                'AutoHeal: cleaning workspace '
                + 'before checkout.'
            )

            deleteDir()

            break


        case 'CLEAN_DEPENDENCY_ENV':

            echo(
                'AutoHeal: dependency environment '
                + 'recovery requested.'
            )

            /*
             * The generic python_test() shared-library step
             * performs the actual dependency environment reset.
             */

            break


        case 'INVALIDATE_DOCKER_CACHE':

            echo(
                'AutoHeal: Docker cache invalidation '
                + 'requested.'
            )

            /*
             * The generic docker_build() shared-library step
             * performs the actual no-cache rebuild.
             */

            break


        case 'CONNECTIVITY_CHECK_BACKOFF':

            echo(
                'AutoHeal: checking Jenkins agent '
                + 'connectivity before retry.'
            )

            sh '''
                set -eu

                command -v curl >/dev/null 2>&1

                curl \
                    --fail \
                    --silent \
                    --show-error \
                    --max-time 10 \
                    https://github.com \
                    >/dev/null

                curl \
                    --fail \
                    --silent \
                    --show-error \
                    --max-time 10 \
                    https://registry-1.docker.io/v2/ \
                    >/dev/null || true
            '''

            break


        case 'RETRY_REGISTRY':

            echo(
                'AutoHeal: registry retry requested.'
            )

            /*
             * The existing docker_push() step performs
             * the retry using the configured Jenkins credentials.
             */

            break


        default:

            error(
                "AutoHeal: unsupported action '${action}'."
            )
    }
}


/**
 * Send a failed normal build to AutoHeal.
 */
private void notifyAutoHeal(
    Map config = [:]
) {

    String baseUrl = (
        config.url
        ?: env.AUTOHEAL_URL
        ?: 'http://127.0.0.1:8000'
    ).replaceAll('/+$', '')


    String credentialId = (
        config.secretCredentialId
        ?: 'autoheal-webhook-secret'
    )


    String payload = JsonOutput.toJson([
        job_name     : env.JOB_NAME,
        build_number : (env.BUILD_NUMBER ?: '0') as Integer,
        build_url    : env.BUILD_URL ?: '',
        status       : 'FAILURE'
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

            sh '''
                set -eu

                response_file="/tmp/autoheal-response.json"

                rm -f "$response_file"


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
                    "$AUTOHEAL_WEBHOOK_URL")


                case "$status_code" in

                    200|202)

                        echo \
                            "AutoHeal webhook accepted (HTTP ${status_code})."

                        ;;


                    *)

                        echo \
                            "AutoHeal webhook failed with HTTP ${status_code}."

                        cat "$response_file" || true

                        exit 1

                        ;;

                esac


                rm -f "$response_file"
            '''
        }
    }
}