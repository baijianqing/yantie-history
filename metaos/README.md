# MetaOS Lite

AI时代创业者的个人研究院。

This package is the stage-0 foundation for parallel module development. Existing
classic-book crawler files stay at repository root for now.

## Module boundaries

- `core`: shared schemas, config, and errors.
- `workspace`: local directories, SQLite, and job state.
- `ingest`: raw file ingestion and source/asset creation.
- `documents`: TXT/Markdown parsing.
- `knowledge`: rule-based category, summary, standard Markdown creation, and
  document chunking for later retrieval.
- `retrieval`: configurable chunk embeddings, ChromaDB indexing, and top-k
  search. Default embeddings use Ollama `bge-m3`; `hash` remains available for
  smoke tests.
- `llm_gateway`: provider boundary for DeepSeek-compatible chat calls.
- `tasks`: Redis/RQ queue boundaries and worker task entrypoints.
- `rag`: single-turn retrieval-augmented answer generation.
- `app`: Streamlit and FastAPI entrypoints.

Future modules such as `media`, `rag`, and `opportunity`
should depend on `core` contracts and `workspace` services instead of reaching
into each other's internals.

## Worker isolation

Use `.venv311` for the main knowledge environment. It owns Chroma access,
indexing, retrieval, and RAG. ChromaDB is version-sensitive, so every process
that touches `library/index/chroma` must use the same environment.
PDF routing and text-page extraction also run here before scanned pages are
delegated to OCR.

```powershell
.\scripts\start-metaos-app.ps1
.\scripts\start-metaos-worker.ps1
```

Use `.venv_ocr` only for OCR. The OCR worker handles images, scanned PDFs, and
scan pages from mixed PDFs. It writes OCR Markdown and submits the result back
to the ingest queue; it must not import Chroma or touch `library/index/chroma`.

```powershell
.\scripts\start-ocr-worker.ps1
```

GPU OCR can run from `.venv_ocr_gpu` after installing `paddlepaddle-gpu`.
Set `OCR_DEVICE` explicitly so each OCR job records whether it used CPU or GPU.
`OCR_MODE=default` keeps the original `PaddleOCR(lang="ch")` behavior; use
`fast` for throughput and `quality` for harder scans.

```powershell
.\scripts\start-ocr-worker.ps1 -Device gpu -Mode fast -RenderZoom 2.0
```

Redis must be running before the app submits background jobs:

```powershell
.\scripts\start-redis.ps1
```

Stop local services with the matching scripts:

```powershell
.\scripts\stop-metaos-worker.ps1
.\scripts\stop-ocr-worker.ps1
.\scripts\stop-metaos-app.ps1
.\scripts\stop-ollama-model.ps1
.\scripts\stop-redis.ps1
```

To stop the MetaOS app and workers in one command:

```powershell
.\scripts\stop-metaos-all.ps1
```

Use optional flags when you also want to release Ollama or Redis:

```powershell
.\scripts\stop-metaos-all.ps1 -IncludeOllamaModel -IncludeRedis
```
