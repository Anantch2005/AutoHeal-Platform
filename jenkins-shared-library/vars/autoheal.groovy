import groovy.json.JsonOutput

/**
 * AutoHeal Jenkins Shared Library
 *
 * This library contains ONLY AutoHeal integration logic.
 *
 * Generic CI/CD functions remain in the separate Shared library.
 *
 * Responsibilities:
 *
 *   1. Detect AutoHeal retry builds.
 *   2. Apply AutoHeal-specific Jenkins actions.
 *   3. Send failed normal builds to AutoHeal backend.
 *   4. Prevent recursive webhook creation during retries.
 */


def call(Map config = [:]) {

    String action =
        (env.AUTOHEAL_ACTION ?: '').trim()


    /*
     * =========================================================
     * NORMAL BUILD
     * =========================================================
     *
     * "NONE" is treated exactly like an empty action.
     *
     * This is important because Jenkins may retain a previous
     * parameter value or the demo job may explicitly use NONE.
     */

    if (
        !action ||
        action == 'NONE'
    ) {

        /*
         * If the current build is already failing, this is a
         * normal failed build and must be reported to AutoHeal.
         */

        if (
            currentBuild.currentResult == 'FAILURE'
        ) {

            sendFailureWebhook(config)

            return
        }


        echo(
            'AutoHeal: normal build; no recovery action.'
        )

        return
    }


    /*
     * =========================================================
     * AUTOHEAL RETRY BUILD
     * =========================================================
     *
     * Any real AutoHeal action means this build was triggered
     * by the AutoHeal backend.
     */

    env.AUTOHEAL_RETRY = 'true'


    echo """
========================================
          AutoHeal Retry Build
========================================
 Action : ${action}
 Build  : ${env.BUILD_NUMBER}
========================================
"""


    applyAutoHealAction(
        action
    )
}


/**
 * Execute the Jenkins-side portion of an AutoHeal action.
 *
 * Generic CI/CD functionality remains in the consumer pipeline
 * and in the separate universal Shared library.
 */
private void applyAutoHealAction(
    String action
) {

    switch (action) {


        // =====================================================
        // GENERIC RETRY
        // =====================================================

        case 'RETRY':

            echo(
                'AutoHeal: controlled retry requested.'
            )

            break


        // =====================================================
        // FLAKY TEST
        // =====================================================

        case 'RETRY_FLAKY_TEST':

            echo(
                'AutoHeal: flaky test retry requested.'
            )

            /*
             * No destructive Jenkins-side operation is required.
             * The pipeline simply reruns the normal test stages.
             */

            break


        // =====================================================
        // WORKSPACE
        // =====================================================

        case 'CLEAN_WORKSPACE':

            echo(
                'AutoHeal: cleaning Jenkins workspace.'
            )

            deleteDir()

            echo(
                'AutoHeal: workspace cleanup completed.'
            )

            break


        // =====================================================
        // DEPENDENCY
        // =====================================================

        case 'CLEAN_DEPENDENCY_ENV':

            echo(
                'AutoHeal: dependency environment cleanup requested.'
            )

            /*
             * The Calculator demo pipeline performs the actual
             * Python environment recreation.
             */

            break


        // =====================================================
        // DOCKER
        // =====================================================

        case 'INVALIDATE_DOCKER_CACHE':

            echo(
                'AutoHeal: Docker cache invalidation requested.'
            )

            /*
             * The Calculator demo pipeline performs the actual
             * docker build --no-cache operation.
             */

            break


        // =====================================================
        // NETWORK
        // =====================================================

        case 'CONNECTIVITY_CHECK_BACKOFF':

            echo(
                'AutoHeal: checking Jenkins agent connectivity.'
            )


            sh '''
                set -eu

                echo "Checking GitHub connectivity..."

                if command -v curl >/dev/null 2>&1; then

                    curl \
                        --fail \
                        --silent \
                        --show-error \
                        --max-time 10 \
                        https://github.com \
                        >/dev/null

                    echo "Connectivity check passed."

                else

                    echo "curl is not available."
                    echo "Skipping connectivity check."

                fi
            '''

            break


        // =====================================================
        // COMBINED NETWORK ACTION
        // =====================================================

        case 'CONNECTIVITY_CHECK_BACKOFF_AND_RETRY':

            echo(
                'AutoHeal: network recovery requested.'
            )


            /*
             * The backend normally converts this into the
             * single Jenkins parameter:
             *
             *     CONNECTIVITY_CHECK_BACKOFF
             *
             * This case is kept for compatibility with an
             * older/manual invocation.
             */

            sh '''
                set -eu

                echo "Checking GitHub connectivity..."

                if command -v curl >/dev/null 2>&1; then

                    curl \
                        --fail \
                        --silent \
                        --show-error \
                        --max-time 10 \
                        https://github.com \
                        >/dev/null

                    echo "Connectivity check passed."

                else

                    echo "curl is not available."
                    echo "Skipping connectivity check."

                fi
            '''

            break


        // =====================================================
        // REGISTRY
        // =====================================================

        case 'RETRY_REGISTRY':

            echo(
                'AutoHeal: registry retry requested.'
            )

            /*
             * Actual authenticated docker push remains in the
             * consumer pipeline.
             */

            break


        // =====================================================
        // UNKNOWN ACTION
        // =====================================================

        default:

            error(
                "AutoHeal: unsupported action '${action}'."
            )
    }
}


/**
 * Send a normal failed Jenkins build to AutoHeal.
 */
private void sendFailureWebhook(
    Map config = [:]
) {

    String baseUrl = (

        config.url

        ?: env.AUTOHEAL_URL

        ?: 'http://127.0.0.1:8000'

    ).replaceAll(
        '/+$',
        ''
    )


    String credentialId = (

        config.secretCredentialId

        ?: 'autoheal-webhook-secret'
    )


    String payload = JsonOutput.toJson([

        job_name:
            env.JOB_NAME,

        build_number:
            (
                env.BUILD_NUMBER ?: '0'
            ) as Integer,

        build_url:
            env.BUILD_URL ?: '',

        status:
            'FAILURE'
    ])


    echo """
========================================
      AutoHeal Failure Notification
========================================
 Job   : ${env.JOB_NAME}
 Build : ${env.BUILD_NUMBER}
========================================
"""


    withCredentials([

        string(

            credentialsId:
                credentialId,

            variable:
                'AUTOHEAL_WEBHOOK_SECRET'
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


                echo \
                    "AutoHeal HTTP status: ${status_code}"


                case "$status_code" in

                    200|202)

                        echo \
                            "AutoHeal webhook accepted."

                        ;;

                    *)

                        echo \
                            "AutoHeal webhook failed."

                        if [ -f "$response_file" ]; then
                            cat "$response_file"
                        fi

                        exit 1

                        ;;

                esac


                rm -f "$response_file"
            '''
        }
    }
}