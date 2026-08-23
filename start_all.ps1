# Lancer Kafka et Kafka UI via Docker Compose
Write-Host "Démarrage de Kafka via docker-compose..."
docker-compose up -d

# Liste de tous les services à lancer
$services = @(
    "gateway",
    "llm-service",
    "mcp-server",
    "registry-service",
    "repository-scanner-service",
    "repository-storage-service",
    "security-intelligence-service",
    "scheduler"
)

# Ouvrir une nouvelle fenêtre PowerShell pour chaque service
foreach ($service in $services) {
    Write-Host "Démarrage de $service..."
    Start-Process powershell -ArgumentList "-NoExit", "-Command", "uv run --package $service $service"
}

Write-Host "Tous les services sont en cours de démarrage !"
Write-Host "Tu auras une fenêtre pour chaque service pour voir les logs."
