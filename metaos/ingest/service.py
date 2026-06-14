"""Raw file ingestion for MetaOS Lite."""

from __future__ import annotations

import hashlib
import re
import shutil
from pathlib import Path

from metaos.core.schemas import Asset, AssetKind, Source, SourceType
from metaos.workspace.catalog import AssetRepository, SourceRepository
from metaos.workspace.paths import WorkspacePaths, ensure_workspace


DOCUMENT_MIME_TYPES = {
    ".md": "text/markdown",
    ".markdown": "text/markdown",
    ".txt": "text/plain",
    ".pdf": "application/pdf",
    ".png": "image/png",
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".bmp": "image/bmp",
    ".tif": "image/tiff",
    ".tiff": "image/tiff",
    ".webp": "image/webp",
}


def sha256_bytes(content: bytes) -> str:
    return hashlib.sha256(content).hexdigest()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as file:
        for chunk in iter(lambda: file.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def safe_filename(filename: str) -> str:
    name = Path(filename).name.strip() or "untitled.txt"
    name = re.sub(r'[<>:"/\\|?*\x00-\x1f]', "_", name)
    return name[:160]


def raw_path_for(filename: str, digest: str, paths: WorkspacePaths) -> Path:
    return paths.raw / f"{digest[:12]}_{safe_filename(filename)}"


class IngestService:
    def __init__(self, paths: WorkspacePaths | None = None):
        self.paths = paths or ensure_workspace()
        self.sources = SourceRepository(self.paths.database)
        self.assets = AssetRepository(self.paths.database)

    def add_bytes(
        self,
        *,
        filename: str,
        content: bytes,
        title: str | None = None,
        note: str | None = None,
    ) -> tuple[Source, Asset]:
        digest = sha256_bytes(content)
        destination = raw_path_for(filename, digest, self.paths)
        if not destination.exists():
            destination.write_bytes(content)
        source = Source(
            type=SourceType.local_file,
            uri=f"upload://{safe_filename(filename)}",
            title=title or Path(filename).stem,
            note=note,
        )
        asset = Asset(
            source_id=source.id,
            kind=AssetKind.document,
            path=destination,
            mime_type=DOCUMENT_MIME_TYPES.get(destination.suffix.lower()),
            sha256=digest,
            size_bytes=len(content),
        )
        self.sources.add(source)
        self.assets.add(asset)
        return source, asset

    def add_local_file(self, path: Path, *, note: str | None = None) -> tuple[Source, Asset]:
        source_path = path.resolve()
        digest = sha256_file(source_path)
        destination = raw_path_for(source_path.name, digest, self.paths)
        if not destination.exists():
            shutil.copy2(source_path, destination)
        source = Source(
            type=SourceType.local_file,
            uri=str(source_path),
            title=source_path.stem,
            note=note,
        )
        asset = Asset(
            source_id=source.id,
            kind=AssetKind.document,
            path=destination,
            mime_type=DOCUMENT_MIME_TYPES.get(source_path.suffix.lower()),
            sha256=digest,
            size_bytes=source_path.stat().st_size,
        )
        self.sources.add(source)
        self.assets.add(asset)
        return source, asset
