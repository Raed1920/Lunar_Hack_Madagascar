$ErrorActionPreference = 'Stop'

Write-Host 'Starting local PostgreSQL container...'
docker compose up -d --wait postgres | Out-Host

$containerId = docker compose ps -q postgres
if ([string]::IsNullOrWhiteSpace($containerId)) {
  Write-Error 'Could not resolve postgres container ID from docker compose.'
}

$health = docker inspect --format='{{.State.Health.Status}}' $containerId 2>$null
if ($health -ne 'healthy') {
  Write-Error 'PostgreSQL container is not healthy. Check logs with: ./scripts/db_status.ps1'
}

Write-Host "PostgreSQL is healthy and ready. Container: $containerId"

$dbUser = if ($env:POSTGRES_USER) { $env:POSTGRES_USER } else { 'marketing_user' }
$dbName = if ($env:POSTGRES_DB) { $env:POSTGRES_DB } else { 'marketing_ai_dev' }

Write-Host 'Applying compatibility migrations for n8n workflows...'
docker compose exec -T postgres psql -v ON_ERROR_STOP=1 -U $dbUser -d $dbName -f /docker-entrypoint-initdb.d/030_n8n_compat.sql | Out-Host
docker compose exec -T postgres psql -v ON_ERROR_STOP=1 -U $dbUser -d $dbName -f /docker-entrypoint-initdb.d/031_n8n_event_store.sql | Out-Host
