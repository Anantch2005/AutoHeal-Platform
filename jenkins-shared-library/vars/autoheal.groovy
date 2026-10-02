import groovy.json.JsonOutput

/**
 * AutoHeal Jenkins Shared Library
 *
 * This library contains ONLY AutoHeal integration logic.
 *
 * It does not provide generic CI/CD helpers such as:
 * python_test()
 * docker_build()
 * docker_push()
 * trivy_scan()
 * sonarqube_analysis()
 *
 * Those remain in the separate generic "Shared" library.
 *
 * Responsibilities:
 *
 * 1. Send failed normal builds to AutoHeal.
 * 2. Detect AutoHeal retry builds.
 * 3. Expose AUTOHEAL_ACTION to the consumer pipeline.
 * 4. Perform only generic agent-level actions that are safe
 *    and independent of application tooling.
 */

def call(Map config = [:]) {

    String action =
        (env.AUTOHEAL_ACTION ?: '').trim()


    /*
     * =====================================================
     * RETRY BUILD
     * =====================================================
     *
     * AutoHeal triggered this Jenkins build.
     *
     * Do not send another failure webhook.
     */

    if (action) {

        env.AUTOHEAL_RETRY = 'true'

        echo """
========================================
          AutoHeal Retry
========================================
 Action : ${action}
========================================
"""

        applyAction(action)

        return
    }


    /*
     * =====================================================
     * NORMAL BUILD
     * =====================================================
     */

    if (
        currentBuild.currentResult != 'FAILURE'
    ) {

        echo(
            'AutoHeal: normal build; no action required.'
        )

        return
    }


    /*
     * =====================================================
     * FAILED NORMAL BUILD
     * =====================================================
     *
     * Send the build event to AutoHeal backend.
     */

    sendFailureWebhook(config)
}


/**
 * Apply the generic part of the AutoHeal action.
 *
 * Application/tool-specific actions remain inside the
 * consumer test pipeline.
 */
private void applyAction(
    String action
) {

    switch (action) {

        case 'RETRY':

            echo(
                'AutoHeal: controlled retry requested.'
            )

            break


        case 'CLEAN_WORKSPACE':

            echo(
                'AutoHeal: cleaning Jenkins workspace.'
            )

            deleteDir()

            break


        case 'CLEAN_DEPENDENCY_ENV':

            echo(
                'AutoHeal: dependency environment '
                + 'reset requested.'
            )

            /*
             * The Calculator demo pipeline performs
             * the actual environment recreation.
             */

            break


        case 'INVALIDATE_DOCKER_CACHE':

            echo(
                'AutoHeal: Docker cache invalidation '
                + 'requested.'
            )

            /*
             * The Calculator demo pipeline performs
             * the actual --no-cache build.
             */

            break


        case 'CONNECTIVITY_CHECK_BACKOFF':

            echo(
                'AutoHeal: checking network connectivity.'
            )

            sh '''
                set -eu

                if command -v curl >/dev/null 2>&1; then

                    curl \
                        --fail \
                        --silent \
                        --show-error \
                        --max-time 10 \
                        https://github.com \
                        >/dev/null

                else

                    echo \
                        "curl not available; skipping connectivity check."

                fi
            '''

            break


        case 'RETRY_REGISTRY':

            echo(
                'AutoHeal: registry retry requested.'
            )

            /*
             * Registry authentication/push remains the
             * responsibility of the consumer pipeline.
             */

            break


        default:

            error(
                "AutoHeal: unsupported action '${action}'."
            )
    }
}


/**
 * Send failed build event to AutoHeal backend.
 */
private void sendFailureWebhook(
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
        build_number : (
            env.BUILD_NUMBER ?: '0'
        ) as Integer,
        build_url    : env.BUILD_URL ?: '',
        status       : 'FAILURE'
    ])


    echo """
========================================
        AutoHeal Failure Event
========================================
 Job   : ${env.JOB_NAME}
 Build : ${env.BUILD_NUMBER}
========================================
"""


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
                            "AutoHeal webhook failed (HTTP ${status_code})."

                        cat "$response_file" || true

                        exit 1

                        ;;

                esac


                rm -f "$response_file"
            '''
        }
    }
}