[CmdletBinding()]
param(
    [ValidateSet("cpu", "gpu", "gpu:0", "auto")]
    [string]$Device = "cpu",
    [ValidateSet("fast", "default", "quality")]
    [string]$Mode = "default",
    [double]$RenderZoom = 2.0
)

$ErrorActionPreference = "Stop"

$projectRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
Set-Location $projectRoot

$resolvedDevice = if ($Device -eq "gpu") { "gpu:0" } else { $Device }
$venvName = if ($resolvedDevice.StartsWith("gpu")) { ".venv_ocr_gpu" } else { ".venv_ocr" }
$python = Join-Path $projectRoot "$venvName\Scripts\python.exe"
if (-not (Test-Path $python)) {
    throw "Cannot find OCR Python: $python"
}

$env:OCR_DEVICE = $resolvedDevice
$env:OCR_MODE = $Mode
$env:OCR_RENDER_ZOOM = [string]$RenderZoom

Write-Host "Starting MetaOS OCR worker"
Write-Host "Environment: $venvName"
Write-Host "OCR: device=$resolvedDevice mode=$Mode render_zoom=$RenderZoom"

& $python -m metaos.tasks.worker ocr
