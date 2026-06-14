[CmdletBinding(SupportsShouldProcess = $true)]
param(
    [switch]$IncludeRedis,
    [switch]$IncludeOllamaModel,
    [string]$OllamaModel = "bge-m3"
)

$ErrorActionPreference = "Stop"

$scriptRoot = $PSScriptRoot

& (Join-Path $scriptRoot "stop-metaos-worker.ps1")
& (Join-Path $scriptRoot "stop-ocr-worker.ps1")
& (Join-Path $scriptRoot "stop-metaos-app.ps1")

if ($IncludeOllamaModel) {
    & (Join-Path $scriptRoot "stop-ollama-model.ps1") -Model $OllamaModel
}

if ($IncludeRedis) {
    & (Join-Path $scriptRoot "stop-redis.ps1")
}
