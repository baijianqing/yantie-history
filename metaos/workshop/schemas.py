"""Pydantic schemas for the MetaOS Alpha content workshop."""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from pathlib import Path

from pydantic import BaseModel, Field, field_validator, model_validator

from metaos.core.schemas import Citation, new_id, utc_now


class EpisodeReviewStatus(str, Enum):
    draft = "draft"
    pending_review = "pending_review"
    approved = "approved"
    changes_requested = "changes_requested"
    rejected = "rejected"


class VideoRenderStatus(str, Enum):
    pending = "pending"
    running = "running"
    succeeded = "succeeded"
    failed = "failed"


def _clean_text(value: str, *, field_name: str) -> str:
    text = value.strip()
    if not text:
        raise ValueError(f"{field_name} cannot be blank")
    return text


def _clean_optional_text(value: str | None) -> str | None:
    if value is None:
        return None
    return value.strip() or None


def _clean_string_list(values: list[str]) -> list[str]:
    cleaned: list[str] = []
    for value in values:
        text = value.strip()
        if not text:
            raise ValueError("list items cannot be blank")
        cleaned.append(text)
    return cleaned


class EpisodeSpec(BaseModel):
    id: str = Field(default_factory=lambda: new_id("episode"))
    daily_summary_id: str
    title: str
    angle: str
    facts: list[str] = Field(default_factory=list)
    judgments: list[str] = Field(default_factory=list)
    reflections: list[str] = Field(default_factory=list)
    actions: list[str] = Field(default_factory=list)
    citations: list[Citation] = Field(default_factory=list)
    review_status: EpisodeReviewStatus = EpisodeReviewStatus.draft
    reviewer_id: str | None = None
    reviewed_at: datetime | None = None
    review_notes: str = ""
    created_at: datetime = Field(default_factory=utc_now)
    updated_at: datetime = Field(default_factory=utc_now)

    @field_validator("daily_summary_id", "title", "angle")
    @classmethod
    def validate_required_text(cls, value: str) -> str:
        return _clean_text(value, field_name="text")

    @field_validator("facts", "judgments", "reflections", "actions")
    @classmethod
    def validate_string_lists(cls, values: list[str]) -> list[str]:
        return _clean_string_list(values)

    @field_validator("reviewer_id")
    @classmethod
    def clean_reviewer_id(cls, value: str | None) -> str | None:
        return _clean_optional_text(value)

    @field_validator("review_notes")
    @classmethod
    def clean_review_notes(cls, value: str) -> str:
        return value.strip()

    @model_validator(mode="after")
    def validate_review_metadata(self):
        if self.updated_at < self.created_at:
            raise ValueError("updated_at cannot be earlier than created_at")
        if self.review_status in terminal_review_statuses():
            if not self.reviewer_id:
                raise ValueError("terminal review status requires reviewer_id")
            if self.reviewed_at is None:
                raise ValueError("terminal review status requires reviewed_at")
        return self

    @property
    def ready_for_final_export(self) -> bool:
        return self.review_status == EpisodeReviewStatus.approved


class WorkshopAssetBundle(BaseModel):
    id: str = Field(default_factory=lambda: new_id("assets"))
    episode_spec_id: str
    output_dir: Path
    script_path: Path
    voiceover_path: Path
    subtitle_path: Path
    cards_path: Path
    remotion_props_path: Path
    created_at: datetime = Field(default_factory=utc_now)

    @field_validator("episode_spec_id")
    @classmethod
    def validate_episode_spec_id(cls, value: str) -> str:
        return _clean_text(value, field_name="episode_spec_id")


class VideoExport(BaseModel):
    id: str = Field(default_factory=lambda: new_id("export"))
    episode_spec_id: str
    script_path: Path
    voiceover_path: Path
    subtitle_path: Path
    cards_path: Path
    remotion_props_path: Path
    mp4_path: Path | None = None
    render_status: VideoRenderStatus = VideoRenderStatus.pending
    review_record_id: str | None = None
    error: str | None = None
    created_at: datetime = Field(default_factory=utc_now)
    updated_at: datetime = Field(default_factory=utc_now)

    @field_validator("episode_spec_id")
    @classmethod
    def validate_export_episode_spec_id(cls, value: str) -> str:
        return _clean_text(value, field_name="episode_spec_id")

    @field_validator("review_record_id", "error")
    @classmethod
    def clean_optional_export_text(cls, value: str | None) -> str | None:
        return _clean_optional_text(value)

    @model_validator(mode="after")
    def validate_export_status(self):
        if self.updated_at < self.created_at:
            raise ValueError("updated_at cannot be earlier than created_at")
        if self.render_status == VideoRenderStatus.succeeded and self.mp4_path is None:
            raise ValueError("succeeded video exports require mp4_path")
        if self.render_status == VideoRenderStatus.failed and not self.error:
            raise ValueError("failed video exports require error")
        return self


def terminal_review_statuses() -> set[EpisodeReviewStatus]:
    return {
        EpisodeReviewStatus.approved,
        EpisodeReviewStatus.changes_requested,
        EpisodeReviewStatus.rejected,
    }


def assert_episode_can_export(episode: EpisodeSpec) -> None:
    if not episode.ready_for_final_export:
        raise ValueError("episode must be approved before final video export")
