[CmdletBinding()]
param(
    [int]$Port = 8501,
    [int]$OllamaEmbedTimeout = 300,
    [int]$OllamaEmbedBatchSize = 64,
    [string]$OllamaEmbedNumGpu = "0",
    [int]$ChromaUpsertBatchSize = 32,
    [int]$IndexJobTimeoutSeconds = 28800,
    [int]$RebuildIndexJobTimeoutSeconds = 28800,
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

Write-Host "Starting MetaOS Streamlit app"
Write-Host "URL: http://localhost:$Port"
Write-Host "Embedding: model=$OllamaEmbedModel batch=$OllamaEmbedBatchSize num_gpu=$OllamaEmbedNumGpu chroma_upsert=$ChromaUpsertBatchSize timeout=${OllamaEmbedTimeout}s"
Write-Host "Index jobs: item_timeout=${IndexJobTimeoutSeconds}s rebuild_timeout=${RebuildIndexJobTimeoutSeconds}s"

& $python -m metaos.app.run_streamlit run .\metaos\app\streamlit_app.py --server.port $Port
