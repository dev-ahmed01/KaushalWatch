<#
.SYNOPSIS
  Build the controlled Next.js production site while online, then stage a
  commit/API/source-bound receipt for offline localhost judge rehearsal.
.DESCRIPTION
  No case resets, camera downloads, officer writes or institutional approvals.
  Fonts are self-hosted by Next during the BUILD, not fetched by the browser.
#>
[CmdletBinding()]
param([ValidateRange(1024,65535)][int]$ApiPort=8000)
$ErrorActionPreference='Stop'
Set-StrictMode -Version Latest
$root=(Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$web=Join-Path $root 'web'
if("$env:KAUSHALWATCH_ENV" -and @('development','local','test') -notcontains "$env:KAUSHALWATCH_ENV".ToLowerInvariant()){
  throw 'Protected officer deployment cannot prepare a controlled demo build.'
}
if("$env:KAUSHALWATCH_STORAGE_BACKEND".ToLowerInvariant() -eq 'postgres' -or
   "$env:KAUSHALWATCH_EVIDENCE_BACKEND".ToLowerInvariant() -eq 's3'){
  throw 'Cannot prepare a controlled demo from live PostgreSQL/S3 configuration.'
}
$python=(Get-Command python -ErrorAction Stop).Source
$git=(Get-Command git -ErrorAction Stop).Source
$node=(Get-Command node -ErrorAction Stop).Source
$npmCommand=Get-Command npm.cmd -ErrorAction SilentlyContinue
if(-not $npmCommand){$npmCommand=Get-Command npm -ErrorAction Stop}
$npm=$npmCommand.Source
if(-not (Test-Path (Join-Path $web 'node_modules/next'))){
  throw 'Install pinned web dependencies first: cd web; npm ci'
}
& $python (Join-Path $root 'scripts/verify_judge_sources.py')
if($LASTEXITCODE -ne 0){throw 'Refusing to build with altered procedural camera sources.'}
& $python (Join-Path $root 'scripts/check_release_readiness.py')
if($LASTEXITCODE -ne 0){throw 'Refusing to build with invalid controlled release assets.'}
$commit=(& $git -C $root rev-parse HEAD).Trim()
if($LASTEXITCODE -ne 0 -or $commit -notmatch '^[a-f0-9]{40}$'){
  throw 'No exact Git source commit.'
}
$dirty=@(& $git -C $root status --porcelain --untracked-files=no)
if($LASTEXITCODE -ne 0 -or @($dirty | Where-Object {$_ -and $_.Trim()}).Count -ne 0){
  throw 'Checkout has uncommitted tracked changes; a frozen demo build needs a clean checkout.'
}
$buildDir=Join-Path $web '.next'
$receipt=Join-Path $buildDir 'kw-offline-demo-build.json'
# An unsuccessful rebuild must NOT leave a green receipt from an old build.
if(Test-Path $receipt){Remove-Item -LiteralPath $receipt -Force}
$previousApi=$env:NEXT_PUBLIC_API_URL
$previousProxy=$env:NEXT_PUBLIC_KAUSHALWATCH_SECURE_PROXY
try{
  $env:NEXT_PUBLIC_API_URL="http://127.0.0.1:$ApiPort"
  $env:NEXT_PUBLIC_KAUSHALWATCH_SECURE_PROXY='false'
  Push-Location $web
  try{
    & $npm run build
    if($LASTEXITCODE -ne 0){throw 'Next.js branded release build failed; internet may be required to fetch fonts at BUILD time.'}
  }finally{Pop-Location}
  $buildIdPath=Join-Path $buildDir 'BUILD_ID'
  if(-not(Test-Path $buildIdPath)){throw 'No successful Next.js production build identity.'}
  $buildId=(Get-Content $buildIdPath -Raw).Trim()
  if($buildId -notmatch '^[A-Za-z0-9_-]{8,200}$'){throw 'Malformed local Next.js build identity.'}
  $manifest=Join-Path $web 'public/camera-trust/manifest.json'
  $hash=(Get-FileHash -LiteralPath $manifest -Algorithm SHA256).Hash.ToLowerInvariant()
  $record=[ordered]@{
    schema='KW_LOCAL_OFFLINE_NEXT_BUILD_V1'
    mode='CONTROLLED_LOCAL_PROCEDURAL_DEMO_ONLY'
    commit=$commit
    api_origin="http://127.0.0.1:$ApiPort"
    next_build_id=$buildId
    source_manifest_sha256=$hash
    runtime_font_requests_external=$false
    protected_officer_mode_enabled=$false
  }
  $text=ConvertTo-Json -InputObject $record -Compress
  [IO.File]::WriteAllText($receipt,$text,[Text.UTF8Encoding]::new($false))
  & $python (Join-Path $root 'scripts/verify_offline_demo_build.py') --root $root --api-port $ApiPort
  if($LASTEXITCODE -ne 0){throw 'Fresh build receipt failed source/port verification.'}
  Write-Host "OFFLINE BUILD READY · source $commit · API http://127.0.0.1:$ApiPort"
  Write-Host 'No browser font-CDN requests required. Launch with -ProductionWeb.'
}finally{
  $env:NEXT_PUBLIC_API_URL=$previousApi
  $env:NEXT_PUBLIC_KAUSHALWATCH_SECURE_PROXY=$previousProxy
}
