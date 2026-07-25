pipeline {
    agent any

    options {
        skipDefaultCheckout(true)
        timestamps()
        timeout(time: 60, unit: 'MINUTES')
        disableConcurrentBuilds()
    }

    environment {
        OLLAMA_URL = 'http://127.0.0.1:11434'
        OLLAMA_MODEL = 'qwen2.5-coder:1.5b'
        OLLAMA_TIMEOUT_SECONDS = '300'
        UV_NO_PROGRESS = '1'
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

                    echo Installing locked third-party dependencies...
                    echo Local workspace packages will be loaded through PYTHONPATH.

                    "%UV_EXE%" sync --locked --no-install-workspace

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

                    function Test-OllamaApi {
                        try {
                            Invoke-RestMethod `
                                -Uri "$env:OLLAMA_URL/api/tags" `
                                -Method Get `
                                -TimeoutSec 5 |
                                Out-Null

                            return $true
                        }
                        catch {
                            return $false
                        }
                    }

                    if (Test-OllamaApi) {
                        Write-Host "Ollama API is already running."
                    }
                    else {
                        Write-Host "Ollama API is not running. Searching for ollama.exe..."

                        $ollamaCandidates = @()

                        if ($env:OLLAMA_EXE) {
                            $ollamaCandidates += $env:OLLAMA_EXE
                        }

                        $ollamaCommand = Get-Command `
                            ollama `
                            -ErrorAction SilentlyContinue

                        if ($ollamaCommand) {
                            $ollamaCandidates += $ollamaCommand.Source
                        }

                        if ($env:LOCALAPPDATA) {
                            $ollamaCandidates += Join-Path `
                                $env:LOCALAPPDATA `
                                "Programs\\Ollama\\ollama.exe"
                        }

                        if ($env:ProgramFiles) {
                            $ollamaCandidates += Join-Path `
                                $env:ProgramFiles `
                                "Ollama\\ollama.exe"
                        }

                        $userOllama = Get-ChildItem `
                            -Path "C:\\Users\\*\\AppData\\Local\\Programs\\Ollama\\ollama.exe" `
                            -File `
                            -ErrorAction SilentlyContinue |
                            Select-Object -First 1

                        if ($userOllama) {
                            $ollamaCandidates += $userOllama.FullName
                        }

                        $ollamaExecutable = $ollamaCandidates |
                            Where-Object {
                                $_ -and (Test-Path $_)
                            } |
                            Select-Object -First 1

                        if (-not $ollamaExecutable) {
                            throw @"
Ollama is not running and ollama.exe was not found.
Start Ollama before the Jenkins build or define OLLAMA_EXE in Jenkins.
"@
                        }

                        Write-Host "Starting Ollama from: $ollamaExecutable"

                        Start-Process `
                            -FilePath $ollamaExecutable `
                            -ArgumentList "serve" `
                            -WindowStyle Hidden

                        for ($attempt = 1; $attempt -le 30; $attempt++) {
                            if (Test-OllamaApi) {
                                break
                            }

                            Write-Host "Waiting for Ollama: attempt $attempt/30"
                            Start-Sleep -Seconds 2
                        }
                    }

                    if (-not (Test-OllamaApi)) {
                        throw "Ollama API did not start at $env:OLLAMA_URL."
                    }

                    Write-Host "Ollama API is ready."
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

                    if ($availableModels -notcontains $env:OLLAMA_MODEL) {
                        Write-Host "Model $env:OLLAMA_MODEL is missing. Pulling it now..."

                        $pullBody = @{
                            model = $env:OLLAMA_MODEL
                            stream = $false
                        } | ConvertTo-Json -Depth 5

                        Invoke-RestMethod `
                            -Uri "$env:OLLAMA_URL/api/pull" `
                            -Method Post `
                            -ContentType "application/json" `
                            -Body $pullBody `
                            -TimeoutSec 1800 |
                            Out-Null
                    }

                    $verificationResponse = Invoke-RestMethod `
                        -Uri "$env:OLLAMA_URL/api/tags" `
                        -Method Get `
                        -TimeoutSec 10

                    $verifiedModels = @(
                        $verificationResponse.models |
                            ForEach-Object {
                                $_.name
                            }
                    )

                    if ($verifiedModels -notcontains $env:OLLAMA_MODEL) {
                        throw "Configured model $env:OLLAMA_MODEL is not available."
                    }

                    Write-Host "Configured model is available: $env:OLLAMA_MODEL"
                '''
            }
        }

        stage('Warm Up Ollama Model') {
            steps {
                powershell '''
                    $ErrorActionPreference = "Stop"

                    Write-Host "Warming up model $env:OLLAMA_MODEL..."

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
                        -TimeoutSec ([int]$env:OLLAMA_TIMEOUT_SECONDS)

                    if (-not $response.message) {
                        throw "Ollama warm-up request failed."
                    }

                    Write-Host "Ollama model is ready."
                    Write-Host "Model response: $($response.message.content)"
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
                    set "PYTHONPATH=%WORKSPACE%\\libs\\common\\src;%WORKSPACE%\\services\\gateway\\src;%WORKSPACE%\\services\\repository_storage_service\\src;%WORKSPACE%\\services\\repository_scanner_service\\src"

                    if exist test-results.xml (
                        del /q test-results.xml
                    )

                    echo Python path:
                    echo %PYTHONPATH%

                    echo Running tests with Ollama model:
                    echo %OLLAMA_MODEL%

                    "%UV_EXE%" run --no-sync pytest -v --junitxml=test-results.xml

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
            echo 'Dependency Sentinel pipeline completed successfully.'
            echo 'Ollama model: qwen2.5-coder:1.5b'
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
