pipeline {
    agent any

    options {
        skipDefaultCheckout(true)
        timestamps()
        timeout(time: 60, unit: 'MINUTES')
    }

    environment {
        OLLAMA_URL = 'http://127.0.0.1:11434'
        OLLAMA_MODEL = 'qwen2.5-coder:1.5b'
        OLLAMA_TIMEOUT_SECONDS = '300'
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

                    $uvDirectory = Join-Path `
                        $env:WORKSPACE `
                        "tools\\uv"

                    $uvExecutable = Join-Path `
                        $uvDirectory `
                        "uv.exe"

                    if (-not (Test-Path $uvExecutable)) {
                        Write-Host `
                            "Installing uv in the Jenkins workspace..."

                        $env:UV_UNMANAGED_INSTALL = $uvDirectory

                        Invoke-RestMethod `
                            "https://astral.sh/uv/install.ps1" |
                            Invoke-Expression
                    }

                    if (-not (Test-Path $uvExecutable)) {
                        throw "uv.exe was not found after installation."
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

                    if errorlevel 1 (
                        exit /b 1
                    )

                    echo Python interpreter selected by uv:

                    "%UV_EXE%" python find

                    if errorlevel 1 (
                        exit /b 1
                    )
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

                    if errorlevel 1 (
                        exit /b 1
                    )
                '''
            }
        }

        stage('Prepare Ollama') {
            steps {
                powershell '''
                    $ErrorActionPreference = "Stop"

                    Write-Host "Searching for Ollama..."

                    $ollamaCandidates = @()

                    $ollamaCommand = Get-Command `
                        ollama `
                        -ErrorAction SilentlyContinue

                    if ($ollamaCommand) {
                        $ollamaCandidates += $ollamaCommand.Source
                    }

                    if ($env:OLLAMA_EXE) {
                        $ollamaCandidates += $env:OLLAMA_EXE
                    }

                    $ollamaCandidates += Join-Path `
                        $env:LOCALAPPDATA `
                        "Programs\\Ollama\\ollama.exe"

                    $ollamaCandidates += Join-Path `
                        $env:WORKSPACE `
                        "tools\\ollama\\ollama.exe"

                    $ollamaExecutable = $ollamaCandidates |
                        Where-Object {
                            $_ -and (Test-Path $_)
                        } |
                        Select-Object -First 1

                    if (-not $ollamaExecutable) {
                        Write-Host "Ollama was not found."
                        Write-Host "Installing Ollama..."

                        Invoke-RestMethod `
                            "https://ollama.com/install.ps1" |
                            Invoke-Expression

                        $ollamaExecutable = Join-Path `
                            $env:LOCALAPPDATA `
                            "Programs\\Ollama\\ollama.exe"
                    }

                    if (-not (Test-Path $ollamaExecutable)) {
                        throw "Ollama executable was not found."
                    }

                    Write-Host `
                        "Ollama executable: $ollamaExecutable"

                    & $ollamaExecutable --version

                    if ($LASTEXITCODE -ne 0) {
                        throw "Unable to execute Ollama."
                    }

                    Write-Host "Checking Ollama API..."

                    $ollamaRunning = $false

                    try {
                        Invoke-RestMethod `
                            -Uri "$env:OLLAMA_URL/api/tags" `
                            -Method Get `
                            -TimeoutSec 5 |
                            Out-Null

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
                        for (
                            $attempt = 1;
                            $attempt -le 30;
                            $attempt++
                        ) {
                            try {
                                Invoke-RestMethod `
                                    -Uri "$env:OLLAMA_URL/api/tags" `
                                    -Method Get `
                                    -TimeoutSec 5 |
                                    Out-Null

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

                    $installedModels = & $ollamaExecutable list

                    if ($LASTEXITCODE -ne 0) {
                        throw "Unable to list Ollama models."
                    }

                    $modelInstalled = $installedModels |
                        Select-String `
                            -SimpleMatch `
                            $env:OLLAMA_MODEL

                    if (-not $modelInstalled) {
                        Write-Host `
                            "Downloading model $env:OLLAMA_MODEL..."

                        & $ollamaExecutable pull `
                            $env:OLLAMA_MODEL

                        if ($LASTEXITCODE -ne 0) {
                            throw `
                                "Failed to download model $env:OLLAMA_MODEL."
                        }
                    }
                    else {
                        Write-Host `
                            "Model $env:OLLAMA_MODEL is already installed."
                    }
                '''
            }
        }

        stage('Verify Ollama Model') {
            steps {
                powershell '''
                    $ErrorActionPreference = "Stop"

                    $response = Invoke-RestMethod `
                        -Uri "$env:OLLAMA_URL/api/tags" `
                        -Method Get `
                        -TimeoutSec 10

                    if (-not $response.models) {
                        throw "No Ollama model is available."
                    }

                    $availableModels = @(
                        $response.models |
                            ForEach-Object {
                                $_.name
                            }
                    )

                    Write-Host "Available Ollama models:"

                    foreach ($modelName in $availableModels) {
                        Write-Host "- $modelName"
                    }

                    if (
                        $availableModels -notcontains
                        $env:OLLAMA_MODEL
                    ) {
                        throw `
                            "Configured model $env:OLLAMA_MODEL is not installed."
                    }

                    Write-Host `
                        "Configured model is available: $env:OLLAMA_MODEL"
                '''
            }
        }

        stage('Warm Up Ollama Model') {
            steps {
                powershell '''
                    $ErrorActionPreference = "Stop"

                    Write-Host `
                        "Warming up model $env:OLLAMA_MODEL..."

                    $requestBody = @{
                        model = $env:OLLAMA_MODEL
                        messages = @(
                            @{
                                role = "user"
                                content = "Reply only with OK."
                            }
                        )
                        stream = $false
                        keep_alive = "10m"
                        options = @{
                            temperature = 0
                        }
                    } | ConvertTo-Json -Depth 10

                    $response = Invoke-RestMethod `
                        -Uri "$env:OLLAMA_URL/api/chat" `
                        -Method Post `
                        -ContentType "application/json" `
                        -Body $requestBody `
                        -TimeoutSec (
                            [int]$env:OLLAMA_TIMEOUT_SECONDS
                        )

                    if (-not $response.message) {
                        throw "Ollama warm-up request failed."
                    }

                    Write-Host "Ollama model is ready."
                    Write-Host `
                        "Model response: $($response.message.content)"
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

                    echo Running tests with Ollama model:
                    echo %OLLAMA_MODEL%

                    "%UV_EXE%" run pytest -v --junitxml=test-results.xml

                    if errorlevel 1 (
                        exit /b 1
                    )
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
            echo '''
                Dependency Sentinel pipeline completed successfully.
                Ollama model: qwen2.5-coder:1.5b
            '''
        }

        failure {
            echo '''
                Pipeline failed.
                Check the first ERROR in Console Output.
            '''
        }

        always {
            archiveArtifacts(
                artifacts: 'test-results.xml',
                allowEmptyArchive: true
            )
        }
    }
}