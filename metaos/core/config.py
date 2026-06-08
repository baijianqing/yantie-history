"""Configuration helpers for the local MetaOS Lite runtime."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[2]


@dataclass(frozen=True)
class Settings:
    project_root: Path
    library_dir: Path
    database_path: Path
    deepseek_api_key: str | None
    deepseek_base_url: str
    deepseek_model: str
    embedding_provider: str
    ollama_base_url: str
    ollama_embed_model: str
    ollama_embed_timeout: float
    ollama_embed_batch_size: int
    chroma_upsert_batch_size: int


def get_settings() -> Settings:
    project_root = Path(os.getenv("METAOS_PROJECT_ROOT", PROJECT_ROOT)).resolve()
    library_dir = Path(os.getenv("METAOS_LIBRARY_DIR", project_root / "library")).resolve()
    database_path = Path(
        os.getenv("METAOS_DATABASE_PATH", library_dir / "metaos.sqlite3")
    ).resolve()
    return Settings(
        project_root=project_root,
        library_dir=library_dir,
        database_path=database_path,
        deepseek_api_key=os.getenv("DEEPSEEK_API_KEY"),
        deepseek_base_url=os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com"),
        deepseek_model=os.getenv("DEEPSEEK_MODEL", "deepseek-chat"),
        embedding_provider=os.getenv("EMBEDDING_PROVIDER", "ollama"),
        ollama_base_url=os.getenv("OLLAMA_BASE_URL", "http://localhost:11434"),
        ollama_embed_model=os.getenv("OLLAMA_EMBED_MODEL", "bge-m3"),
        ollama_embed_timeout=float(os.getenv("OLLAMA_EMBED_TIMEOUT", "300")),
        ollama_embed_batch_size=int(os.getenv("OLLAMA_EMBED_BATCH_SIZE", "8")),
        chroma_upsert_batch_size=int(os.getenv("CHROMA_UPSERT_BATCH_SIZE", "16")),
    )
