"""TXT and Markdown parsing for the stage-1 ingestion loop."""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

from metaos.core.errors import UnsupportedDocumentError
from metaos.core.schemas import Asset


SUPPORTED_TEXT_EXTENSIONS = {".txt", ".md", ".markdown"}


@dataclass(frozen=True)
class ParsedDocument:
    title: str
    text: str
    source_path: Path
    extension: str


def read_text(path: Path) -> str:
    raw = path.read_bytes()
    for encoding in ("utf-8-sig", "utf-8", "gb18030"):
        try:
            return raw.decode(encoding)
        except UnicodeDecodeError:
            continue
    return raw.decode("utf-8", errors="replace")


def normalize_text(text: str) -> str:
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    text = re.sub(r"[ \t]+\n", "\n", text)
    text = re.sub(r"\n{4,}", "\n\n\n", text)
    return text.strip()


def extract_title(text: str, fallback: str) -> str:
    for line in text.splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        if stripped.startswith("#"):
            heading = stripped.lstrip("#").strip()
            if heading:
                return heading[:120]
        return stripped[:120]
    return fallback


def parse_text_document(asset: Asset) -> ParsedDocument:
    path = asset.path
    extension = path.suffix.lower()
    if extension not in SUPPORTED_TEXT_EXTENSIONS:
        raise UnsupportedDocumentError(f"暂不支持的文档类型：{extension or path.name}")
    text = normalize_text(read_text(path))
    title = extract_title(text, path.stem)
    return ParsedDocument(title=title, text=text, source_path=path, extension=extension)
