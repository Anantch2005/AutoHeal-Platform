def call(Map config = [:]) {

    String action = (env.AUTOHEAL_ACTION ?: '').trim()

    if (currentBuild.currentResult == 'FAILURE') {

        if (action) {
            echo "AutoHeal retry build detected."
            return
        }

        notifyAutoHeal(config)
        return
    }

    if (!action) {
        echo "AutoHeal: normal build."
        return
    }

    env.AUTOHEAL_RETRY = 'true'

    switch (action) {

        case 'RETRY':
            echo 'AutoHeal: retry requested.'
            break

        case 'CLEAN_WORKSPACE':
            echo 'AutoHeal: cleaning workspace.'
            deleteDir()
            break

        case 'CLEAN_DEPENDENCY_ENV':
            echo 'AutoHeal: dependency recovery requested.'
            break

        case 'INVALIDATE_DOCKER_CACHE':
            echo 'AutoHeal: Docker cache recovery requested.'
            break

        case 'CONNECTIVITY_CHECK_BACKOFF':
            echo 'AutoHeal: network recovery requested.'
            sh '''
                set -eu
                getent hosts github.com
                getent hosts registry-1.docker.io
            '''
            break

        case 'RETRY_REGISTRY':
            echo 'AutoHeal: registry retry requested.'
            break

        default:
            error("AutoHeal: unsupported action '${action}'.")
    }
}


private void notifyAutoHeal(Map config = [:]) {

    String baseUrl =
        (
            config.url
            ?: env.AUTOHEAL_URL
            ?: 'http://127.0.0.1:8000'
        ).replaceAll('/+$', '')

    String credentialId =
        config.secretCredentialId
        ?: 'autoheal-webhook-secret'


    def payload = """
{
  "job_name": "${env.JOB_NAME}",
  "build_number": ${env.BUILD_NUMBER},
  "build_url": "${env.BUILD_URL ?: ''}",
  "status": "FAILURE"
}
"""


    withCredentials([
        string(
            credentialsId: credentialId,
            variable: 'AUTOHEAL_WEBHOOK_SECRET'
        )
    ]) {

        sh """
            set -eu

            curl \
              --fail \
              --silent \
              --show-error \
              --request POST \
              --header 'Content-Type: application/json' \
              --header "X-AutoHeal-Secret: \$AUTOHEAL_WEBHOOK_SECRET" \
              --data '${payload.replace("'", "'\"'\"'")}' \
              '${baseUrl}/webhook/jenkins'
        """
    }
}