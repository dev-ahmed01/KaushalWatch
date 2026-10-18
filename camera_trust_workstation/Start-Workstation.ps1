# KaushalWatch Camera Trust unified research workstation.
# Runs read-only API on localhost:8766 without interfering with older container.
param([switch]$WithFullVideos)
$ErrorActionPreference = 'Stop'
$root = Split-Path -Parent $MyInvocation.MyCommand.Path
if (-not $root) { throw 'Save the script to a .ps1 file, then run it. Do not paste its contents.' }
Set-Location -LiteralPath $root
if (-not (Get-Command docker -ErrorAction SilentlyContinue)) {
    throw 'Docker Desktop CLI missing; install Docker Desktop first.'
}
docker info *> $null
if ($LASTEXITCODE -ne 0) { throw 'Docker Desktop daemon not started.' }
foreach ($folder in @('out','local_drive_sources','.private')) {
    New-Item -Force -ItemType Directory -Path (Join-Path $root $folder) | Out-Null
}
$env:KWTRUST_OUTPUT = '/output/evidence-full-coverage.json'
if ($WithFullVideos) {
    foreach ($file in @('day3-source.avi','day4-source.avi')) {
        if (-not (Test-Path -LiteralPath (Join-Path $root "local_drive_sources\$file"))) {
            throw "Missing original video $file. See README Drive sync instructions."
        }
    }
    $stamp = Get-Date -Format 'yyyyMMdd-HHmmss'
    $env:KWTRUST_OUTPUT = "/output/evidence-replayed-$stamp.json"
    $env:ENABLE_LOCAL_AVI_ANALYSIS = '1'
    docker compose -f compose.yaml -f compose.video.yaml up --build -d
} else {
    $env:ENABLE_LOCAL_AVI_ANALYSIS = '0'
    docker compose -f compose.yaml up --build -d
}
if ($LASTEXITCODE -ne 0) { throw 'Container startup failed. Run docker compose logs --tail 100' }
$ready = $false
for ($attempt = 0; $attempt -lt 180; $attempt++) {
    try {
        $response = Invoke-WebRequest -Uri 'http://127.0.0.1:8767/api/health' -TimeoutSec 3 -UseBasicParsing
        if ($response.StatusCode -eq 200) { $ready = $true; break }
    } catch { if ($attempt % 12 -eq 0) { Write-Host 'Waiting for workstation readiness...' } }
    Start-Sleep -Seconds 2
}
if (-not $ready) {
    docker logs --tail 100 kwtrust-final
    throw 'Workstation did not become ready.'
}
Write-Host 'Unified research workstation ready: http://127.0.0.1:8767'
Start-Process 'http://127.0.0.1:8767/#overview'
