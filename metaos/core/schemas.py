"""Public data contracts for MetaOS Lite modules."""

from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any
from uuid import uuid4

from pydantic import BaseModel, Field


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def new_id(prefix: str) -> str:
    return f"{prefix}_{uuid4().hex}"


class SourceType(str, Enum):
    local_file = "local_file"
    url = "url"
    youtube = "youtube"
    bilibili = "bilibili"
    podcast = "podcast"
    browser = "browser"


class AssetKind(str, Enum):
    document = "document"
    video = "video"
    audio = "audio"
    transcript = "transcript"
    markdown = "markdown"
    export = "export"


class JobType(str, Enum):
    ingest_document = "ingest_document"
    ingest_video = "ingest_video"
    transcribe_audio = "transcribe_audio"
    summarize_knowledge = "summarize_knowledge"
    index_knowledge = "index_knowledge"
    answer_question = "answer_question"
    extract_opportunities = "extract_opportunities"
    sync_github = "sync_github"
    browser_collect = "browser_collect"


class JobStatus(str, Enum):
    pending = "pending"
    running = "running"
    succeeded = "succeeded"
    failed = "failed"
    canceled = "canceled"


class KnowledgeCategory(str, Enum):
    ai = "AI"
    entrepreneurship = "entrepreneurship"
    product = "product"
    technology = "technology"
    investment = "investment"
    philosophy = "philosophy"
    history = "history"
    economics = "economics"
    computer_science = "computer_science"
    mathematics = "mathematics"
    uncategorized = "uncategorized"


class Source(BaseModel):
    id: str = Field(default_factory=lambda: new_id("src"))
    type: SourceType
    uri: str
    title: str | None = None
    platform: str | None = None
    note: str | None = None
    created_at: datetime = Field(default_factory=utc_now)


class Asset(BaseModel):
    id: str = Field(default_factory=lambda: new_id("asset"))
    source_id: str
    kind: AssetKind
    path: Path
    mime_type: str | None = None
    sha256: str | None = None
    size_bytes: int | None = None
    created_at: datetime = Field(default_factory=utc_now)


class Citation(BaseModel):
    source_id: str | None = None
    asset_id: str | None = None
    file_path: Path | None = None
    page: int | None = None
    timestamp_seconds: float | None = None
    excerpt: str | None = None


class TranscriptSegment(BaseModel):
    start_seconds: float
    end_seconds: float | None = None
    text: str


class Transcript(BaseModel):
    id: str = Field(default_factory=lambda: new_id("tr"))
    asset_id: str
    language: str | None = None
    segments: list[TranscriptSegment] = Field(default_factory=list)
    text: str
    created_at: datetime = Field(default_factory=utc_now)


class KnowledgeItem(BaseModel):
    id: str = Field(default_factory=lambda: new_id("ki"))
    title: str
    summary: str | None = None
    category: KnowledgeCategory = KnowledgeCategory.uncategorized
    tags: list[str] = Field(default_factory=list)
    markdown_path: Path | None = None
    citations: list[Citation] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=utc_now)


class Chunk(BaseModel):
    id: str = Field(default_factory=lambda: new_id("chunk"))
    knowledge_item_id: str
    text: str
    heading_path: list[str] = Field(default_factory=list)
    ordinal: int = 0
    char_count: int | None = None
    citation: Citation | None = None
    embedding_id: str | None = None
    created_at: datetime = Field(default_factory=utc_now)


class OpportunityCard(BaseModel):
    id: str = Field(default_factory=lambda: new_id("opp"))
    title: str
    pain_point: str
    target_user: str | None = None
    evidence: list[Citation] = Field(default_factory=list)
    product_idea: str | None = None
    trend_signal: str | None = None
    confidence: float = Field(default=0.5, ge=0, le=1)
    created_at: datetime = Field(default_factory=utc_now)


class Job(BaseModel):
    id: str = Field(default_factory=lambda: new_id("job"))
    type: JobType
    status: JobStatus = JobStatus.pending
    progress: float = Field(default=0, ge=0, le=1)
    message: str | None = None
    error: str | None = None
    payload: dict[str, Any] = Field(default_factory=dict)
    result: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=utc_now)
    updated_at: datetime = Field(default_factory=utc_now)
