/*
 * AutoHeal Jenkins remediation integration
 *
 * AutoHeal sends explicit parameters.
 * Jenkins is responsible for executing the remediation
 * inside the Jenkins agent.
 *
 * Requires:
 *   Workspace Cleanup Plugin
 */

pipeline {

    agent any

    options {
        /*
         * Needed when AutoHeal must clean the workspace
         * before performing SCM checkout.
         */
        skipDefaultCheckout(true)
    }

    parameters {

        booleanParam(
            name: 'AUTOHEAL_RETRY',
            defaultValue: false,
            description: 'Build was triggered by AutoHeal.'
        )

        string(
            name: 'AUTOHEAL_ACTION',
            defaultValue: '',
            description: 'Category-specific AutoHeal remediation action.'
        )

        booleanParam(
            name: 'AUTOHEAL_CLEAN_WORKSPACE',
            defaultValue: false,
            description: 'Clean Jenkins workspace before checkout.'
        )

        booleanParam(
            name: 'AUTOHEAL_FRESH_CHECKOUT',
            defaultValue: false,
            description: 'Perform a fresh SCM checkout.'
        )

        booleanParam(
            name: 'AUTOHEAL_CLEAN_DEPENDENCY_ENV',
            defaultValue: false,
            description: 'Recreate the dependency environment.'
        )

        booleanParam(
            name: 'AUTOHEAL_INSTALL_FROM_LOCKFILE',
            defaultValue: false,
            description: 'Install using the repository dependency definition.'
        )

        booleanParam(
            name: 'AUTOHEAL_DOCKER_NO_CACHE',
            defaultValue: false,
            description: 'Build Docker image without the build cache.'
        )

        booleanParam(
            name: 'AUTOHEAL_CONNECTIVITY_CHECK',
            defaultValue: false,
            description: 'Run network connectivity checks on the Jenkins agent.'
        )

        string(
            name: 'AUTOHEAL_BACKOFF_SECONDS',
            defaultValue: '10',
            description: 'Backoff requested for network recovery.'
        )
    }

    stages {

        stage('AutoHeal Recovery') {

            when {
                expression {
                    params.AUTOHEAL_RETRY
                }
            }

            steps {

                script {

                    /*
                     * ====================================
                     * WORKSPACE REMEDIATION
                     * ====================================
                     */

                    if (
                        params.AUTOHEAL_CLEAN_WORKSPACE
                    ) {

                        echo(
                            'AutoHeal: cleaning workspace'
                        )

                        cleanWs()
                    }

                    if (
                        params.AUTOHEAL_FRESH_CHECKOUT
                    ) {

                        echo(
                            'AutoHeal: performing fresh checkout'
                        )

                        checkout scm
                    }

                    /*
                     * ====================================
                     * NETWORK REMEDIATION
                     * ====================================
                     */

                    if (
                        params.AUTOHEAL_CONNECTIVITY_CHECK
                    ) {

                        echo(
                            'AutoHeal: checking connectivity'
                        )

                        sh '''
                            set -eu

                            getent hosts registry-1.docker.io

                            curl \
                              --fail \
                              --silent \
                              --show-error \
                              --max-time 10 \
                              https://registry-1.docker.io/v2/ \
                              || true
                        '''
                    }

                    /*
                     * Backoff happens before normal
                     * pipeline work continues.
                     */

                    if (
                        params.AUTOHEAL_BACKOFF_SECONDS?.isInteger()
                    ) {

                        int seconds =
                            params.AUTOHEAL_BACKOFF_SECONDS.toInteger()

                        if (seconds > 0) {

                            echo(
                                "AutoHeal: waiting ${seconds}s before recovery"
                            )

                            sleep(
                                time: seconds,
                                unit: 'SECONDS'
                            )
                        }
                    }
                }
            }
        }

        /*
         * =========================================
         * CHECKOUT
         * =========================================
         */

        stage('Checkout') {

            when {
                expression {
                    !params.AUTOHEAL_FRESH_CHECKOUT
                }
            }

            steps {

                checkout scm
            }
        }

        /*
         * =========================================
         * DEPENDENCIES
         * =========================================
         */

        stage('Dependencies') {

            steps {

                script {

                    if (
                        params.AUTOHEAL_CLEAN_DEPENDENCY_ENV
                    ) {

                        echo(
                            'AutoHeal: recreating dependency environment'
                        )

                        /*
                         * Python example.
                         * Adapt for your actual application stack.
                         */

                        sh '''
                            rm -rf .venv
                            python3 -m venv .venv
                        '''
                    }

                    if (
                        params.AUTOHEAL_INSTALL_FROM_LOCKFILE
                    ) {

                        echo(
                            'AutoHeal: installing dependencies'
                        )

                        /*
                         * Current AutoHeal example uses
                         * requirements.txt.
                         *
                         * For projects with an actual lockfile,
                         * replace this with the correct locked
                         * install command.
                         */

                        sh '''
                            . .venv/bin/activate

                            python -m pip install \
                              -r requirements.txt
                        '''
                    }
                }
            }
        }

        /*
         * =========================================
         * DOCKER
         * =========================================
         */

        stage('Docker Build') {

            steps {

                script {

                    if (
                        params.AUTOHEAL_DOCKER_NO_CACHE
                    ) {

                        echo(
                            'AutoHeal: rebuilding Docker image without cache'
                        )

                        sh '''
                            docker build \
                              --no-cache \
                              -t autoheal-demo:recovery \
                              .
                        '''

                    } else {

                        sh '''
                            docker build \
                              -t autoheal-demo:build \
                              .
                        '''
                    }
                }
            }
        }

        /*
         * =========================================
         * NORMAL PIPELINE
         * =========================================
         */

        stage('Test / Build') {

            steps {

                echo(
                    'Run the application normal build/test stages here.'
                )
            }
        }
    }
}