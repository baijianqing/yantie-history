[CmdletBinding()]
param(
    [string[]]$Queues = @("ingest", "index", "rag"),
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

Write-Host "Starting MetaOS worker"
Write-Host "Queues: $($Queues -join ', ')"
Write-Host "Embedding: model=$OllamaEmbedModel batch=$OllamaEmbedBatchSize num_gpu=$OllamaEmbedNumGpu chroma_upsert=$ChromaUpsertBatchSize timeout=${OllamaEmbedTimeout}s"
Write-Host "Index jobs: item_timeout=${IndexJobTimeoutSeconds}s rebuild_timeout=${RebuildIndexJobTimeoutSeconds}s"
Write-Host "OCR jobs: timeout=${OcrJobTimeoutSeconds}s"

& $python -m metaos.tasks.worker @Queues
