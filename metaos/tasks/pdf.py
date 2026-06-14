"""PDF routing tasks for text, scanned, and mixed documents."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from metaos.core.schemas import Asset, AssetKind, JobStatus
from metaos.documents.pdf import PdfAnalysis, analyze_pdf, extract_pdf_markdown, extract_pdf_page_texts
from metaos.ingest.service import sha256_file
from metaos.tasks.queueing import enqueue_ingest_document, enqueue_ocr_document, enqueue_ocr_pdf_pages
from metaos.workspace.catalog import AssetRepository
from metaos.workspace.jobs import JobRepository
from metaos.workspace.paths import ensure_workspace


def run_pdf_route(job_id: str) -> dict[str, Any]:
    paths = ensure_workspace()
    jobs = JobRepository(paths.database)
    assets = AssetRepository(paths.database)
    job = jobs.get(job_id)
    asset_id = str(job.payload["asset_id"])
    source_id = str(job.payload["source_id"])

    try:
        jobs.update(job_id, status=JobStatus.running, progress=0.1, message="分析 PDF 页面")
        asset = assets.get(asset_id)
        analysis = analyze_pdf(asset.path)

        if analysis.classification == "non_scanned":
            jobs.update(job_id, progress=0.55, message="抽取 PDF 文本")
            markdown_asset = create_pdf_text_markdown_asset(
                asset=asset,
                markdown=extract_pdf_markdown(asset.path, title=asset.path.stem),
                suffix="text",
            )
            jobs.update(job_id, progress=0.85, message="提交入库任务")
            child_job = enqueue_ingest_document(source_id, markdown_asset.id)
        elif analysis.classification == "scanned":
            jobs.update(job_id, progress=0.85, message="提交 OCR 任务")
            child_job = enqueue_ocr_document(source_id, asset.id)
            markdown_asset = None
        else:
            jobs.update(job_id, progress=0.45, message="生成混合 PDF 页计划")
            plan_path = write_mixed_pdf_plan(asset.path, asset, analysis)
            jobs.update(job_id, progress=0.85, message="提交混合 PDF OCR 任务")
            child_job = enqueue_ocr_pdf_pages(source_id, asset.id, str(plan_path))
            markdown_asset = None

        result = {
            "source_id": source_id,
            "asset_id": asset.id,
            "classification": analysis.classification,
            "page_count": analysis.page_count,
            "ocr_pages": analysis.ocr_pages,
            "analysis": analysis.as_dict(),
            "child_job_id": child_job.id,
        }
        if markdown_asset is not None:
            result["markdown_asset_id"] = markdown_asset.id
            result["markdown_path"] = str(markdown_asset.path)
        jobs.update(
            job_id,
            status=JobStatus.succeeded,
            progress=1,
            message=f"PDF 路由完成：{analysis.classification}",
            result=result,
        )
        return result
    except Exception as exc:
        jobs.update(
            job_id,
            status=JobStatus.failed,
            progress=1,
            message="PDF 路由失败",
            error=str(exc),
        )
        raise


def create_pdf_text_markdown_asset(*, asset: Asset, markdown: str, suffix: str) -> Asset:
    paths = ensure_workspace()
    assets = AssetRepository(paths.database)
    markdown_path = paths.markdown / f"{asset.id}_pdf_{suffix}.md"
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
    return markdown_asset


def write_mixed_pdf_plan(path: Path, asset: Asset, analysis: PdfAnalysis) -> Path:
    paths = ensure_workspace()
    text_pages = {page.page_number for page in analysis.pages if page.mode == "text"}
    text_by_page = extract_pdf_page_texts(path, text_pages)
    plan = {
        "source_asset_id": asset.id,
        "source_id": asset.source_id,
        "source_path": str(path),
        "title": path.stem,
        "classification": analysis.classification,
        "page_count": analysis.page_count,
        "pages": [page.as_dict() for page in analysis.pages],
        "ocr_pages": analysis.ocr_pages,
        "text_by_page": {str(page_number): text for page_number, text in text_by_page.items()},
    }
    plan_path = paths.exports / f"{asset.id}_pdf_route.json"
    plan_path.write_text(json.dumps(plan, ensure_ascii=False, indent=2), encoding="utf-8")
    return plan_path
