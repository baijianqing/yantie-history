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
- `app`: Streamlit and FastAPI entrypoints.

Future modules such as `media`, `rag`, and `opportunity`
should depend on `core` contracts and `workspace` services instead of reaching
into each other's internals.
