"""Stable document and chunk versioning contracts for MetaOS Alpha."""

from __future__ import annotations

import hashlib
import json
from datetime import datetime

from pydantic import BaseModel, Field, field_validator

from metaos.core.schemas import Asset, Citation, Source, utc_now
from metaos.documents.service import ParsedDocument
from metaos.knowledge.chunking import (
    DEFAULT_CHUNKER_VERSION,
    ChunkerVersion,
    build_chunks,
    estimate_tokens,
)


DOCUMENT_STANDARD_VERSION = "document_standard_v1"
STABLE_CHUNK_ID_VERSION = "stable_chunk_id_v1"
DEFAULT_INDEX_VERSION = "index_v1"


class DocumentVersion(BaseModel):
    id: str
    stable_id: str
    source_stable_id: str
    source_id: str
    asset_id: str
    version: str
    content_sha256: str
    structure_sha256: str
    title: str
    language: str | None = None
    parser_version: str = "text_v1"
    chunker_version: str = DEFAULT_CHUNKER_VERSION
    index_version: str = DEFAULT_INDEX_VERSION
    created_at: datetime = Field(default_factory=utc_now)

    @field_validator(
        "id",
        "stable_id",
        "source_stable_id",
        "source_id",
        "asset_id",
        "version",
        "content_sha256",
        "structure_sha256",
        "title",
        "parser_version",
        "chunker_version",
        "index_version",
    )
    @classmethod
    def validate_required_text(cls, value: str) -> str:
        text = value.strip()
        if not text:
            raise ValueError("field cannot be blank")
        return text


class StableChunk(BaseModel):
    id: str
    stable_id: str
    document_version_id: str
    document_stable_id: str
    source_id: str
    asset_id: str
    ordinal: int = Field(ge=1)
    heading_path: list[str] = Field(default_factory=list)
    text: str
    char_count: int = Field(ge=0)
    token_count: int = Field(ge=0)
    parent_chunk_id: str | None = None
    previous_chunk_id: str | None = None
    next_chunk_id: str | None = None
    chunker_version: str = DEFAULT_CHUNKER_VERSION
    index_version: str = DEFAULT_INDEX_VERSION
    section_path: list[str] = Field(default_factory=list)
    position: int = Field(ge=0)
    content_sha256: str
    citation: Citation | None = None
    created_at: datetime = Field(default_factory=utc_now)

    @field_validator(
        "id",
        "stable_id",
        "document_version_id",
        "document_stable_id",
        "source_id",
        "asset_id",
        "text",
        "chunker_version",
        "index_version",
        "content_sha256",
    )
    @classmethod
    def validate_required_text(cls, value: str) -> str:
        text = value.strip()
        if not text:
            raise ValueError("field cannot be blank")
        return text


class StandardizedDocument(BaseModel):
    document_version: DocumentVersion
    chunks: list[StableChunk] = Field(default_factory=list)


def standardize_document(
    *,
    source: Source,
    asset: Asset,
    document: ParsedDocument,
    parser_version: str = "text_v1",
    chunker_version: ChunkerVersion = DEFAULT_CHUNKER_VERSION,
    index_version: str = DEFAULT_INDEX_VERSION,
) -> StandardizedDocument:
    source_stable_id = stable_source_id(source)
    document_stable_id = stable_document_id(source_stable_id, document)
    content_sha = sha256_text(normalize_for_hash(document.text))
    structure_sha = sha256_json(
        {
            "title": document.title.strip(),
            "extension": document.extension.lower(),
            "headings": heading_fingerprint(document.text),
        }
    )
    document_version = DocumentVersion(
        id=stable_prefixed_id(
            "docv",
            [
                document_stable_id,
                content_sha,
                structure_sha,
                parser_version,
                chunker_version,
                index_version,
            ],
        ),
        stable_id=document_stable_id,
        source_stable_id=source_stable_id,
        source_id=source.id,
        asset_id=asset.id,
        version=DOCUMENT_STANDARD_VERSION,
        content_sha256=content_sha,
        structure_sha256=structure_sha,
        title=document.title,
        parser_version=parser_version,
        chunker_version=chunker_version,
        index_version=index_version,
    )
    core_chunks = build_chunks(
        knowledge_item_id=document_stable_id,
        source=source,
        asset=asset,
        document=document,
        version=chunker_version,
    )
    stable_chunks: list[StableChunk] = []
    for chunk_index, chunk in enumerate(core_chunks):
        chunk_id = stable_chunk_id(
            document_stable_id=document_stable_id,
            heading_path=chunk.heading_path,
            text=chunk.text,
            occurrence=occurrence_index(core_chunks, chunk_index),
            chunker_version=chunker_version,
            index_version=index_version,
        )
        stable_chunks.append(
            StableChunk(
                id=chunk_id,
                stable_id=chunk_id,
                document_version_id=document_version.id,
                document_stable_id=document_stable_id,
                source_id=source.id,
                asset_id=asset.id,
                ordinal=chunk.ordinal,
                heading_path=chunk.heading_path,
                text=chunk.text,
                char_count=chunk.char_count or len(chunk.text),
                token_count=estimate_tokens(chunk.text),
                parent_chunk_id=parent_heading_id(document_stable_id, chunk.heading_path),
                chunker_version=chunker_version,
                index_version=index_version,
                section_path=chunk.heading_path,
                position=chunk.ordinal - 1,
                content_sha256=sha256_text(normalize_for_hash(chunk.text)),
                citation=chunk.citation,
            )
        )
    chunks = assign_stable_chunk_links(stable_chunks)
    return StandardizedDocument(document_version=document_version, chunks=chunks)


def assign_stable_chunk_links(chunks: list[StableChunk]) -> list[StableChunk]:
    linked: list[StableChunk] = []
    for index, chunk in enumerate(chunks):
        previous_id = chunks[index - 1].id if index > 0 else None
        next_id = chunks[index + 1].id if index < len(chunks) - 1 else None
        linked.append(
            chunk.model_copy(
                update={
                    "previous_chunk_id": previous_id,
                    "next_chunk_id": next_id,
                }
            )
        )
    return linked


def stable_source_id(source: Source) -> str:
    return stable_prefixed_id("srcstable", [source.type.value, normalize_for_hash(source.uri)])


def stable_document_id(source_stable_id: str, document: ParsedDocument) -> str:
    return stable_prefixed_id(
        "doc",
        [
            source_stable_id,
            normalize_for_hash(document.title),
            document.extension.lower(),
        ],
    )


def stable_chunk_id(
    *,
    document_stable_id: str,
    heading_path: list[str],
    text: str,
    occurrence: int,
    chunker_version: str,
    index_version: str,
) -> str:
    return stable_prefixed_id(
        "chunk",
        [
            STABLE_CHUNK_ID_VERSION,
            document_stable_id,
            json.dumps(heading_path, ensure_ascii=False),
            normalize_for_hash(text),
            str(occurrence),
            chunker_version,
            index_version,
        ],
    )


def parent_heading_id(document_stable_id: str, heading_path: list[str]) -> str | None:
    if len(heading_path) <= 1:
        return None
    return stable_prefixed_id(
        "heading",
        [
            document_stable_id,
            json.dumps(heading_path[:-1], ensure_ascii=False),
        ],
    )


def occurrence_index(chunks, chunk_index: int) -> int:
    target = chunks[chunk_index]
    occurrence = 0
    for candidate in chunks[: chunk_index + 1]:
        if candidate.heading_path == target.heading_path and candidate.text == target.text:
            occurrence += 1
    return occurrence


def heading_fingerprint(text: str) -> list[str]:
    headings: list[str] = []
    for line in text.splitlines():
        stripped = line.strip()
        if stripped.startswith("#"):
            heading = stripped.lstrip("#").strip()
            if heading:
                headings.append(heading)
    return headings


def stable_prefixed_id(prefix: str, parts: list[str]) -> str:
    return f"{prefix}_{sha256_json(parts)[:24]}"


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def sha256_json(value) -> str:
    payload = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return sha256_text(payload)


def normalize_for_hash(text: str) -> str:
    normalized = text.replace("\r\n", "\n").replace("\r", "\n")
    return "\n".join(line.rstrip() for line in normalized.splitlines()).strip()
