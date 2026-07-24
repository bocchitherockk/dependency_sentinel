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

                    "%UV_EXE%" sync --locked --all-packages
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

    pipeline {
    agent any

    environment {
        OLLAMA_URL = 'http://127.0.0.1:11434'
        OLLAMA_MODEL = 'qwen2.5-coder:3b'
        STORAGE_URL = 'http://127.0.0.1:8001'
    }

    stages {
        stage('Checkout') {
            steps {
                checkout scm
            }
        }

        stage('Install and prepare Ollama') {
            steps {
                powershell '''
                    $ErrorActionPreference = "Stop"

                    Write-Host "Checking Ollama installation..."

                    $ollamaCommand = Get-Command ollama `
                        -ErrorAction SilentlyContinue

                    if (-not $ollamaCommand) {
                        Write-Host "Ollama is not installed."
                        Write-Host "Installing Ollama..."

                        irm https://ollama.com/install.ps1 | iex

                        $ollamaExecutable = Join-Path `
                            $env:LOCALAPPDATA `
                            "Programs\\Ollama\\ollama.exe"
                    }
                    else {
                        $ollamaExecutable = $ollamaCommand.Source
                    }

                    if (-not (Test-Path $ollamaExecutable)) {
                        throw "Ollama executable was not found."
                    }

                    Write-Host "Ollama executable: $ollamaExecutable"

                    & $ollamaExecutable --version

                    Write-Host "Checking Ollama API..."

                    $ollamaRunning = $false

                    try {
                        Invoke-RestMethod `
                            -Uri "$env:OLLAMA_URL/api/tags" `
                            -TimeoutSec 5 | Out-Null

                        $ollamaRunning = $true
                    }
                    catch {
                        Write-Host "Starting Ollama server..."

                        Start-Process `
                            -FilePath $ollamaExecutable `
                            -ArgumentList "serve" `
                            -WindowStyle Hidden
                    }

                    if (-not $ollamaRunning) {
                        for ($attempt = 1; $attempt -le 30; $attempt++) {
                            try {
                                Invoke-RestMethod `
                                    -Uri "$env:OLLAMA_URL/api/tags" `
                                    -TimeoutSec 5 | Out-Null

                                $ollamaRunning = $true
                                break
                            }
                            catch {
                                Write-Host `
                                    "Waiting for Ollama: attempt $attempt/30"

                                Start-Sleep -Seconds 2
                            }
                        }
                    }

                    if (-not $ollamaRunning) {
                        throw "Ollama API did not start."
                    }

                    Write-Host "Ollama API is running."

                    $models = & $ollamaExecutable list

                    $modelInstalled = $models |
                        Select-String `
                            -SimpleMatch `
                            $env:OLLAMA_MODEL

                    if (-not $modelInstalled) {
                        Write-Host `
                            "Downloading model $env:OLLAMA_MODEL..."

                        & $ollamaExecutable pull `
                            $env:OLLAMA_MODEL

                        if ($LASTEXITCODE -ne 0) {
                            throw "Failed to download Ollama model."
                        }
                    }
                    else {
                        Write-Host `
                            "Model $env:OLLAMA_MODEL is already installed."
                    }
                '''
            }
        }

        stage('Verify Ollama') {
            steps {
                powershell '''
                    $response = Invoke-RestMethod `
                        -Uri "$env:OLLAMA_URL/api/tags" `
                        -Method Get

                    if (-not $response.models) {
                        throw "No Ollama model is available."
                    }

                    Write-Host "Ollama is ready."
                    Write-Host "Configured model: $env:OLLAMA_MODEL"

                    $response.models |
                        ForEach-Object {
                            Write-Host "Available model: $($_.name)"
                        }
                '''
            }
        }

        stage('Install Python dependencies') {
            steps {
                powershell '''
                    uv sync --all-packages
                '''
            }
        }

        stage('Run tests') {
            steps {
                powershell '''
                    uv run pytest -v
                '''
            }
        }
    }

    post {
        success {
            echo 'Pipeline completed successfully.'
        }

        failure {
            echo 'Pipeline failed.'
        }
    }
}
}