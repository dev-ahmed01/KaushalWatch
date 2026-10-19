# Windows submission launcher: one command, no private media uploads.
param([switch]$ResetDemo)
$ErrorActionPreference="Stop"
$root=Split-Path -Parent $PSCommandPath
Set-Location $root
if (-not (Get-Command npm.cmd -ErrorAction SilentlyContinue)) { throw "Install Node.js first." }
$py=Join-Path $root ".venv\Scripts\python.exe"
if (-not (Test-Path $py)) {
    if (Get-Command py -ErrorAction SilentlyContinue) { & py -3.12 -m venv ".venv" }
    elseif (Get-Command python -ErrorAction SilentlyContinue) { & python -m venv ".venv" }
    else { throw "Install Python 3.12 first." }
}
if (-not (Test-Path $py)) { throw "Failed to create Python environment." }
& $py -m pip install --disable-pip-version-check -r "backend\requirements.txt"
if ($LASTEXITCODE -ne 0) { throw "Backend installation failed." }
$env:KAUSHALWATCH_ENV="development"
$env:KAUSHALWATCH_STORAGE_BACKEND="json"
$env:KAUSHALWATCH_EVIDENCE_BACKEND="local"
$env:KAUSHALWATCH_REVIEW_AUTH_MODE="demo"
$env:NEXT_PUBLIC_KAUSHALWATCH_SECURE_PROXY="false"
if ($ResetDemo -or -not (Test-Path (Join-Path $root "data\cases.json"))) {
    & $py "scripts\prepare_demo_state.py" --yes
    if ($LASTEXITCODE -ne 0) { throw "Demo state could not be prepared." }
}
$web=Join-Path $root "web"
if (-not (Test-Path (Join-Path $web "node_modules"))) {
    Push-Location $web
    try { & npm.cmd ci; if ($LASTEXITCODE -ne 0) { throw "Web install failed." } }
    finally { Pop-Location }
}
foreach ($stem in @("training-bay","workshop-floor","east-corridor")) {
    if (-not (Test-Path (Join-Path $web ("public\camera-trust\"+$stem+".mp4")))) {
        throw "Bundled camera recording missing: $stem"
    }
}
$api="& '$py' -m uvicorn app.main:app --app-dir '$root\backend' --host 127.0.0.1 --port 8000"
$site="Set-Location '$web'; npm.cmd run dev"
Start-Process powershell.exe -WorkingDirectory $root -ArgumentList @("-NoExit","-Command",$api)
Start-Process powershell.exe -WorkingDirectory $web -ArgumentList @("-NoExit","-Command",$site)
Write-Host "Camera Trust: http://localhost:3000/centres/DEMO-KA-104/camera-trust"
Start-Process "http://localhost:3000/centres/DEMO-KA-104/camera-trust"
