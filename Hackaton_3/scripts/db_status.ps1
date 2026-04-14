$ErrorActionPreference = 'Stop'

Write-Host 'Container status:'
docker compose ps | Out-Host

$containerId = docker compose ps -q postgres
if ([string]::IsNullOrWhiteSpace($containerId)) {
	Write-Host 'PostgreSQL container is not running.'
	exit 0
}

Write-Host ''
Write-Host 'Recent PostgreSQL logs:'
docker logs --tail 40 $containerId | Out-Host
