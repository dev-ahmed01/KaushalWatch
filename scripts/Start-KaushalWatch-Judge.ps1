<#
.SYNOPSIS
  Safe Windows controlled SIH judge-day launcher.
.DESCRIPTION
  -PreflightOnly is read-only.
  -ResetSimulatedState is explicit and guarded against real/non-demo data.
  -CalibratedModel requires a separately installed authoritative detector.
  -RunRehearsal runs a read-only Chromium journey and stops just this command's servers.
  -ProductionWeb starts a source/port-bound, locally built Next production site.
  -BuildProductionWeb prepares that frozen build first (requires build-time fonts).
#>
[CmdletBinding()]
param(
  [switch]$PreflightOnly,
  [switch]$ResetSimulatedState,
  [switch]$CalibratedModel,
  [switch]$RunRehearsal,
  [switch]$ProductionWeb,
  [switch]$BuildProductionWeb,
  [ValidateRange(1024,65535)][int]$ApiPort=8000,
  [ValidateRange(1024,65535)][int]$WebPort=3000
)
$ErrorActionPreference='Stop'
Set-StrictMode -Version Latest
$root=(Resolve-Path (Join-Path $PSScriptRoot '..')).Path
Set-Location $root
if($ApiPort -eq $WebPort){throw 'API and web ports cannot be identical.'}
if($PreflightOnly -and $RunRehearsal){throw '-PreflightOnly and -RunRehearsal cannot be combined.'}
if($BuildProductionWeb -and -not $ProductionWeb){throw '-BuildProductionWeb requires -ProductionWeb.'}
if($BuildProductionWeb -and $PreflightOnly){throw 'Read-only preflight cannot build or alter .next.'}
if($RunRehearsal -and $CalibratedModel){throw 'Controlled rehearsal is the frozen synthetic path; use -CalibratedModel separately.'}
$mode="$env:KAUSHALWATCH_ENV".ToLowerInvariant()
if($mode -and @('development','local','test') -notcontains $mode){
  throw 'Protected environment selected; controlled judge launcher refuses to run.'
}
if("$env:KAUSHALWATCH_STORAGE_BACKEND".ToLowerInvariant() -eq 'postgres'){
  throw 'Judge reset/launcher requires JSON demo storage, not PostgreSQL.'
}
if("$env:KAUSHALWATCH_EVIDENCE_BACKEND".ToLowerInvariant() -eq 's3'){
  throw 'Judge reset/launcher refuses live object evidence storage.'
}
$python=(Get-Command python -ErrorAction Stop).Source
$npmCommand=Get-Command npm.cmd -ErrorAction SilentlyContinue
if(-not $npmCommand){$npmCommand=Get-Command npm -ErrorAction Stop}
$npm=$npmCommand.Source
Write-Host 'KaushalWatch · controlled judge preflight'
& $python (Join-Path $root 'scripts/verify_judge_sources.py')
if($LASTEXITCODE -ne 0){throw 'Procedural replay source checksum mismatch.'}
& $python (Join-Path $root 'scripts/check_release_readiness.py')
if($LASTEXITCODE -ne 0){throw 'Deterministic demo release seed is not valid.'}
if($PreflightOnly){
  if($ProductionWeb){
    & $python (Join-Path $root 'scripts/verify_offline_demo_build.py') --root $root --api-port $ApiPort
    if($LASTEXITCODE -ne 0){throw 'Missing or stale source-bound local production build.'}
  }
  Write-Host 'Read-only preflight passed. No services started and no demo records reset.'
  exit 0
}
# Check ports BEFORE any destructive synthetic reset. Never accidentally
# connect the presentation browser to a stale API or Next process.
& $python (Join-Path $root 'scripts/check_judge_runtime.py') --api-port $ApiPort --web-port $WebPort --check-ports-free
if($LASTEXITCODE -ne 0){throw 'Judge ports are occupied; stop old services rather than accepting stale case data.'}
if($BuildProductionWeb){
  & (Join-Path $root 'scripts/Prepare-KaushalWatch-OfflineBuild.ps1') -ApiPort $ApiPort
}
if($ProductionWeb){
  & $python (Join-Path $root 'scripts/verify_offline_demo_build.py') --root $root --api-port $ApiPort
  if($LASTEXITCODE -ne 0){throw 'Offline build missing, stale, or compiled for a different API port.'}
}
$data=Join-Path $root 'data'
if($ResetSimulatedState){
  if(-not (Test-Path $data)){New-Item -ItemType Directory -Path $data | Out-Null}
  & $python (Join-Path $root 'scripts/judge_reset_guard.py') --data-dir $data
  if($LASTEXITCODE -ne 0){throw 'Unsafe demo reset refused; move real data to an approved backup first.'}
  & $python (Join-Path $root 'scripts/prepare_demo_state.py') --data-dir $data --yes
  if($LASTEXITCODE -ne 0){throw 'Synthetic demo seeding failed.'}
}
if(-not (Test-Path (Join-Path $data 'cases.json'))){
  throw 'No demo state. Use -ResetSimulatedState ONLY if this is a safe demo workspace.'
}
& $python (Join-Path $root 'scripts/judge_reset_guard.py') --data-dir $data
if($LASTEXITCODE -ne 0){throw 'Non-demo state detected; refusing to launch controlled display.'}
if(-not (Test-Path (Join-Path $root 'web/node_modules'))){
  throw 'Web dependencies missing: run npm ci from the web folder before launch.'
}
# Run Next directly under node rather than npm.cmd: process ID belongs
# to the actual web server rather than an intermediary shell wrapper.
$node=(Get-Command node -ErrorAction Stop).Source
$nextCli=Join-Path $root 'web/node_modules/next/dist/bin/next'
if(-not (Test-Path $nextCli)){throw 'Next.js CLI missing: run npm ci inside web.'}
$logRoot=Join-Path ([IO.Path]::GetTempPath()) 'kaushalwatch-judge'
if(-not (Test-Path $logRoot)){New-Item -ItemType Directory -Path $logRoot | Out-Null}
$env:KAUSHALWATCH_ENV='development'
$env:KAUSHALWATCH_STORAGE_BACKEND='json'
$env:KAUSHALWATCH_EVIDENCE_BACKEND='local'
$env:KAUSHALWATCH_REVIEW_AUTH_MODE='demo'
$env:KAUSHALWATCH_EDGE_SYNC_AUTH_MODE='demo'
$env:KAUSHALWATCH_WEB_AUTH_MODE='demo'
$env:NEXT_PUBLIC_KAUSHALWATCH_SECURE_PROXY='false'
$env:NEXT_PUBLIC_API_URL="http://127.0.0.1:$ApiPort"
$env:PYTHONPATH=(Join-Path $root 'backend')
$backendArgs=if($CalibratedModel){
  @('scripts/start_demo_backend.py','--host','127.0.0.1','--port',"$ApiPort")
}else{
  @('-m','uvicorn','app.main:app','--host','127.0.0.1','--port',"$ApiPort")
}
$apiLog=Join-Path $logRoot 'api.stdout.log'
$apiErr=Join-Path $logRoot 'api.stderr.log'
$webLog=Join-Path $logRoot 'web.stdout.log'
$webErr=Join-Path $logRoot 'web.stderr.log'
$api=Start-Process -FilePath $python -ArgumentList $backendArgs -WorkingDirectory $root -PassThru -RedirectStandardOutput $apiLog -RedirectStandardError $apiErr
$web=$null
try{
  # Start-Process joins ArgumentList into one command line on Windows. Quote
  # an installed Next CLI path that may live under a directory with spaces.
  $quotedNextCli='"' + $nextCli + '"'
  $nextMode=if($ProductionWeb){'start'}else{'dev'}
  $web=Start-Process -FilePath $node -ArgumentList @($quotedNextCli,$nextMode,'--hostname','127.0.0.1','--port',"$WebPort") -WorkingDirectory (Join-Path $root 'web') -PassThru -RedirectStandardOutput $webLog -RedirectStandardError $webErr
  # A living PID does not establish startup. Verify real API source cases,
  # a saved evidence pack, PDF bytes and the served judge mission HTML.
  & $python (Join-Path $root 'scripts/check_judge_runtime.py') --api-port $ApiPort --web-port $WebPort --timeout-seconds 75
  if($LASTEXITCODE -ne 0){throw 'Judge runtime failed real HTTP readiness. See temporary service logs.'}
  $api.Refresh()
  $web.Refresh()
  if($api.HasExited -or $web.HasExited){throw 'A verified service exited unexpectedly; inspect temporary judge logs.'}
  Write-Host "API: http://127.0.0.1:$ApiPort"
  Write-Host "Web: http://127.0.0.1:$WebPort/demo/mission"
  Write-Host "Insights: http://127.0.0.1:$WebPort/insights"
  Write-Host "Logs: $logRoot"
  Write-Host 'Videos are procedural; seeded records synthetic. Institutional accuracy remains unqualified.'
  if($ProductionWeb){Write-Host 'Optimized local production web build active; browser font assets are served from localhost.'}
  if($RunRehearsal){
    # Browser tests are read-only, never submit officer review changes.
    # CI runs the same test file against a real Next/FastAPI stack.
    $playwrightCli=Join-Path $root 'web/node_modules/playwright/cli.js'
    if(-not (Test-Path $playwrightCli)){
      throw 'Playwright CLI not installed: run npm ci inside the web folder.'
    }
    $previousE2EBase=$env:E2E_BASE_URL
    $previousApiBase=$env:E2E_API_BASE_URL
    try{
      $env:E2E_BASE_URL="http://127.0.0.1:$WebPort"
      $env:E2E_API_BASE_URL="http://127.0.0.1:$ApiPort"
      Push-Location (Join-Path $root 'web')
      try{
        & $node $playwrightCli test 'e2e/phase15-release-rehearsal.spec.ts' '--project=chromium' '--workers=1' '--reporter=line'
        if($LASTEXITCODE -ne 0){
          throw 'Controlled end-to-end browser rehearsal FAILED. Check Playwright output, browser installation and temporary service logs.'
        }
      }finally{
        Pop-Location
      }
      & $python (Join-Path $root 'scripts/check_judge_runtime.py') --api-port $ApiPort --web-port $WebPort --once
      if($LASTEXITCODE -ne 0){
        throw 'Rehearsal browser passed but final service integrity check FAILED.'
      }
      Write-Host 'REHEARSAL PASSED: actual UI journey, case provenance, source manifest, real PDF and recovery.'
      Write-Host 'This is a local synthetic controlled demonstration, NOT institutional field qualification.'
    }finally{
      $env:E2E_BASE_URL=$previousE2EBase
      $env:E2E_API_BASE_URL=$previousApiBase
      # Always stop only the service processes this invocation created.
      if($web -and -not $web.HasExited){Stop-Process -Id $web.Id -Force}
      if($api -and -not $api.HasExited){Stop-Process -Id $api.Id -Force}
      Write-Host 'Rehearsal services launched by this command have been stopped.'
    }
  }else{
    Write-Host "To stop: Stop-Process -Id $($api.Id),$($web.Id) (only while these exact processes remain active)"
  }
}catch{
  if($web -and -not $web.HasExited){Stop-Process -Id $web.Id -Force}
  if(-not $api.HasExited){Stop-Process -Id $api.Id -Force}
  throw
}
