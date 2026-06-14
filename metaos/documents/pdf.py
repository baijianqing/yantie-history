"""PDF page analysis and text extraction helpers."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any


TEXT_PAGE_MIN_CHARS = 80
STRONG_TEXT_PAGE_CHARS = 240
SCAN_IMAGE_RATIO = 0.45
MIXED_IMAGE_RATIO = 0.25


@dataclass(frozen=True)
class PdfPageAnalysis:
    page_number: int
    mode: str
    text_length: int
    image_count: int
    image_ratio: float

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class PdfAnalysis:
    path: Path
    page_count: int
    classification: str
    pages: list[PdfPageAnalysis]

    def as_dict(self) -> dict[str, Any]:
        return {
            "path": str(self.path),
            "page_count": self.page_count,
            "classification": self.classification,
            "pages": [page.as_dict() for page in self.pages],
        }

    @property
    def ocr_pages(self) -> list[int]:
        return [page.page_number for page in self.pages if page.mode in {"scan", "mixed"}]


def open_pdf(path: Path):
    try:
        import pymupdf
    except ImportError:
        import fitz as pymupdf

    return pymupdf.open(str(path))


def analyze_pdf(path: Path) -> PdfAnalysis:
    path = path.resolve()
    pages: list[PdfPageAnalysis] = []
    with open_pdf(path) as document:
        for index, page in enumerate(document, start=1):
            text = page.get_text("text") or ""
            text_length = len("".join(text.split()))
            image_infos = page_image_infos(page)
            image_ratio = page_image_ratio(page, image_infos)
            mode = classify_page(
                text_length=text_length,
                image_count=len(image_infos),
                image_ratio=image_ratio,
            )
            pages.append(
                PdfPageAnalysis(
                    page_number=index,
                    mode=mode,
                    text_length=text_length,
                    image_count=len(image_infos),
                    image_ratio=round(image_ratio, 4),
                )
            )
    return PdfAnalysis(
        path=path,
        page_count=len(pages),
        classification=classify_document(pages),
        pages=pages,
    )


def page_image_infos(page) -> list[dict[str, Any]]:
    try:
        return list(page.get_image_info(xrefs=True))
    except Exception:
        return [{"bbox": bbox} for bbox in page.get_image_rects()]


def page_image_ratio(page, image_infos: list[dict[str, Any]]) -> float:
    page_area = float(abs(page.rect.width * page.rect.height))
    if page_area <= 0:
        return 0.0
    total_area = 0.0
    for info in image_infos:
        bbox = info.get("bbox") if isinstance(info, dict) else None
        if bbox is None:
            continue
        try:
            width = max(0.0, float(bbox[2]) - float(bbox[0]))
            height = max(0.0, float(bbox[3]) - float(bbox[1]))
        except Exception:
            continue
        total_area += width * height
    return min(1.0, total_area / page_area)


def classify_page(*, text_length: int, image_count: int, image_ratio: float) -> str:
    if text_length >= STRONG_TEXT_PAGE_CHARS and image_ratio < 0.75:
        return "text"
    if text_length >= TEXT_PAGE_MIN_CHARS and image_ratio < MIXED_IMAGE_RATIO:
        return "text"
    if image_count > 0 and image_ratio >= SCAN_IMAGE_RATIO and text_length < TEXT_PAGE_MIN_CHARS:
        return "scan"
    if image_count > 0 and image_ratio >= MIXED_IMAGE_RATIO:
        return "mixed"
    return "text"


def classify_document(pages: list[PdfPageAnalysis]) -> str:
    if not pages:
        return "non_scanned"
    modes = {page.mode for page in pages}
    if modes <= {"text"}:
        return "non_scanned"
    if modes <= {"scan"}:
        return "scanned"
    return "mixed"


def extract_pdf_markdown(path: Path, *, pages: set[int] | None = None, title: str | None = None) -> str:
    path = path.resolve()
    heading = title or path.stem
    parts = [f"# {heading}", ""]
    with open_pdf(path) as document:
        for index, page in enumerate(document, start=1):
            if pages is not None and index not in pages:
                continue
            text = (page.get_text("text") or "").strip()
            parts.extend([f"<!-- metaos:page={index} -->", "", text or "（本页未提取到文本）", ""])
    return "\n".join(parts).strip() + "\n"


def extract_pdf_page_texts(path: Path, pages: set[int]) -> dict[int, str]:
    texts: dict[int, str] = {}
    with open_pdf(path) as document:
        for index, page in enumerate(document, start=1):
            if index in pages:
                texts[index] = (page.get_text("text") or "").strip()
    return texts


def render_pdf_page(path: Path, page_number: int, output_path: Path, zoom: float = 2.0) -> Path:
    try:
        import pymupdf
    except ImportError:
        import fitz as pymupdf

    with pymupdf.open(str(path)) as document:
        page = document.load_page(page_number - 1)
        matrix = pymupdf.Matrix(zoom, zoom)
        pixmap = page.get_pixmap(matrix=matrix, alpha=False)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        pixmap.save(str(output_path))
    return output_path
