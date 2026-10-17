
@Library('BuildSentry') _

/*
 * Minimal BuildSentry integration example.
 *
 * BuildSentry Shared Library contains ONLY buildsentry().
 *
 * Generic CI/CD steps belong to the separate Shared library.
 */

pipeline {

    agent any


    options {

        skipDefaultCheckout(
            true
        )

        timestamps()
    }


    parameters {

        /*
         * Internal parameter used only when BuildSentry
         * triggers a retry build.
         */
        string(
            name: 'AUTOHEAL_ACTION',
            defaultValue: '',
            description: (
                'Internal BuildSentry action. '
                + 'Leave empty for normal builds.'
            )
        )
    }


    stages {

        stage('Checkout') {

            steps {

                script {

                    buildsentry(stage: 'checkout')

                    checkout scm
                }
            }
        }


        stage('Build') {

            steps {

                echo(
                    'Normal application pipeline.'
                )
            }
        }
    }


    post {

        failure {

            script {

                buildsentry()
            }
        }
    }
}