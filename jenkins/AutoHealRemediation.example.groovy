@Library('AutoHeal') _

/*
 * Minimal AutoHeal integration example.
 *
 * AutoHeal Shared Library contains ONLY autoheal().
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
         * Internal parameter used only when AutoHeal
         * triggers a retry build.
         */
        string(
            name: 'AUTOHEAL_ACTION',
            defaultValue: '',
            description: (
                'Internal AutoHeal action. '
                + 'Leave empty for normal builds.'
            )
        )
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

                echo(
                    'Normal application pipeline.'
                )
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