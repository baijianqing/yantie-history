"""Shared event names for future async workflows."""

from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field

from metaos.core.schemas import new_id


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class EventType(str, Enum):
    source_submitted = "SourceSubmitted"
    asset_stored = "AssetStored"
    transcript_ready = "TranscriptReady"
    document_parsed = "DocumentParsed"
    knowledge_item_created = "KnowledgeItemCreated"
    chunks_indexed = "ChunksIndexed"
    question_answered = "QuestionAnswered"
    opportunity_detected = "OpportunityDetected"
    export_completed = "ExportCompleted"
    job_failed = "JobFailed"


class DomainEvent(BaseModel):
    id: str = Field(default_factory=lambda: new_id("evt"))
    type: EventType
    payload: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=utc_now)
