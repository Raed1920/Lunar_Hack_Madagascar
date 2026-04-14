param(
	[switch]$Fresh
)

$ErrorActionPreference = 'Stop'

Write-Host 'Stopping local PostgreSQL container...'
if ($Fresh) {
	docker compose down -v | Out-Host
	Write-Host 'PostgreSQL stack stopped and volumes removed (fresh reset).'
}
else {
	docker compose down | Out-Host
	Write-Host 'PostgreSQL stack stopped.'
}
