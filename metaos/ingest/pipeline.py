"""Stage-1 document ingestion pipeline."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from metaos.core.schemas import Asset, Job, JobStatus, JobType, KnowledgeItem, Source
from metaos.documents.service import parse_text_document
from metaos.ingest.service import IngestService
from metaos.knowledge.service import KnowledgeService
from metaos.workspace.jobs import JobRepository
from metaos.workspace.paths import WorkspacePaths, ensure_workspace


@dataclass(frozen=True)
class DocumentIngestResult:
    source: Source
    asset: Asset
    knowledge_item: KnowledgeItem
    job: Job


class DocumentIngestPipeline:
    def __init__(self, paths: WorkspacePaths | None = None):
        self.paths = paths or ensure_workspace()
        self.ingest = IngestService(self.paths)
        self.knowledge = KnowledgeService(self.paths)
        self.jobs = JobRepository(self.paths.database)

    def ingest_upload(self, *, filename: str, content: bytes) -> DocumentIngestResult:
        job = self.jobs.create(JobType.ingest_document, {"filename": filename})
        return self._run(job, lambda: self.ingest.add_bytes(filename=filename, content=content))

    def ingest_local_file(self, path: Path) -> DocumentIngestResult:
        job = self.jobs.create(JobType.ingest_document, {"path": str(path)})
        return self._run(job, lambda: self.ingest.add_local_file(path))

    def _run(self, job: Job, add_asset) -> DocumentIngestResult:
        try:
            self.jobs.update(job.id, status=JobStatus.running, progress=0.15, message="保存原始文件")
            source, asset = add_asset()
            self.jobs.update(job.id, progress=0.45, message="解析文本")
            document = parse_text_document(asset)
            self.jobs.update(job.id, progress=0.75, message="生成知识条目")
            knowledge_item = self.knowledge.create_from_document(
                source=source,
                asset=asset,
                document=document,
            )
            final_job = self.jobs.update(
                job.id,
                status=JobStatus.succeeded,
                progress=1,
                message="入库完成",
                result={
                    "source_id": source.id,
                    "asset_id": asset.id,
                    "knowledge_item_id": knowledge_item.id,
                    "chunk_count": knowledge_item.metadata.get("chunk_count", 0),
                    "markdown_path": str(knowledge_item.markdown_path),
                },
            )
            return DocumentIngestResult(
                source=source,
                asset=asset,
                knowledge_item=knowledge_item,
                job=final_job,
            )
        except Exception as exc:
            self.jobs.update(
                job.id,
                status=JobStatus.failed,
                progress=1,
                message="入库失败",
                error=str(exc),
            )
            raise
