pipeline {
    agent any

    options {
        skipDefaultCheckout(true)
        timestamps()
        timeout(time: 30, unit: 'MINUTES')
    }

    environment {
        PYTHON_CMD = 'py'
        PIP_DISABLE_PIP_VERSION_CHECK = '1'
    }

    stages {
        stage('Checkout') {
            steps {
                checkout scm
            }
        }

        stage('Verify Environment') {
            steps {
                bat '''
                    @echo off

                    echo ========================================
                    echo Jenkins Windows environment
                    echo ========================================

                    echo Current user:
                    whoami

                    echo Current workspace:
                    cd

                    echo Workspace content:
                    dir

                    echo Python launcher:
                    where %PYTHON_CMD%

                    echo Python version:
                    %PYTHON_CMD% --version

                    if not exist pyproject.toml (
                        echo.
                        echo ERROR: pyproject.toml was not found.
                        echo Check the Git repository and Jenkins branch configuration.
                        exit /b 1
                    )

                    echo pyproject.toml found successfully.
                '''
            }
        }

        stage('Install UV') {
            steps {
                bat '''
                    @echo off

                    echo Installing uv...
                    %PYTHON_CMD% -m pip install --upgrade uv

                    echo Checking uv...
                    %PYTHON_CMD% -m uv --version
                '''
            }
        }

        stage('Install Dependencies') {
            steps {
                bat '''
                    @echo off

                    if exist uv.lock (
                        echo uv.lock found. Installing locked dependencies...
                        %PYTHON_CMD% -m uv sync --locked
                    ) else (
                        echo WARNING: uv.lock was not found.
                        echo Installing dependencies from pyproject.toml...
                        %PYTHON_CMD% -m uv sync
                    )
                '''
            }
        }

        stage('Run Tests') {
            steps {
                bat '''
                    @echo off

                    echo Running tests...
                    %PYTHON_CMD% -m uv run pytest -v --junitxml=test-results.xml
                '''
            }

            post {
                always {
                    junit(
                        testResults: 'test-results.xml',
                        allowEmptyResults: true
                    )
                }
            }
        }
    }

    post {
        success {
            echo 'Dependency Sentinel pipeline completed successfully.'
        }

        unstable {
            echo 'Pipeline completed, but some tests failed.'
        }

        failure {
            echo 'Pipeline failed. Check the first ERROR in Console Output.'
        }

        always {
            archiveArtifacts(
                artifacts: 'test-results.xml',
                allowEmptyArchive: true
            )
        }
    }
}