"""Async pipeline routing for uploaded documents."""

from __future__ import annotations

from metaos.core.errors import UnsupportedDocumentError
from metaos.core.schemas import Asset, Source
from metaos.documents.service import SUPPORTED_TEXT_EXTENSIONS
from metaos.tasks.queueing import enqueue_ingest_document, enqueue_ocr_document, enqueue_pdf_route


OCR_EXTENSIONS = {
    ".png",
    ".jpg",
    ".jpeg",
    ".bmp",
    ".tif",
    ".tiff",
    ".webp",
}


def enqueue_document_pipeline(source: Source, asset: Asset):
    suffix = asset.path.suffix.lower()
    if suffix in SUPPORTED_TEXT_EXTENSIONS:
        return enqueue_ingest_document(source.id, asset.id)
    if suffix == ".pdf":
        return enqueue_pdf_route(source.id, asset.id)
    if suffix in OCR_EXTENSIONS:
        return enqueue_ocr_document(source.id, asset.id)
    raise UnsupportedDocumentError(f"暂不支持的文档类型：{suffix or asset.path.name}")
