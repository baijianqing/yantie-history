"""Document parsing and chunking tasks for the ingest worker."""

from __future__ import annotations

from metaos.core.schemas import JobStatus
from metaos.documents.service import ParsedDocument, parse_text_document
from metaos.knowledge.service import KnowledgeService
from metaos.tasks.queueing import enqueue_index_knowledge
from metaos.workspace.catalog import AssetRepository, SourceRepository
from metaos.workspace.jobs import JobRepository
from metaos.workspace.paths import ensure_workspace


def run_ingest_document(job_id: str) -> dict:
    paths = ensure_workspace()
    jobs = JobRepository(paths.database)
    assets = AssetRepository(paths.database)
    sources = SourceRepository(paths.database)
    knowledge = KnowledgeService(paths)
    job = jobs.get(job_id)
    asset_id = str(job.payload["asset_id"])
    source_id = str(job.payload["source_id"])

    try:
        jobs.update(job_id, status=JobStatus.running, progress=0.1, message="解析文本")
        source = sources.get(source_id)
        asset = assets.get(asset_id)
        document = parse_text_document(asset)

        jobs.update(job_id, progress=0.55, message="生成知识条目和知识块")
        item = knowledge.create_from_document(source=source, asset=asset, document=document)
        chunk_count = int(item.metadata.get("chunk_count", 0))

        jobs.update(job_id, progress=0.85, message="提交索引任务")
        index_job = enqueue_index_knowledge(item.id)
        result = {
            "source_id": source.id,
            "asset_id": asset.id,
            "knowledge_item_id": item.id,
            "chunk_count": chunk_count,
            "markdown_path": str(item.markdown_path),
            "index_job_id": index_job.id,
        }
        jobs.update(
            job_id,
            status=JobStatus.succeeded,
            progress=1,
            message="入库完成，索引任务已提交",
            result=result,
        )
        return result
    except Exception as exc:
        jobs.update(
            job_id,
            status=JobStatus.failed,
            progress=1,
            message="入库失败",
            error=str(exc),
        )
        raise


def run_rebuild_chunks(job_id: str) -> dict:
    paths = ensure_workspace()
    jobs = JobRepository(paths.database)
    knowledge = KnowledgeService(paths)
    job = jobs.get(job_id)
    item_id = str(job.payload["knowledge_item_id"])

    try:
        jobs.update(job_id, status=JobStatus.running, progress=0.1, message="重新生成知识块")
        item, chunk_count = knowledge.rebuild_chunks(item_id)
        jobs.update(job_id, progress=0.85, message="提交索引任务")
        index_job = enqueue_index_knowledge(item.id)
        result = {
            "knowledge_item_id": item.id,
            "chunk_count": chunk_count,
            "index_job_id": index_job.id,
        }
        jobs.update(
            job_id,
            status=JobStatus.succeeded,
            progress=1,
            message="知识块已生成，索引任务已提交",
            result=result,
        )
        return result
    except Exception as exc:
        jobs.update(
            job_id,
            status=JobStatus.failed,
            progress=1,
            message="知识块生成失败",
            error=str(exc),
        )
        raise
