[CmdletBinding()]
param(
    [string]$Model = "bge-m3"
)

$ErrorActionPreference = "Stop"

if (-not (Get-Command ollama -ErrorAction SilentlyContinue)) {
    throw "Cannot find ollama on PATH."
}

Write-Host "Stopping Ollama model: $Model"
& ollama stop $Model
