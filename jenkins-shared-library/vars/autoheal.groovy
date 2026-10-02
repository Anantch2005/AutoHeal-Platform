import groovy.json.JsonOutput

/**
 * AutoHeal Jenkins Shared Library
 *
 * This library contains ONLY AutoHeal integration logic.
 *
 * Generic CI/CD steps such as:
 *
 *   python_test()
 *   docker_build()
 *   docker_push()
 *   trivy_scan()
 *   sonarqube_analysis()
 *
 * remain in the separate generic Shared library.
 *
 * AutoHeal responsibilities:
 *
 *   1. Detect AutoHeal retry builds.
 *   2. Apply generic AutoHeal actions that belong to Jenkins.
 *   3. Send failed normal builds to the AutoHeal backend.
 *   4. Prevent retry builds from recursively creating incidents.
 */


def call(Map config = [:]) {

    /*
     * AutoHeal passes exactly one internal parameter:
     *
     *     AUTOHEAL_ACTION
     *
     * Empty = normal build.
     * Non-empty = AutoHeal retry build.
     */

    String action =
        (env.AUTOHEAL_ACTION ?: '').trim()


    // =========================================================
    // AUTOHEAL RETRY BUILD
    // =========================================================

    if (action) {

        /*
         * This build was triggered by AutoHeal.
         *
         * Set an internal environment flag which the
         * consuming pipeline/tests can use to avoid
         * re-triggering demo failures.
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


        applyAutoHealAction(action)

        return
    }


    // =========================================================
    // NORMAL BUILD
    // =========================================================

    /*
     * Calling autoheal() during normal successful pipeline
     * execution is intentionally a no-op.
     */

    if (
        currentBuild.currentResult != 'FAILURE'
    ) {

        echo(
            'AutoHeal: normal build; no recovery action.'
        )

        return
    }


    // =========================================================
    // NORMAL BUILD FAILURE
    // =========================================================

    /*
     * Only a normal failed build creates a new AutoHeal
     * incident.
     */

    sendFailureWebhook(config)
}


/**
 * Execute AutoHeal actions that belong to the Jenkins
 * integration itself.
 *
 * Application/tool-specific work remains in the consumer
 * pipeline. This keeps the AutoHeal library dedicated to
 * AutoHeal rather than becoming a generic CI/CD library.
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
        // WORKSPACE RECOVERY
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
        // DEPENDENCY RECOVERY
        // =====================================================

        case 'CLEAN_DEPENDENCY_ENV':

            echo(
                'AutoHeal: dependency environment '
                + 'cleanup requested.'
            )

            /*
             * The consuming application pipeline performs
             * the actual dependency environment recreation.
             */

            break


        // =====================================================
        // DOCKER RECOVERY
        // =====================================================

        case 'INVALIDATE_DOCKER_CACHE':

            echo(
                'AutoHeal: Docker cache invalidation '
                + 'requested.'
            )

            /*
             * The consuming application pipeline performs
             * the Docker --no-cache rebuild.
             */

            break


        // =====================================================
        // NETWORK RECOVERY
        // =====================================================

        case 'CONNECTIVITY_CHECK_BACKOFF':

            echo(
                'AutoHeal: checking Jenkins agent '
                + 'connectivity.'
            )


            sh '''
                set -eu

                if command -v curl >/dev/null 2>&1; then

                    echo "Checking GitHub connectivity..."

                    curl \
                        --fail \
                        --silent \
                        --show-error \
                        --max-time 10 \
                        https://github.com \
                        >/dev/null

                    echo "GitHub connectivity check passed."

                else

                    echo \
                        "curl is not available; skipping connectivity check."

                fi
            '''

            break


        // =====================================================
        // REGISTRY RECOVERY
        // =====================================================

        case 'RETRY_REGISTRY':

            echo(
                'AutoHeal: registry retry requested.'
            )

            /*
             * The consuming application pipeline performs
             * the actual authenticated registry push.
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
 * Send a normal failed Jenkins build to the AutoHeal backend.
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