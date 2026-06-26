"""Local Core Alpha ingestion helpers for versioned knowledge foundations."""

from __future__ import annotations

import re
import hashlib
from pathlib import Path

from pydantic import BaseModel, Field

from metaos.core.schemas import (
    Asset,
    AssetKind,
    Chunk,
    Citation,
    KnowledgeCategory,
    KnowledgeItem,
    Source,
    SourceType,
)
from metaos.documents.service import ParsedDocument, extract_title, normalize_text
from metaos.knowledge.service import classify_text, infer_tags, summarize_text
from metaos.knowledge.versioning import (
    DEFAULT_INDEX_VERSION,
    build_versioned_knowledge_foundation,
    sha256_text,
    stable_prefixed_id,
)
from metaos.workspace.catalog import AssetRepository, ChunkRepository, KnowledgeRepository, SourceRepository
from metaos.workspace.paths import WorkspacePaths, ensure_workspace


SUPPORTED_CORE_ALPHA_UPLOAD_EXTENSIONS = {".txt", ".md", ".markdown"}


class CoreAlphaIngestResult(BaseModel):
    knowledge_item_id: str
    knowledge_item_version_id: str
    title: str
    source_id: str
    asset_id: str
    chunk_set_manifest_id: str
    active_chunk_count: int = Field(ge=0)
    active_chunk_set_hash: str
    index_generation_ids: dict[str, str]


def ingest_uploaded_text_document(
    *,
    filename: str,
    content: bytes,
    title: str | None = None,
    paths: WorkspacePaths | None = None,
    parser_version: str = "text_v1",
    chunker_version: str = "v2",
    index_strategy_version: str = DEFAULT_INDEX_VERSION,
) -> CoreAlphaIngestResult:
    """Ingest a local text/Markdown upload into the Core Alpha catalog projection.

    This helper intentionally does not build Chroma or call OCR. It writes a
    fixed source, asset, knowledge item, stable chunks, and version/generation
    metadata so Core Alpha can evaluate retrieval against a reproducible base.
    """

    extension = Path(filename).suffix.lower()
    if extension not in SUPPORTED_CORE_ALPHA_UPLOAD_EXTENSIONS:
        supported = ", ".join(sorted(SUPPORTED_CORE_ALPHA_UPLOAD_EXTENSIONS))
        raise ValueError(f"Core Alpha 入库目前只支持文本/Markdown：{supported}")

    text = normalize_text(_decode_upload(content))
    if not text:
        raise ValueError("上传文件没有可入库文本")

    workspace = paths or ensure_workspace()
    source_uri = f"upload://core-alpha/{filename}"
    source_id = stable_prefixed_id("src", [SourceType.local_file.value, source_uri])
    source = Source(
        id=source_id,
        type=SourceType.local_file,
        uri=source_uri,
        title=title.strip() if title and title.strip() else Path(filename).stem,
        note="Core Alpha versioned foundation upload",
    )

    content_hash = sha256_text(text)
    raw_content_hash = hashlib.sha256(content).hexdigest()
    raw_dir = workspace.raw / "core_alpha_uploads"
    raw_dir.mkdir(parents=True, exist_ok=True)
    asset_path = raw_dir / f"{content_hash[:16]}_{_safe_filename(filename)}"
    asset_path.write_bytes(content)
    asset_id = stable_prefixed_id("asset", [source_id, raw_content_hash, asset_path.name])
    asset = Asset(
        id=asset_id,
        source_id=source.id,
        kind=AssetKind.markdown if extension in {".md", ".markdown"} else AssetKind.document,
        path=asset_path,
        mime_type="text/markdown" if extension in {".md", ".markdown"} else "text/plain",
        sha256=raw_content_hash,
        size_bytes=len(content),
    )

    document = ParsedDocument(
        title=title.strip() if title and title.strip() else extract_title(text, Path(filename).stem),
        text=text,
        source_path=asset_path,
        extension=extension,
    )
    foundation = build_versioned_knowledge_foundation(
        source=source,
        asset=asset,
        document=document,
        parser_version=parser_version,
        chunker_version=chunker_version,
        index_strategy_version=index_strategy_version,
        index_types=("workspace_chunk_metadata",),
    )

    item_id = stable_prefixed_id("ki", [foundation.document.document_version.id])
    category = classify_text(document.title, document.text)
    summary = summarize_text(document.text)
    item = KnowledgeItem(
        id=item_id,
        title=document.title,
        summary=summary,
        category=category,
        tags=infer_tags(document.title, document.text, category),
        citations=[
            Citation(
                source_id=source.id,
                asset_id=asset.id,
                file_path=asset.path,
                excerpt=summary[:160] if summary else None,
            )
        ],
        metadata={
            "source_id": source.id,
            "asset_id": asset.id,
            "source_uri": source.uri,
            "parser": parser_version,
            "chunker": chunker_version,
            "index_version": index_strategy_version,
            "knowledge_item_version_id": foundation.document.document_version.id,
            "content_hash": f"sha256:{foundation.document.document_version.content_sha256}",
            "structure_hash": f"sha256:{foundation.document.document_version.structure_sha256}",
            "chunk_set_manifest": foundation.chunk_set.model_dump(mode="json"),
            "index_generations": [
                generation.model_dump(mode="json") for generation in foundation.index_generations
            ],
        },
    )

    SourceRepository(workspace.database).add(source)
    AssetRepository(workspace.database).add(asset)
    KnowledgeRepository(workspace.database).add(item)
    ChunkRepository(workspace.database).add_many(
        [
            Chunk(
                id=stable_prefixed_id(
                    "chunk",
                    [
                        foundation.document.document_version.id,
                        stable_chunk.id,
                    ],
                ),
                knowledge_item_id=item.id,
                text=stable_chunk.text,
                heading_path=stable_chunk.heading_path,
                ordinal=stable_chunk.ordinal,
                char_count=stable_chunk.char_count,
                citation=stable_chunk.citation,
                embedding_id=None,
            )
            for stable_chunk in foundation.document.chunks
        ]
    )
    return CoreAlphaIngestResult(
        knowledge_item_id=item.id,
        knowledge_item_version_id=foundation.document.document_version.id,
        title=item.title,
        source_id=source.id,
        asset_id=asset.id,
        chunk_set_manifest_id=foundation.chunk_set.id,
        active_chunk_count=foundation.chunk_set.active_chunk_count,
        active_chunk_set_hash=foundation.chunk_set.active_chunk_set_hash,
        index_generation_ids=foundation.current_index_generation_ids,
    )


def _decode_upload(content: bytes) -> str:
    for encoding in ("utf-8-sig", "utf-8", "gb18030"):
        try:
            return content.decode(encoding)
        except UnicodeDecodeError:
            continue
    return content.decode("utf-8", errors="replace")


def _safe_filename(filename: str) -> str:
    safe = re.sub(r'[<>:"/\\|?*\x00-\x1f]', "_", Path(filename).name).strip()
    return safe or "upload.txt"


__all__ = [
    "CoreAlphaIngestResult",
    "SUPPORTED_CORE_ALPHA_UPLOAD_EXTENSIONS",
    "ingest_uploaded_text_document",
]
