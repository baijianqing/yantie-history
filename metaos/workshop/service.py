"""Content workshop asset generation and local render helpers."""

from __future__ import annotations

import json
import subprocess
from datetime import datetime
from pathlib import Path

from metaos.core.schemas import utc_now
from metaos.workshop.schemas import (
    EpisodeReviewStatus,
    EpisodeSpec,
    VideoExport,
    VideoRenderStatus,
    WorkshopAssetBundle,
    assert_episode_can_export,
)


def generate_episode_assets(episode: EpisodeSpec, output_dir: Path) -> WorkshopAssetBundle:
    episode_dir = output_dir / episode.id
    episode_dir.mkdir(parents=True, exist_ok=True)

    script_path = episode_dir / "script.md"
    voiceover_path = episode_dir / "voiceover.txt"
    subtitle_path = episode_dir / "subtitles.srt"
    cards_path = episode_dir / "cards.json"
    remotion_props_path = episode_dir / "remotion_props.json"

    script = build_script(episode)
    voiceover = build_voiceover(episode)
    cards = build_cards(episode)
    remotion_props = {
        "episodeId": episode.id,
        "dailySummaryId": episode.daily_summary_id,
        "title": episode.title,
        "angle": episode.angle,
        "cards": cards,
        "reviewStatus": episode.review_status.value,
    }

    script_path.write_text(script, encoding="utf-8")
    voiceover_path.write_text(voiceover, encoding="utf-8")
    subtitle_path.write_text(build_subtitles(voiceover), encoding="utf-8")
    cards_path.write_text(json.dumps(cards, ensure_ascii=False, indent=2), encoding="utf-8")
    remotion_props_path.write_text(
        json.dumps(remotion_props, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    return WorkshopAssetBundle(
        episode_spec_id=episode.id,
        output_dir=episode_dir,
        script_path=script_path,
        voiceover_path=voiceover_path,
        subtitle_path=subtitle_path,
        cards_path=cards_path,
        remotion_props_path=remotion_props_path,
    )


def review_episode(
    episode: EpisodeSpec,
    *,
    status: EpisodeReviewStatus,
    reviewer_id: str | None = None,
    reviewed_at: datetime | None = None,
    review_notes: str = "",
) -> EpisodeSpec:
    data = episode.model_dump()
    data.update(
        {
            "review_status": status,
            "reviewer_id": reviewer_id,
            "reviewed_at": reviewed_at or utc_now(),
            "review_notes": review_notes,
            "updated_at": utc_now(),
        }
    )
    return EpisodeSpec(**data)


def render_episode_video(
    episode: EpisodeSpec,
    assets: WorkshopAssetBundle,
    output_dir: Path,
    *,
    ffmpeg_binary: str = "ffmpeg",
    final_export: bool = True,
) -> VideoExport:
    output_dir.mkdir(parents=True, exist_ok=True)
    mp4_path = output_dir / f"{episode.id}.mp4"
    base_kwargs = {
        "episode_spec_id": episode.id,
        "script_path": assets.script_path,
        "voiceover_path": assets.voiceover_path,
        "subtitle_path": assets.subtitle_path,
        "cards_path": assets.cards_path,
        "remotion_props_path": assets.remotion_props_path,
        "review_record_id": episode.reviewer_id,
    }

    try:
        if final_export:
            assert_episode_can_export(episode)
        command = [
            ffmpeg_binary,
            "-y",
            "-f",
            "lavfi",
            "-i",
            "color=c=0x111111:s=1280x720:d=1",
            "-f",
            "lavfi",
            "-i",
            "anullsrc=channel_layout=stereo:sample_rate=44100",
            "-shortest",
            "-c:v",
            "libx264",
            "-pix_fmt",
            "yuv420p",
            "-c:a",
            "aac",
            str(mp4_path),
        ]
        completed = subprocess.run(
            command,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            check=False,
        )
        if completed.returncode != 0:
            return failed_export(base_kwargs, completed.stderr or completed.stdout or "ffmpeg failed")
        return VideoExport(
            **base_kwargs,
            mp4_path=mp4_path,
            render_status=VideoRenderStatus.succeeded,
        )
    except (OSError, ValueError) as exc:
        return failed_export(base_kwargs, str(exc))


def failed_export(base_kwargs: dict, error: str) -> VideoExport:
    return VideoExport(
        **base_kwargs,
        render_status=VideoRenderStatus.failed,
        error=error.strip() or "video render failed",
    )


def build_script(episode: EpisodeSpec) -> str:
    sections = [
        f"# {episode.title}",
        "",
        f"Angle: {episode.angle}",
        "",
        format_section("Facts", episode.facts),
        format_section("Judgments", episode.judgments),
        format_section("Reflections", episode.reflections),
        format_section("Actions", episode.actions),
    ]
    return "\n".join(section for section in sections if section is not None).strip() + "\n"


def build_voiceover(episode: EpisodeSpec) -> str:
    lines = [episode.title, episode.angle]
    for label, values in (
        ("Facts", episode.facts),
        ("Judgments", episode.judgments),
        ("Reflections", episode.reflections),
        ("Actions", episode.actions),
    ):
        if values:
            lines.append(f"{label}. " + " ".join(values))
    return "\n".join(lines).strip() + "\n"


def build_subtitles(voiceover: str, seconds_per_line: int = 4) -> str:
    lines = [line.strip() for line in voiceover.splitlines() if line.strip()]
    entries: list[str] = []
    for index, line in enumerate(lines, start=1):
        start = (index - 1) * seconds_per_line
        end = index * seconds_per_line
        entries.append(f"{index}\n{format_srt_time(start)} --> {format_srt_time(end)}\n{line}\n")
    return "\n".join(entries)


def build_cards(episode: EpisodeSpec) -> list[dict[str, str]]:
    cards: list[dict[str, str]] = []
    for card_type, values in (
        ("fact", episode.facts),
        ("judgment", episode.judgments),
        ("reflection", episode.reflections),
        ("action", episode.actions),
    ):
        cards.extend({"type": card_type, "text": value} for value in values)
    return cards


def format_section(title: str, values: list[str]) -> str | None:
    if not values:
        return None
    body = "\n".join(f"- {value}" for value in values)
    return f"## {title}\n\n{body}\n"


def format_srt_time(total_seconds: int) -> str:
    hours, remainder = divmod(total_seconds, 3600)
    minutes, seconds = divmod(remainder, 60)
    return f"{hours:02}:{minutes:02}:{seconds:02},000"
