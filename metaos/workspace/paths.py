"""Local workspace directory management."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path

from metaos.core.config import get_settings


LIBRARY_SUBDIRS = (
    "raw",
    "audio",
    "transcripts",
    "markdown",
    "index",
    "exports",
)


@dataclass(frozen=True)
class WorkspacePaths:
    root: Path
    library: Path
    raw: Path
    audio: Path
    transcripts: Path
    markdown: Path
    index: Path
    exports: Path
    database: Path

    def as_jsonable(self) -> dict[str, str]:
        return {key: str(value) for key, value in asdict(self).items()}


def get_workspace_paths(library_dir: Path | None = None) -> WorkspacePaths:
    settings = get_settings()
    library = (library_dir or settings.library_dir).resolve()
    return WorkspacePaths(
        root=settings.project_root,
        library=library,
        raw=library / "raw",
        audio=library / "audio",
        transcripts=library / "transcripts",
        markdown=library / "markdown",
        index=library / "index",
        exports=library / "exports",
        database=settings.database_path if library_dir is None else library / "metaos.sqlite3",
    )


def ensure_workspace(library_dir: Path | None = None) -> WorkspacePaths:
    paths = get_workspace_paths(library_dir)
    paths.library.mkdir(parents=True, exist_ok=True)
    for subdir in LIBRARY_SUBDIRS:
        (paths.library / subdir).mkdir(parents=True, exist_ok=True)
    paths.database.parent.mkdir(parents=True, exist_ok=True)
    return paths


def main() -> None:
    paths = ensure_workspace()
    print(json.dumps(paths.as_jsonable(), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
