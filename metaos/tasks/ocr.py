"""OCR tasks for the isolated OCR worker environment."""

from __future__ import annotations

import json
from tempfile import TemporaryDirectory
from pathlib import Path
from typing import Any

from metaos.core.config import get_settings
from metaos.core.schemas import Asset, AssetKind, JobStatus
from metaos.documents.pdf import render_pdf_page
from metaos.ingest.service import sha256_file
from metaos.tasks.queueing import enqueue_ingest_document
from metaos.workspace.catalog import AssetRepository
from metaos.workspace.jobs import JobRepository
from metaos.workspace.paths import ensure_workspace


OCR_MODES = {"fast", "default", "quality"}

_OCR_ENGINE_CACHE: dict[tuple[str, str], Any] = {}
_OCR_RUNTIME_CACHE: dict[tuple[str, str], dict[str, Any]] = {}
_LAST_OCR_CACHE_KEY: tuple[str, str] | None = None


def run_ocr_document(job_id: str) -> dict:
    paths = ensure_workspace()
    jobs = JobRepository(paths.database)
    assets = AssetRepository(paths.database)
    job = jobs.get(job_id)
    asset_id = str(job.payload["asset_id"])

    try:
        jobs.update(job_id, status=JobStatus.running, progress=0.1, message="加载 OCR 引擎")
        asset = assets.get(asset_id)
        markdown = ocr_pdf_markdown(asset.path) if asset.path.suffix.lower() == ".pdf" else ""
        if not markdown:
            text = ocr_file(asset.path)
            markdown = f"# {asset.path.stem}\n\n{text.strip()}\n"
        if not markdown.strip():
            raise RuntimeError("OCR 没有识别出文本。")

        jobs.update(job_id, progress=0.75, message="保存 OCR Markdown")
        markdown_path = paths.markdown / f"{asset.id}_ocr.md"
        markdown_path.write_text(markdown, encoding="utf-8", newline="\n")
        markdown_asset = Asset(
            source_id=asset.source_id,
            kind=AssetKind.markdown,
            path=markdown_path,
            mime_type="text/markdown",
            sha256=sha256_file(markdown_path),
            size_bytes=markdown_path.stat().st_size,
        )
        assets.add(markdown_asset)

        jobs.update(job_id, progress=0.9, message="提交入库任务")
        ingest_job = enqueue_ingest_document(asset.source_id, markdown_asset.id)
        result = {
            "source_asset_id": asset.id,
            "ocr_markdown_asset_id": markdown_asset.id,
            "ocr_markdown_path": str(markdown_path),
            "ingest_job_id": ingest_job.id,
            **ocr_runtime_summary(),
        }
        jobs.update(
            job_id,
            status=JobStatus.succeeded,
            progress=1,
            message="OCR 完成，入库任务已提交",
            result=result,
        )
        return result
    except Exception as exc:
        jobs.update(
            job_id,
            status=JobStatus.failed,
            progress=1,
            message="OCR 失败",
            error=str(exc),
        )
        raise


def run_ocr_pdf_pages(job_id: str) -> dict:
    paths = ensure_workspace()
    jobs = JobRepository(paths.database)
    assets = AssetRepository(paths.database)
    job = jobs.get(job_id)
    asset_id = str(job.payload["asset_id"])
    plan_path = Path(str(job.payload["plan_path"]))

    try:
        jobs.update(job_id, status=JobStatus.running, progress=0.1, message="读取混合 PDF 页计划")
        asset = assets.get(asset_id)
        plan = json.loads(plan_path.read_text(encoding="utf-8"))
        ocr_pages = [int(page) for page in plan.get("ocr_pages", [])]
        text_by_page = {int(key): str(value) for key, value in plan.get("text_by_page", {}).items()}

        jobs.update(job_id, progress=0.2, message="OCR 扫描页")
        ocr_text_by_page = ocr_pdf_pages(asset.path, ocr_pages, job_id=job_id)
        markdown = merge_pdf_page_markdown(
            title=str(plan.get("title") or asset.path.stem),
            page_count=int(plan.get("page_count") or max([*text_by_page, *ocr_text_by_page], default=0)),
            text_by_page=text_by_page,
            ocr_text_by_page=ocr_text_by_page,
        )
        if not markdown.strip():
            raise RuntimeError("混合 PDF 没有生成可入库文本。")

        jobs.update(job_id, progress=0.8, message="保存混合 PDF Markdown")
        markdown_path = paths.markdown / f"{asset.id}_pdf_mixed.md"
        markdown_path.write_text(markdown, encoding="utf-8", newline="\n")
        markdown_asset = Asset(
            source_id=asset.source_id,
            kind=AssetKind.markdown,
            path=markdown_path,
            mime_type="text/markdown",
            sha256=sha256_file(markdown_path),
            size_bytes=markdown_path.stat().st_size,
        )
        assets.add(markdown_asset)

        jobs.update(job_id, progress=0.9, message="提交入库任务")
        ingest_job = enqueue_ingest_document(asset.source_id, markdown_asset.id)
        result = {
            "source_asset_id": asset.id,
            "ocr_pages": ocr_pages,
            "ocr_markdown_asset_id": markdown_asset.id,
            "ocr_markdown_path": str(markdown_path),
            "ingest_job_id": ingest_job.id,
            **ocr_runtime_summary(),
        }
        jobs.update(
            job_id,
            status=JobStatus.succeeded,
            progress=1,
            message="混合 PDF OCR 完成，入库任务已提交",
            result=result,
        )
        return result
    except Exception as exc:
        jobs.update(
            job_id,
            status=JobStatus.failed,
            progress=1,
            message="混合 PDF OCR 失败",
            error=str(exc),
        )
        raise


def ocr_file(path: Path) -> str:
    return ocr_path(path, make_ocr_engine())


def make_ocr_engine():
    global _LAST_OCR_CACHE_KEY

    settings = get_settings()
    mode = normalize_ocr_mode(settings.ocr_mode)
    resolved_device, runtime_info = configure_paddle_device(settings.ocr_device)
    cache_key = (mode, resolved_device)
    _LAST_OCR_CACHE_KEY = cache_key
    if cache_key in _OCR_ENGINE_CACHE:
        _OCR_RUNTIME_CACHE[cache_key]["ocr_render_zoom"] = settings.ocr_render_zoom
        return _OCR_ENGINE_CACHE[cache_key]

    from paddleocr import PaddleOCR

    if mode == "fast":
        engine = PaddleOCR(
            lang="ch",
            use_doc_orientation_classify=False,
            use_doc_unwarping=False,
            use_textline_orientation=False,
        )
    elif mode == "default":
        engine = PaddleOCR(lang="ch")
    elif mode == "quality":
        engine = PaddleOCR(
            lang="ch",
            use_doc_orientation_classify=True,
            use_doc_unwarping=True,
            use_textline_orientation=True,
        )
    else:
        raise RuntimeError(f"Unsupported OCR_MODE: {mode}")

    _OCR_ENGINE_CACHE[cache_key] = engine
    _OCR_RUNTIME_CACHE[cache_key] = {
        **runtime_info,
        "ocr_mode": mode,
        "ocr_device": resolved_device,
        "ocr_requested_device": settings.ocr_device,
        "ocr_render_zoom": settings.ocr_render_zoom,
    }
    return engine


def normalize_ocr_mode(mode: str) -> str:
    normalized = mode.strip().lower()
    if normalized not in OCR_MODES:
        raise RuntimeError(f"Unsupported OCR_MODE: {mode}. Use one of: fast, default, quality.")
    return normalized


def normalize_ocr_device(device: str) -> str:
    normalized = device.strip().lower()
    if normalized in {"auto", "cpu"}:
        return normalized
    if normalized == "gpu":
        return "gpu:0"
    if normalized.startswith("gpu:"):
        suffix = normalized.removeprefix("gpu:")
        if suffix.isdigit():
            return normalized
    raise RuntimeError("Unsupported OCR_DEVICE. Use auto, cpu, gpu, or gpu:0.")


def configure_paddle_device(requested_device: str) -> tuple[str, dict[str, Any]]:
    import paddle

    requested = normalize_ocr_device(requested_device)
    compiled_with_cuda = bool(paddle.device.is_compiled_with_cuda())
    if requested == "auto":
        resolved = "gpu:0" if compiled_with_cuda else "cpu"
    else:
        resolved = requested

    if resolved.startswith("gpu") and not compiled_with_cuda:
        raise RuntimeError(
            f"OCR_DEVICE={requested_device} requires GPU Paddle, "
            "but current Paddle is not compiled with CUDA."
        )

    try:
        paddle.device.set_device(resolved)
    except Exception as exc:
        raise RuntimeError(f"Failed to set OCR device to {resolved}: {exc}") from exc

    try:
        current_device = paddle.device.get_device()
    except Exception:
        current_device = resolved

    return current_device, {
        "paddle_version": getattr(paddle, "__version__", "unknown"),
        "compiled_with_cuda": compiled_with_cuda,
        "paddle_current_device": current_device,
    }


def ocr_runtime_summary() -> dict[str, Any]:
    settings = get_settings()
    info: dict[str, Any] = {}
    if _LAST_OCR_CACHE_KEY is not None:
        info.update(_OCR_RUNTIME_CACHE.get(_LAST_OCR_CACHE_KEY, {}))
    return {
        "ocr_mode": info.get("ocr_mode", normalize_ocr_mode(settings.ocr_mode)),
        "ocr_device": info.get("ocr_device"),
        "ocr_requested_device": info.get("ocr_requested_device", settings.ocr_device),
        "ocr_render_zoom": info.get("ocr_render_zoom", settings.ocr_render_zoom),
        "paddle_version": info.get("paddle_version"),
        "compiled_with_cuda": info.get("compiled_with_cuda"),
        "paddle_current_device": info.get("paddle_current_device"),
    }


def ocr_path(path: Path, ocr) -> str:
    try:
        result = ocr.predict(str(path))
    except Exception:
        result = ocr.ocr(str(path))
    lines = extract_text_lines(result)
    return "\n".join(line for line in lines if line.strip())


def ocr_pdf_markdown(path: Path) -> str:
    page_texts = ocr_pdf_pages(path, None)
    if not any(text.strip() for text in page_texts.values()):
        return ""
    return merge_pdf_page_markdown(
        title=path.stem,
        page_count=max(page_texts, default=0),
        text_by_page={},
        ocr_text_by_page=page_texts,
    )


def ocr_pdf_pages(path: Path, pages: list[int] | None, *, job_id: str | None = None) -> dict[int, str]:
    paths = ensure_workspace()
    jobs = JobRepository(paths.database)
    ocr = make_ocr_engine()
    zoom = get_settings().ocr_render_zoom
    if zoom <= 0:
        raise RuntimeError(f"OCR_RENDER_ZOOM must be greater than 0, got {zoom}.")
    page_numbers = pages or all_pdf_page_numbers(path)
    texts: dict[int, str] = {}
    total = len(page_numbers)
    with TemporaryDirectory() as tmp:
        tmp_dir = Path(tmp)
        for index, page_number in enumerate(page_numbers, start=1):
            if job_id:
                progress = 0.2 + 0.55 * (index - 1) / max(total, 1)
                jobs.update(job_id, progress=progress, message=f"OCR 第 {page_number} 页")
            image_path = render_pdf_page(path, page_number, tmp_dir / f"page_{page_number}.png", zoom=zoom)
            texts[page_number] = ocr_path(image_path, ocr)
    return texts


def all_pdf_page_numbers(path: Path) -> list[int]:
    try:
        import pymupdf
    except ImportError:
        import fitz as pymupdf

    with pymupdf.open(str(path)) as document:
        return list(range(1, len(document) + 1))


def merge_pdf_page_markdown(
    *,
    title: str,
    page_count: int,
    text_by_page: dict[int, str],
    ocr_text_by_page: dict[int, str],
) -> str:
    parts = [f"# {title}", ""]
    for page_number in range(1, page_count + 1):
        text = (text_by_page.get(page_number) or ocr_text_by_page.get(page_number) or "").strip()
        parts.extend([f"<!-- metaos:page={page_number} -->", "", text or "（本页未提取到文本）", ""])
    return "\n".join(parts).strip() + "\n"


def extract_text_lines(value: Any) -> list[str]:
    lines: list[str] = []
    collect_text(value, lines)
    deduped: list[str] = []
    for line in lines:
        stripped = line.strip()
        if stripped and (not deduped or deduped[-1] != stripped):
            deduped.append(stripped)
    return deduped


def collect_text(value: Any, lines: list[str]) -> None:
    if value is None:
        return
    if isinstance(value, str):
        if value.strip():
            lines.append(value)
        return
    if isinstance(value, dict):
        for key in ("rec_texts", "texts", "text"):
            if key in value:
                collect_text(value[key], lines)
        return
    if hasattr(value, "json"):
        try:
            collect_text(value.json, lines)
            return
        except Exception:
            pass
    if isinstance(value, (list, tuple)):
        if len(value) >= 2 and isinstance(value[1], (list, tuple)) and value[1]:
            candidate = value[1][0]
            if isinstance(candidate, str):
                lines.append(candidate)
                return
        for item in value:
            collect_text(item, lines)
