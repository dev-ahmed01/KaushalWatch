$ErrorActionPreference='Stop'
Set-Location -LiteralPath (Split-Path -Parent $MyInvocation.MyCommand.Path)
docker compose -f compose.yaml down
