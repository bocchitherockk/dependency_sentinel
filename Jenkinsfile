pipeline {
    agent any

    options {
        skipDefaultCheckout(true)
        timestamps()
        timeout(time: 30, unit: 'MINUTES')
    }

    stages {
        stage('Checkout') {
            steps {
                checkout scm
            }
        }

        stage('Verify Project') {
            steps {
                bat '''
                    @echo off

                    echo Current user:
                    whoami

                    echo Current workspace:
                    cd

                    echo Project files:
                    dir

                    if not exist pyproject.toml (
                        echo ERROR: pyproject.toml not found
                        exit /b 1
                    )

                    if not exist uv.lock (
                        echo ERROR: uv.lock not found
                        exit /b 1
                    )

                    if exist .python-version (
                        echo Requested Python version:
                        type .python-version
                    )
                '''
            }
        }

        stage('Install UV') {
            steps {
                powershell '''
                    $ErrorActionPreference = "Stop"

                    $uvDirectory = Join-Path $env:WORKSPACE "tools\\uv"
                    $uvExecutable = Join-Path $uvDirectory "uv.exe"

                    if (-not (Test-Path $uvExecutable)) {
                        Write-Host "Installing uv in the Jenkins workspace..."

                        $env:UV_UNMANAGED_INSTALL = $uvDirectory
                        Invoke-RestMethod "https://astral.sh/uv/install.ps1" |
                            Invoke-Expression
                    }

                    & $uvExecutable --version

                    if ($LASTEXITCODE -ne 0) {
                        exit $LASTEXITCODE
                    }
                '''
            }
        }

        stage('Install Python') {
            steps {
                bat '''
                    @echo off

                    set "UV_EXE=%WORKSPACE%\\tools\\uv\\uv.exe"
                    set "UV_PYTHON_INSTALL_DIR=%WORKSPACE%\\.uv-python"
                    set "UV_CACHE_DIR=%WORKSPACE%\\.uv-cache"

                    echo Installing the Python version requested by the project...

                    "%UV_EXE%" python install
                    if errorlevel 1 exit /b 1

                    echo Python interpreter selected by uv:
                    "%UV_EXE%" python find
                    if errorlevel 1 exit /b 1
                '''
            }
        }

        stage('Install Dependencies') {
            steps {
                bat '''
                    @echo off

                    set "UV_EXE=%WORKSPACE%\\tools\\uv\\uv.exe"
                    set "UV_PYTHON_INSTALL_DIR=%WORKSPACE%\\.uv-python"
                    set "UV_CACHE_DIR=%WORKSPACE%\\.uv-cache"

                    echo Installing locked dependencies...

                    "%UV_EXE%" sync --locked
                    if errorlevel 1 exit /b 1
                '''
            }
        }

        stage('Run Tests') {
            steps {
                bat '''
                    @echo off

                    set "UV_EXE=%WORKSPACE%\\tools\\uv\\uv.exe"
                    set "UV_PYTHON_INSTALL_DIR=%WORKSPACE%\\.uv-python"
                    set "UV_CACHE_DIR=%WORKSPACE%\\.uv-cache"

                    if exist test-results.xml (
                        del /q test-results.xml
                    )

                    echo Running tests...

                    "%UV_EXE%" run pytest -v --junitxml=test-results.xml
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