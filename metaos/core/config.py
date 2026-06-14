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
    deepseek_cny_per_usd: float | None
    embedding_provider: str
    ollama_base_url: str
    ollama_embed_model: str
    ollama_embed_timeout: float
    ollama_embed_batch_size: int
    ollama_embed_num_gpu: int | None
    chroma_upsert_batch_size: int
    chroma_required_version: str
    index_job_timeout_seconds: int
    rebuild_index_job_timeout_seconds: int
    redis_url: str
    ocr_device: str
    ocr_mode: str
    ocr_render_zoom: float


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
        deepseek_model=os.getenv("DEEPSEEK_MODEL", "deepseek-v4-flash"),
        deepseek_cny_per_usd=optional_float_env("DEEPSEEK_CNY_PER_USD"),
        embedding_provider=os.getenv("EMBEDDING_PROVIDER", "ollama"),
        ollama_base_url=os.getenv("OLLAMA_BASE_URL", "http://localhost:11434"),
        ollama_embed_model=os.getenv("OLLAMA_EMBED_MODEL", "bge-m3"),
        ollama_embed_timeout=float(os.getenv("OLLAMA_EMBED_TIMEOUT", "300")),
        ollama_embed_batch_size=int(os.getenv("OLLAMA_EMBED_BATCH_SIZE", "64")),
        ollama_embed_num_gpu=optional_int_env("OLLAMA_EMBED_NUM_GPU", "0"),
        chroma_upsert_batch_size=int(os.getenv("CHROMA_UPSERT_BATCH_SIZE", "32")),
        chroma_required_version=os.getenv("CHROMA_REQUIRED_VERSION", "0.4.24"),
        index_job_timeout_seconds=int(os.getenv("METAOS_INDEX_JOB_TIMEOUT_SECONDS", "28800")),
        rebuild_index_job_timeout_seconds=int(
            os.getenv(
                "METAOS_REBUILD_INDEX_JOB_TIMEOUT_SECONDS",
                os.getenv("METAOS_INDEX_JOB_TIMEOUT_SECONDS", "28800"),
            )
        ),
        redis_url=os.getenv("REDIS_URL", "redis://localhost:6379/0"),
        ocr_device=os.getenv("OCR_DEVICE", "auto"),
        ocr_mode=os.getenv("OCR_MODE", "default"),
        ocr_render_zoom=float(os.getenv("OCR_RENDER_ZOOM", "2.0")),
    )


def optional_int_env(name: str, default: str) -> int | None:
    value = os.getenv(name, default).strip().lower()
    if value in {"", "auto", "none", "null"}:
        return None
    return int(value)


def optional_float_env(name: str, default: str = "") -> float | None:
    value = os.getenv(name, default).strip().lower()
    if value in {"", "auto", "none", "null"}:
        return None
    return float(value)
