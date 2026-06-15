"""Collectors that turn local work traces into ledger WorkEvents."""

from __future__ import annotations

import subprocess
from datetime import date, datetime, time, timezone
from pathlib import Path

from pydantic import BaseModel, Field, field_validator, model_validator

from metaos.core.schemas import Citation
from metaos.ledger.schemas import WorkEvent, WorkEventSource, WorkEventType


MARKDOWN_EXTENSIONS = (".md", ".markdown")
GIT_RECORD_SEPARATOR = "\x1e"
GIT_FIELD_SEPARATOR = "\x1f"


class CollectionWindow(BaseModel):
    date_from: date
    date_to: date
    related_intent_id: str | None = None

    @field_validator("related_intent_id")
    @classmethod
    def clean_related_intent_id(cls, value: str | None) -> str | None:
        if value is None:
            return None
        return value.strip() or None

    @model_validator(mode="after")
    def validate_date_range(self):
        if self.date_to < self.date_from:
            raise ValueError("date_to cannot be earlier than date_from")
        return self


class GitCommitCollectionPayload(CollectionWindow):
    repo_path: Path


class MarkdownChangeCollectionPayload(CollectionWindow):
    markdown_dir: Path
    extensions: tuple[str, ...] = Field(default=MARKDOWN_EXTENSIONS)

    @field_validator("extensions")
    @classmethod
    def normalize_extensions(cls, values: tuple[str, ...]) -> tuple[str, ...]:
        cleaned = []
        for value in values:
            suffix = value.strip().lower()
            if not suffix:
                raise ValueError("extensions cannot contain blank values")
            cleaned.append(suffix if suffix.startswith(".") else f".{suffix}")
        return tuple(dict.fromkeys(cleaned))


def collect_git_commits(payload: GitCommitCollectionPayload) -> list[WorkEvent]:
    repo_path = payload.repo_path.resolve()
    if not repo_path.exists() or not repo_path.is_dir():
        raise FileNotFoundError(f"Git repository directory not found: {repo_path}")

    start, end = window_bounds(payload.date_from, payload.date_to)
    pretty = f"{GIT_RECORD_SEPARATOR}%H{GIT_FIELD_SEPARATOR}%cI{GIT_FIELD_SEPARATOR}%s{GIT_FIELD_SEPARATOR}%an"
    output = run_git(
        repo_path,
        [
            "log",
            f"--since={start.isoformat()}",
            f"--until={end.isoformat()}",
            "--date=iso-strict",
            "--name-only",
            f"--pretty=format:{pretty}",
        ],
    )
    events: list[WorkEvent] = []
    for record in output.split(GIT_RECORD_SEPARATOR):
        record = record.strip()
        if not record:
            continue
        lines = [line.strip() for line in record.splitlines()]
        header = lines[0]
        fields = header.split(GIT_FIELD_SEPARATOR)
        if len(fields) < 4:
            continue
        commit_hash, committed_at_text, subject, author = fields[:4]
        changed_files = [line for line in lines[1:] if line]
        committed_at = parse_git_datetime(committed_at_text)
        events.append(
            WorkEvent(
                date=committed_at.date(),
                event_type=WorkEventType.build,
                title=subject or commit_hash[:12],
                description=f"Git commit by {author}: {subject or commit_hash[:12]}",
                source=WorkEventSource.git_commit,
                source_ref=commit_hash,
                started_at=committed_at,
                related_intent_id=payload.related_intent_id,
                citations=[
                    Citation(file_path=repo_path / file_path, excerpt=subject or None)
                    for file_path in changed_files
                ],
                metadata={
                    "repo_path": str(repo_path),
                    "commit_hash": commit_hash,
                    "author": author,
                    "changed_files": changed_files,
                },
            )
        )
    return sorted(events, key=lambda event: (event.started_at or datetime.min.replace(tzinfo=timezone.utc), event.source_ref or ""))


def collect_markdown_changes(payload: MarkdownChangeCollectionPayload) -> list[WorkEvent]:
    markdown_dir = payload.markdown_dir.resolve()
    if not markdown_dir.exists() or not markdown_dir.is_dir():
        raise FileNotFoundError(f"Markdown directory not found: {markdown_dir}")

    start, end = window_bounds(payload.date_from, payload.date_to)
    events: list[WorkEvent] = []
    for path in sorted(markdown_dir.rglob("*")):
        if not path.is_file() or path.suffix.lower() not in payload.extensions:
            continue
        modified_at = datetime.fromtimestamp(path.stat().st_mtime, tz=timezone.utc)
        if modified_at < start or modified_at > end:
            continue
        relative_path = path.relative_to(markdown_dir)
        excerpt = read_excerpt(path)
        title = excerpt or path.stem
        events.append(
            WorkEvent(
                date=modified_at.date(),
                event_type=WorkEventType.note,
                title=title[:120],
                description=f"Markdown file changed: {relative_path.as_posix()}",
                source=WorkEventSource.markdown_change,
                source_ref=relative_path.as_posix(),
                started_at=modified_at,
                related_intent_id=payload.related_intent_id,
                citations=[Citation(file_path=path, excerpt=excerpt or None)],
                metadata={
                    "markdown_dir": str(markdown_dir),
                    "relative_path": relative_path.as_posix(),
                    "modified_at": modified_at.isoformat(),
                    "size_bytes": path.stat().st_size,
                },
            )
        )
    return events


def window_bounds(date_from: date, date_to: date) -> tuple[datetime, datetime]:
    return (
        datetime.combine(date_from, time.min, tzinfo=timezone.utc),
        datetime.combine(date_to, time.max, tzinfo=timezone.utc),
    )


def run_git(repo_path: Path, args: list[str]) -> str:
    completed = subprocess.run(
        ["git", "-C", str(repo_path), *args],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
    )
    if completed.returncode != 0:
        raise RuntimeError((completed.stderr or completed.stdout or "git command failed").strip())
    return completed.stdout


def parse_git_datetime(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def read_excerpt(path: Path, limit_chars: int = 240) -> str:
    raw = path.read_bytes()
    for encoding in ("utf-8-sig", "utf-8", "gb18030"):
        try:
            text = raw.decode(encoding)
            break
        except UnicodeDecodeError:
            continue
    else:
        text = raw.decode("utf-8", errors="replace")
    for line in text.splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        if stripped.startswith("#"):
            stripped = stripped.lstrip("#").strip()
        if stripped:
            return stripped[:limit_chars]
    return ""

