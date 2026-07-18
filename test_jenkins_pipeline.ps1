Write-Host "========================================" -ForegroundColor Cyan
Write-Host "🧪 TEST DU PIPELINE JENKINS" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan

$ERRORS = 0

function Test-Step {
    param(
        [string]$Name,
        [scriptblock]$Command
    )
    Write-Host "`n Étape : $Name" -ForegroundColor Yellow
    Write-Host "----------------------------------------" -ForegroundColor Gray
    
    try {
        & $Command
        if ($LASTEXITCODE -ne 0) {
            throw "La commande a échoué avec le code $LASTEXITCODE"
        }
        Write-Host " $Name : RÉUSSI" -ForegroundColor Green
    } catch {
        Write-Host " $Name : ÉCHOUÉ" -ForegroundColor Red
        Write-Host "   Erreur : $_" -ForegroundColor Red
        $global:ERRORS++
    }
}

Test-Step -Name "Checkout" -Command {
    Write-Host "    Vérification des fichiers du projet..."
    if (Test-Path "pyproject.toml") {
        Write-Host "    pyproject.toml trouvé"
    } else {
        throw "pyproject.toml non trouvé"
    }
    if (Test-Path "Jenkinsfile") {
        Write-Host "  Jenkinsfile trouvé"
    } else {
        throw "Jenkinsfile non trouvé"
    }
}

Test-Step -Name "Setup Python" -Command {
    $version = py --version 2>&1
    Write-Host "    $version"
    if ($LASTEXITCODE -ne 0) {
        throw "Python n'est pas installé"
    }
}

Test-Step -Name "Install Dependencies" -Command {
    Write-Host "    Installation de uv..."
    py -m pip install uv
    Write-Host "    Synchronisation des dépendances..."
    uv sync
}

Test-Step -Name "Run Tests" -Command {
    Write-Host "    Lancement des tests..."
    uv run pytest -v --junitxml=test-results.xml
}

Test-Step -Name "Build Docker Images" -Command {
    Write-Host "    Construction du Gateway..."
    docker build -t dependency-sentinel-gateway:test -f services/gateway/Dockerfile .
    
    Write-Host "    Construction du Scanner..."
    docker build -t dependency-sentinel-scanner:test -f services/repository_scanner_service/Dockerfile .
}

Write-Host "`n========================================" -ForegroundColor Cyan
Write-Host " RÉSUMÉ DU TEST" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan

if ($ERRORS -eq 0) {
    Write-Host " PIPELINE VALIDÉ ! Toutes les étapes ont réussi." -ForegroundColor Green
    Write-Host " Ton Jenkinsfile est prêt à être utilisé !" -ForegroundColor Green
} else {
    Write-Host " $ERRORS étape(s) ont échoué." -ForegroundColor Red
    Write-Host " Corrige les erreurs et relance le test." -ForegroundColor Yellow
}

Write-Host "`n Images Docker créées :" -ForegroundColor Cyan
docker images --format "table {{.Repository}}\t{{.Tag}}\t{{.Size}}" | findstr dependency-sentinel