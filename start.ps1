param(
    [switch]$NoBrowser
)

$ErrorActionPreference = "Stop"
$url = "http://127.0.0.1:8700"

try {
    docker compose version | Out-Null
} catch {
    Write-Error "Docker Desktop with Docker Compose is required. Install or update it, then run start.cmd again."
    exit 1
}

Write-Host "Building and starting Agent Flight Recorder..."
docker compose up --build -d
if ($LASTEXITCODE -ne 0) {
    exit $LASTEXITCODE
}

$containerId = (docker compose ps -q afr).Trim()
if (-not $containerId) {
    Write-Error "AFR did not create a container. Run 'docker compose logs afr' for details."
    exit 1
}

$status = "starting"
for ($attempt = 0; $attempt -lt 90; $attempt++) {
    $status = (docker inspect --format "{{if .State.Health}}{{.State.Health.Status}}{{else}}{{.State.Status}}{{end}}" $containerId 2>$null).Trim()
    if ($status -eq "healthy") {
        break
    }
    if ($status -in @("unhealthy", "exited", "dead")) {
        Write-Error "AFR failed to become healthy (status: $status)."
        docker compose logs afr
        exit 1
    }
    Start-Sleep -Seconds 1
}

if ($status -ne "healthy") {
    Write-Error "AFR did not become healthy before the startup deadline."
    docker compose logs afr
    exit 1
}

Write-Host "Agent Flight Recorder is ready at $url"
Write-Host "Data is stored in the Docker volume named afr-data."
Write-Host "Stop it with: docker compose down"

if (-not $NoBrowser) {
    Start-Process $url
}
