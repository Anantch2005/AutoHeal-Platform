/*
 * AutoHeal Jenkins Shared Library integration
 *
 * Consumer contract:
 *   1. Define one internal AUTOHEAL_ACTION parameter.
 *   2. Call autoheal() before SCM checkout.
 *   3. Call autoheal() from post/failure.
 *
 * The pipeline does NOT need to know failure categories or define
 * remediation flags. AutoHeal decides the action; the shared library
 * executes it on the Jenkins agent.
 */

@Library('AutoHeal') _

pipeline {

    agent any

    options {
        skipDefaultCheckout(true)
    }

    stages {

        stage('Checkout') {
            steps {
                script {
                    autoheal()
                    checkout scm
                }
            }
        }

        stage('Build') {
            steps {
                echo 'Normal application pipeline'
            }
        }
    }

    post {
        failure {
            script {
                autoheal()
            }
        }
    }
}