[CmdletBinding()]
param(
    [string]$RedisCommand = "redis-server"
)

$ErrorActionPreference = "Stop"

$projectRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
Set-Location $projectRoot

if (-not (Get-Command $RedisCommand -ErrorAction SilentlyContinue)) {
    throw "Cannot find redis-server. Make sure Redis is installed and available on PATH."
}

Write-Host "Starting Redis from $projectRoot"
& $RedisCommand
