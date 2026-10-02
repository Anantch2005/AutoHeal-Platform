@Library('AutoHeal') _

/*
 * Minimal AutoHeal integration.
 *
 * The consumer pipeline only needs:
 *
 *     autoheal()
 *
 * before checkout/setup, and:
 *
 *     autoheal()
 *
 * in post { failure { ... } }.
 *
 * AutoHeal itself decides classification,
 * policy and remediation action.
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
         * Internal routing parameter.
         *
         * AutoHeal supplies this when it triggers
         * a remediation build.
         *
         * Normal users leave it empty.
         */

        string(
            name: 'AUTOHEAL_ACTION',
            defaultValue: '',
            description: (
                'Internal AutoHeal routing value. '
                + 'Leave empty for normal builds.'
            )
        )
    }


    stages {


        stage('Checkout') {

            steps {

                script {

                    /*
                     * Normal build:
                     *     no-op
                     *
                     * Retry:
                     *     execute requested preparation
                     */

                    autoheal()

                    checkout scm
                }
            }
        }


        stage('Application Pipeline') {

            steps {

                echo(
                    'Run the normal project pipeline here.'
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