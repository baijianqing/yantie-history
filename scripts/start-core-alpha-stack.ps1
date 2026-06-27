[CmdletBinding()]
param(
    [int]$ApiPort = 8000,
    [int]$UiPort = 8501,
    [string[]]$Queues = @("ingest", "index", "rag"),
    [switch]$SkipWorkers,
    [switch]$SkipOcrWorker,
    [switch]$RequireOcrWorker,
    [switch]$EnableDeveloperDiagnostics = $true,
    [ValidateSet("cpu", "gpu", "gpu:0", "auto")]
    [string]$OcrDevice = "cpu",
    [ValidateSet("fast", "default", "quality")]
    [string]$OcrMode = "default",
    [double]$OcrRenderZoom = 2.0,
    [int]$OllamaEmbedTimeout = 300,
    [int]$OllamaEmbedBatchSize = 64,
    [string]$OllamaEmbedNumGpu = "0",
    [int]$ChromaUpsertBatchSize = 32,
    [int]$IndexJobTimeoutSeconds = 28800,
    [int]$RebuildIndexJobTimeoutSeconds = 28800,
    [int]$OcrJobTimeoutSeconds = 28800,
    [string]$OllamaBaseUrl = "http://localhost:11434",
    [string]$OllamaEmbedModel = "bge-m3"
)

$ErrorActionPreference = "Stop"

$projectRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
Set-Location $projectRoot

$python = Join-Path $projectRoot ".venv311\Scripts\python.exe"
if (-not (Test-Path $python)) {
    throw "Cannot find .venv311 Python: $python"
}

$env:OLLAMA_BASE_URL = $OllamaBaseUrl
$env:OLLAMA_EMBED_MODEL = $OllamaEmbedModel
$env:OLLAMA_EMBED_TIMEOUT = [string]$OllamaEmbedTimeout
$env:OLLAMA_EMBED_BATCH_SIZE = [string]$OllamaEmbedBatchSize
$env:OLLAMA_EMBED_NUM_GPU = $OllamaEmbedNumGpu
$env:CHROMA_UPSERT_BATCH_SIZE = [string]$ChromaUpsertBatchSize
$env:METAOS_INDEX_JOB_TIMEOUT_SECONDS = [string]$IndexJobTimeoutSeconds
$env:METAOS_REBUILD_INDEX_JOB_TIMEOUT_SECONDS = [string]$RebuildIndexJobTimeoutSeconds
$env:METAOS_OCR_JOB_TIMEOUT_SECONDS = [string]$OcrJobTimeoutSeconds
$env:METAOS_CORE_ALPHA_DEVELOPER_DIAGNOSTICS = if ($EnableDeveloperDiagnostics) { "1" } else { "0" }

Write-Host "Starting MetaOS Core Alpha stack"
Write-Host "Project: $projectRoot"
Write-Host "This script does not start Redis or Ollama."
Write-Host "API: http://localhost:$ApiPort"
Write-Host "UI:  http://localhost:$UiPort"

function Test-PortListening {
    param([int]$Port)
    $connection = Get-NetTCPConnection -LocalPort $Port -State Listen -ErrorAction SilentlyContinue
    return $null -ne $connection
}

function Start-HiddenProcess {
    param(
        [string]$Name,
        [string]$FilePath,
        [string[]]$Arguments
    )
    $process = Start-Process `
        -FilePath $FilePath `
        -ArgumentList $Arguments `
        -WorkingDirectory $projectRoot `
        -WindowStyle Hidden `
        -PassThru
    Write-Host "Started $Name PID $($process.Id)"
    return $process
}

if (Test-PortListening -Port $ApiPort) {
    Write-Host "API port $ApiPort is already listening; skipping API start."
} else {
    Start-HiddenProcess `
        -Name "Core Alpha API" `
        -FilePath $python `
        -Arguments @(
            "-m", "uvicorn",
            "metaos.app.core_alpha_api:create_app",
            "--factory",
            "--host", "127.0.0.1",
            "--port", [string]$ApiPort
        ) | Out-Null
}

if (Test-PortListening -Port $UiPort) {
    Write-Host "UI port $UiPort is already listening; skipping UI start."
} else {
    Start-HiddenProcess `
        -Name "Core Alpha workbench" `
        -FilePath $python `
        -Arguments @(
            "-m", "streamlit",
            "run",
            "metaos\app\core_alpha_workbench.py",
            "--server.port", [string]$UiPort,
            "--server.headless", "true"
        ) | Out-Null
}

if (-not $SkipWorkers) {
    $workerArguments = @("-m", "metaos.tasks.worker") + $Queues
    Start-HiddenProcess `
        -Name "MetaOS worker ($($Queues -join ', '))" `
        -FilePath $python `
        -Arguments $workerArguments | Out-Null
} else {
    Write-Host "Skipping main worker."
}

if (-not $SkipOcrWorker) {
    $resolvedOcrDevice = if ($OcrDevice -eq "gpu") { "gpu:0" } else { $OcrDevice }
    $ocrVenvName = if ($resolvedOcrDevice.StartsWith("gpu")) { ".venv_ocr_gpu" } else { ".venv_ocr" }
    $ocrPython = Join-Path $projectRoot "$ocrVenvName\Scripts\python.exe"
    if (Test-Path $ocrPython) {
        $env:OCR_DEVICE = $resolvedOcrDevice
        $env:OCR_MODE = $OcrMode
        $env:OCR_RENDER_ZOOM = [string]$OcrRenderZoom
        Start-HiddenProcess `
            -Name "MetaOS OCR worker ($resolvedOcrDevice/$OcrMode)" `
            -FilePath $ocrPython `
            -Arguments @("-m", "metaos.tasks.worker", "ocr") | Out-Null
    } elseif ($RequireOcrWorker) {
        throw "Cannot find OCR Python: $ocrPython"
    } else {
        Write-Warning "OCR Python not found: $ocrPython. OCR worker was not started."
    }
} else {
    Write-Host "Skipping OCR worker."
}

Start-Sleep -Seconds 2
Write-Host ""
Write-Host "Status:"
Write-Host "  API port $ApiPort listening: $(Test-PortListening -Port $ApiPort)"
Write-Host "  UI  port $UiPort listening: $(Test-PortListening -Port $UiPort)"
Write-Host ""
Write-Host "If you use PDF/image ingestion, ensure Redis is running and OCR worker started."
