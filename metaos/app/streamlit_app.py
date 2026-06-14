"""Streamlit dashboard for the MetaOS Lite local workspace."""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path
from typing import Any

import streamlit as st

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from metaos import __version__
from metaos.core.config import get_settings
from metaos.core.schemas import Chunk, Job, JobStatus, JobType
from metaos.ingest.service import IngestService
from metaos.knowledge.deletion import KnowledgeDeletionService
from metaos.llm_gateway.client import LLMGateway
from metaos.llm_gateway.pricing import estimate_balance_tokens, price_for_model
from metaos.retrieval.service import RetrievalService
from metaos.tasks.monitoring import runtime_status
from metaos.tasks.pipeline import enqueue_document_pipeline
from metaos.tasks.queueing import (
    enqueue_index_knowledge,
    enqueue_rag_answer,
    enqueue_rebuild_chunks,
    enqueue_rebuild_index,
)
from metaos.workspace.catalog import ChunkRepository, KnowledgeRepository
from metaos.workspace.jobs import JobRepository
from metaos.workspace.paths import ensure_workspace


st.set_page_config(page_title="MetaOS Lite", page_icon="M", layout="wide")

st.title("MetaOS Lite")
st.caption("AI 时代创业者的个人研究院")

paths = ensure_workspace()
repo = JobRepository(paths.database)
knowledge_repo = KnowledgeRepository(paths.database)
chunk_repo = ChunkRepository(paths.database)
ingest_service = IngestService(paths)

PAGE_HEADING_RE = re.compile(r"^第\s*\d+\s*页$")
PAGE_MARKER_TEXT = "metaos:page="

if "chunk_rebuild_message" in st.session_state:
    st.success(st.session_state.pop("chunk_rebuild_message"))
if "index_message" in st.session_state:
    st.success(st.session_state.pop("index_message"))
if "ingest_message" in st.session_state:
    st.success(st.session_state.pop("ingest_message"))
if "rag_message" in st.session_state:
    st.success(st.session_state.pop("rag_message"))
if "delete_message" in st.session_state:
    st.success(st.session_state.pop("delete_message"))


def json_text(value: Any) -> str:
    return json.dumps(value or {}, ensure_ascii=False, indent=2, default=str)


def format_int(value: Any) -> str:
    try:
        return f"{int(value):,}"
    except (TypeError, ValueError):
        return "-"


def format_float(value: Any, digits: int = 6) -> str:
    try:
        return f"{float(value):,.{digits}f}"
    except (TypeError, ValueError):
        return "-"


def optional_int(value: Any) -> int | None:
    if value in {None, ""}:
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def optional_float(value: Any) -> float | None:
    if value in {None, ""}:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def collect_job_links(value: Any) -> list[str]:
    links: list[str] = []

    def visit(node: Any) -> None:
        if isinstance(node, dict):
            for key, item in node.items():
                if isinstance(item, str) and (key.endswith("_job_id") or key == "child_job_id"):
                    links.append(item)
                else:
                    visit(item)
            return
        if isinstance(node, list):
            for item in node:
                visit(item)

    visit(value)
    return list(dict.fromkeys(links))


def job_summary(job: Job) -> dict[str, Any]:
    child_jobs = collect_job_links({"payload": job.payload, "result": job.result})
    return {
        "id": job.id,
        "type": job.type.value,
        "status": job.status.value,
        "progress": f"{job.progress:.0%}",
        "message": job.message or "",
        "error": job.error or "",
        "child_jobs": ", ".join(child_jobs),
        "updated_at": job.updated_at.isoformat(),
    }


def is_page_heading_path(heading_path: list[str]) -> bool:
    return any(PAGE_HEADING_RE.fullmatch(part.strip()) for part in heading_path)


def chunk_health(chunks: list[Chunk]) -> dict[str, Any]:
    total = len(chunks)
    if total <= 0:
        return {
            "chunk_count": 0,
            "avg_chars": 0,
            "min_chars": 0,
            "max_chars": 0,
            "page_heading_count": 0,
            "page_heading_ratio": 0.0,
            "citation_page_count": 0,
            "citation_page_ratio": 0.0,
            "marker_count": 0,
            "status": "empty",
        }

    char_counts = [chunk.char_count or len(chunk.text) for chunk in chunks]
    page_heading_count = sum(1 for chunk in chunks if is_page_heading_path(chunk.heading_path))
    citation_page_count = sum(1 for chunk in chunks if chunk.citation and chunk.citation.page is not None)
    marker_count = sum(1 for chunk in chunks if PAGE_MARKER_TEXT in chunk.text)
    page_heading_ratio = page_heading_count / total
    citation_page_ratio = citation_page_count / total
    if page_heading_ratio > 0.5 or marker_count > 0:
        status = "needs_attention"
    elif citation_page_ratio == 0:
        status = "no_page_citation"
    else:
        status = "healthy"
    return {
        "chunk_count": total,
        "avg_chars": round(sum(char_counts) / total),
        "min_chars": min(char_counts),
        "max_chars": max(char_counts),
        "page_heading_count": page_heading_count,
        "page_heading_ratio": page_heading_ratio,
        "citation_page_count": citation_page_count,
        "citation_page_ratio": citation_page_ratio,
        "marker_count": marker_count,
        "status": status,
    }


def render_chunk_health(chunks: list[Chunk], metadata: dict[str, Any]) -> None:
    st.subheader("分块健康检查")
    health = chunk_health(chunks)
    cols = st.columns(4)
    cols[0].metric("Chunk 数", health["chunk_count"])
    cols[1].metric("平均长度", f"{health['avg_chars']} 字")
    cols[2].metric("页标题风险", f"{health['page_heading_count']} 个")
    cols[3].metric("页码引用覆盖", f"{health['citation_page_ratio']:.0%}")
    st.caption(
        f"chunker={metadata.get('chunker', '-')}; "
        f"metadata.chunk_count={metadata.get('chunk_count', '-')}; "
        f"min/max={health['min_chars']}/{health['max_chars']}"
    )
    if health["status"] == "needs_attention":
        st.warning(
            "这个条目可能仍然存在按页分块问题。建议点击“重新生成知识块”，完成后再重建索引。"
        )
    elif health["status"] == "no_page_citation":
        source_uri = str(metadata.get("source_uri", "")).lower()
        if source_uri.endswith(".pdf"):
            st.warning("当前 PDF/OCR 条目没有页码 citation。建议重新生成知识块。")
        else:
            st.info("当前 chunks 没有页码 citation。TXT/Markdown 文档通常正常。")
    elif health["status"] == "healthy":
        st.success("分块结构看起来正常：未发现页码 heading 污染，且 chunks 有页码引用。")
    else:
        st.info("当前条目还没有 chunks。")


def render_runtime_console(job_repository: JobRepository) -> None:
    st.subheader("运行控制台")
    status = runtime_status()
    redis_status = status["redis"]
    queues = status.get("queues", [])
    workers = status.get("workers", [])
    coverage = status.get("worker_coverage", {})
    recent_jobs = job_repository.list(limit=200)

    health_cols = st.columns(4)
    health_cols[0].metric("Redis", "正常" if redis_status["ok"] else "异常")
    health_cols[1].metric("排队任务", sum(queue.get("queued", 0) for queue in queues))
    health_cols[2].metric("活跃 Worker", len(workers))
    health_cols[3].metric(
        "运行中任务",
        sum(1 for job in recent_jobs if job.status == JobStatus.running),
    )
    if not redis_status["ok"]:
        st.error(f"Redis 连接失败：{redis_status.get('error') or redis_status.get('url')}")

    queue_tab, worker_tab, job_tab = st.tabs(["队列", "Worker", "任务"])
    with queue_tab:
        if queues:
            st.dataframe(queues, width="stretch", hide_index=True)
        else:
            st.info("Redis 不可用或暂无队列状态。")
        if coverage:
            st.caption("Worker 覆盖情况")
            st.dataframe(
                [
                    {"queue": queue_name, "has_worker": has_worker}
                    for queue_name, has_worker in coverage.items()
                ],
                width="stretch",
                hide_index=True,
            )

    with worker_tab:
        if workers:
            st.dataframe(workers, width="stretch", hide_index=True)
        else:
            st.warning("没有检测到 RQ worker。请确认 main worker 和 OCR worker 已启动。")

    with job_tab:
        render_job_browser(recent_jobs)


def render_job_browser(jobs: list[Job]) -> None:
    if not jobs:
        st.write("暂无任务。")
        return

    filter_cols = st.columns([1, 1, 1])
    status_options = [status.value for status in JobStatus]
    type_options = sorted({job.type.value for job in jobs} | {job_type.value for job_type in JobType})
    selected_statuses = filter_cols[0].multiselect(
        "状态过滤",
        options=status_options,
        default=status_options,
    )
    selected_types = filter_cols[1].multiselect(
        "类型过滤",
        options=type_options,
        default=type_options,
    )
    detail_limit = filter_cols[2].number_input("显示数量", min_value=10, max_value=200, value=50, step=10)

    filtered = [
        job
        for job in jobs
        if job.status.value in selected_statuses and job.type.value in selected_types
    ][: int(detail_limit)]
    if not filtered:
        st.write("当前过滤条件下没有任务。")
        return

    st.dataframe(
        [job_summary(job) for job in filtered],
        width="stretch",
        hide_index=True,
    )

    st.caption("任务详情")
    for job in filtered:
        child_jobs = collect_job_links({"payload": job.payload, "result": job.result})
        title = f"{job.status.value} · {job.type.value} · {job.id}"
        with st.expander(title):
            st.write(f"进度：`{job.progress:.0%}`")
            st.write(f"更新时间：`{job.updated_at.isoformat()}`")
            if job.message:
                st.info(job.message)
            if job.error:
                st.error(job.error)
            if child_jobs:
                st.write("子任务链路：")
                st.code("\n".join(child_jobs), language="text")
            detail_cols = st.columns(2)
            with detail_cols[0]:
                st.caption("payload")
                st.code(json_text(job.payload), language="json")
            with detail_cols[1]:
                st.caption("result")
                st.code(json_text(job.result), language="json")


def rag_job_label(job: Job) -> str:
    question = str(job.payload.get("question") or "").strip()
    if len(question) > 42:
        question = f"{question[:42]}..."
    return f"{job.status.value} · {job.updated_at.strftime('%m-%d %H:%M')} · {question or job.id}"


def render_rag_answer_job(job: Job) -> None:
    st.caption(f"任务：`{job.id}` · 状态：`{job.status.value}` · 进度：`{job.progress:.0%}`")
    question = str(job.payload.get("question") or "").strip()
    if question:
        st.write(f"问题：{question}")
    if job.message and job.status != JobStatus.succeeded:
        st.info(job.message)
    if job.status == JobStatus.failed:
        st.error(job.error or "RAG 问答任务失败。")
        return
    if job.status != JobStatus.succeeded:
        st.info("答案还在生成中。请稍后刷新任务状态。")
        return

    answer = str(job.result.get("answer") or "").strip()
    if answer:
        st.markdown(answer)
    else:
        st.warning("任务已完成，但没有返回 answer 字段。")

    render_rag_token_usage(job.result)

    citations = job.result.get("citations") or []
    if citations:
        st.caption("引用来源")
        st.dataframe(
            [
                {
                    "index": citation.get("index"),
                    "score": citation.get("score"),
                    "heading": " / ".join(citation.get("heading_path") or []),
                    "ordinal": citation.get("ordinal"),
                    "file_path": citation.get("file_path") or "",
                }
                for citation in citations
            ],
            width="stretch",
            hide_index=True,
        )

    retrieved_chunks = job.result.get("retrieved_chunks") or []
    if retrieved_chunks:
        st.caption("命中的知识块")
        for chunk in retrieved_chunks:
            heading = " / ".join(chunk.get("heading_path") or []) or "未命名片段"
            score = chunk.get("score")
            ordinal = chunk.get("ordinal") or "-"
            title = f"{score:.3f} · {heading} · #{ordinal}" if isinstance(score, (int, float)) else f"{heading} · #{ordinal}"
            with st.expander(title):
                if chunk.get("file_path"):
                    st.caption(str(chunk.get("file_path")))
                st.text(str(chunk.get("text") or ""))


def render_rag_token_usage(result: dict[str, Any]) -> None:
    usage = result.get("llm_usage") or {}
    if not usage:
        st.caption("本次 RAG 没有记录 DeepSeek token 用量。老任务或无召回任务可能为空。")
        return

    st.caption("本次 DeepSeek token 消耗")
    cols = st.columns(5)
    cols[0].metric("输入 tokens", format_int(usage.get("prompt_tokens")))
    cols[1].metric("输出 tokens", format_int(usage.get("completion_tokens")))
    cols[2].metric("总 tokens", format_int(usage.get("total_tokens")))
    cols[3].metric("缓存命中", format_int(usage.get("prompt_cache_hit_tokens")))
    cols[4].metric("缓存未命中", format_int(usage.get("prompt_cache_miss_tokens")))

    reasoning_tokens = usage.get("reasoning_tokens")
    cost = result.get("llm_cost_estimate") or {}
    price = cost.get("price_per_1m") or {}
    cost_parts = []
    if result.get("llm_model"):
        cost_parts.append(f"模型：`{result.get('llm_model')}`")
    if reasoning_tokens:
        cost_parts.append(f"推理 tokens：`{format_int(reasoning_tokens)}`")
    if cost:
        cost_parts.append(f"估算费用：`${format_float(cost.get('total_cost'), 8)}`")
    if price:
        cost_parts.append(
            "单价/1M tokens："
            f"cache hit `${price.get('input_cache_hit')}`，"
            f"cache miss `${price.get('input_cache_miss')}`，"
            f"output `${price.get('output')}`"
        )
    if cost_parts:
        st.caption("；".join(cost_parts))


def recent_rag_jobs(job_repository: JobRepository, limit: int = 20) -> list[Job]:
    return [
        job
        for job in job_repository.list(limit=100)
        if job.type == JobType.answer_question
    ][:limit]


def rag_usage_summary(job: Job) -> dict[str, Any]:
    usage = job.result.get("llm_usage") or {}
    cost = job.result.get("llm_cost_estimate") or {}
    question = str(job.payload.get("question") or "")
    if len(question) > 36:
        question = f"{question[:36]}..."
    return {
        "updated_at": job.updated_at.strftime("%m-%d %H:%M"),
        "status": job.status.value,
        "question": question,
        "model": job.result.get("llm_model") or "",
        "prompt_tokens": optional_int(usage.get("prompt_tokens")),
        "completion_tokens": optional_int(usage.get("completion_tokens")),
        "total_tokens": optional_int(usage.get("total_tokens")),
        "cost_usd": optional_float(cost.get("total_cost")),
    }


def render_deepseek_account_status() -> None:
    settings = get_settings()
    price = price_for_model(settings.deepseek_model)
    st.caption(
        "DeepSeek："
        f"API Key {'已配置' if settings.deepseek_api_key else '未配置'}；"
        f"模型 `{settings.deepseek_model}`；"
        f"按 `{price.model}` 价格估算"
    )
    if not settings.deepseek_api_key:
        st.warning("未配置 DEEPSEEK_API_KEY，RAG 问答无法调用 DeepSeek。")
        return

    if st.button("刷新 DeepSeek 余额"):
        st.session_state.pop("deepseek_balance", None)
        st.session_state.pop("deepseek_balance_error", None)

    if "deepseek_balance" not in st.session_state and st.session_state.get("deepseek_balance_error"):
        st.warning(f"DeepSeek 余额读取失败：{st.session_state['deepseek_balance_error']}")
        return

    if "deepseek_balance" not in st.session_state:
        try:
            st.session_state.pop("deepseek_balance_error", None)
            st.session_state["deepseek_balance"] = LLMGateway(settings).get_balance()
        except Exception as exc:  # noqa: BLE001 - show user-facing failure
            st.session_state["deepseek_balance_error"] = str(exc)
            st.warning(f"DeepSeek 余额读取失败：{exc}")
            return

    balance = st.session_state.get("deepseek_balance") or {}
    if st.session_state.get("deepseek_balance_error"):
        st.warning(f"DeepSeek 余额读取失败：{st.session_state['deepseek_balance_error']}")
    balance_infos = balance.get("balance_infos") or []
    cols = st.columns(4)
    cols[0].metric("账户可用", "是" if balance.get("is_available") else "否")
    if balance_infos:
        first = balance_infos[0]
        currency = first.get("currency") or "-"
        cols[1].metric("币种", currency)
        cols[2].metric("总余额", str(first.get("total_balance") or "-"))
        cols[3].metric("充值余额", str(first.get("topped_up_balance") or "-"))
        st.caption(
            f"赠送余额：`{first.get('granted_balance') or '-'}`；"
            f"CNY/USD：`{settings.deepseek_cny_per_usd or '未配置'}`"
        )
    else:
        st.info("DeepSeek 未返回 balance_infos。")

    estimates = estimate_balance_tokens(
        balance,
        settings.deepseek_model,
        cny_per_usd=settings.deepseek_cny_per_usd,
    )
    if estimates:
        st.caption("剩余 token 估算")
        st.dataframe(
            [
                {
                    "currency": item.get("currency"),
                    "total_balance": item.get("total_balance"),
                    "model": item.get("model", price.model),
                    "estimate_available": item.get("estimate_available"),
                    "纯输入 cache miss tokens": format_int(item.get("input_cache_miss_tokens")),
                    "纯输入 cache hit tokens": format_int(item.get("input_cache_hit_tokens")),
                    "纯输出 tokens": format_int(item.get("output_tokens")),
                }
                for item in estimates
            ],
            width="stretch",
            hide_index=True,
        )
    st.caption("说明：DeepSeek 官方返回的是余额，不是精确剩余 token；这里按当前模型价格做估算。")


left, right = st.columns([1, 1])

with left:
    st.subheader("本地工作区")
    st.write(f"版本：`{__version__}`")
    st.write(f"知识库：`{paths.library}`")
    st.write(f"数据库：`{paths.database}`")
    st.write(f"Markdown：`{paths.markdown}`")
    st.write(f"索引：`{paths.index}`")

with right:
    st.subheader("阶段 1：最小入库")
    if st.button("创建演示任务"):
        job = repo.create(JobType.ingest_document, {"created_from": "streamlit"})
        st.success(f"已创建任务：{job.id}")
    st.info("当前版本支持 TXT/Markdown 入库、文档级知识条目、自动分块。")

render_runtime_console(repo)

st.subheader("上传 TXT / Markdown")
uploaded_file = st.file_uploader(
    "选择一个 .txt、.md、.markdown、.pdf 或图片文件",
    type=["txt", "md", "markdown", "pdf", "png", "jpg", "jpeg", "bmp", "tif", "tiff", "webp"],
)
if uploaded_file is not None:
    if st.button("提交入库任务", type="primary"):
        try:
            with st.spinner("正在保存原始文件并提交后台任务..."):
                source, asset = ingest_service.add_bytes(
                    filename=uploaded_file.name,
                    content=uploaded_file.getvalue(),
                )
                job = enqueue_document_pipeline(source, asset)
            st.session_state["ingest_message"] = f"已提交入库任务：{job.id}"
            st.rerun()
        except Exception as exc:  # noqa: BLE001 - show user-facing failure
            st.error(f"提交入库任务失败：{exc}")

st.subheader("知识条目")
knowledge_items = knowledge_repo.list(limit=100)
if not knowledge_items:
    st.write("暂无知识条目。上传一个 TXT 或 Markdown 开始。")
else:
    chunk_counts = chunk_repo.counts_by_knowledge_item_ids([item.id for item in knowledge_items])
    st.dataframe(
        [
            {
                "title": item.title,
                "category": item.category.value,
                "chunks": chunk_counts.get(item.id, 0),
                "chunker": item.metadata.get("chunker", ""),
                "summary": item.summary,
                "tags": "、".join(item.tags),
                "markdown_path": str(item.markdown_path or ""),
                "created_at": item.created_at.isoformat(),
            }
            for item in knowledge_items
        ],
        width="stretch",
        hide_index=True,
    )

    st.subheader("知识块预览")
    item_by_id = {item.id: item for item in knowledge_items}
    selected_item_id = st.selectbox(
        "选择知识条目",
        options=list(item_by_id),
        format_func=lambda item_id: item_by_id[item_id].title,
    )
    selected_chunk_count = chunk_counts.get(selected_item_id, 0)
    selected_item = item_by_id[selected_item_id]
    selected_chunks = chunk_repo.list_by_knowledge_item(selected_item_id, limit=10000)
    with st.expander("删除当前知识条目", expanded=False):
        st.warning("删除会同时移除知识条目、知识块和 Chroma 索引；不会删除原始 source/asset 文件。")
        delete_confirm = st.text_input(
            "输入当前知识条目标题以确认删除",
            key=f"delete_confirm_{selected_item_id}",
        )
        delete_disabled = delete_confirm.strip() != selected_item.title
        if st.button(
            "删除知识条目",
            type="secondary",
            disabled=delete_disabled,
            key=f"delete_item_{selected_item_id}",
        ):
            try:
                with st.spinner("正在删除知识条目、知识块和索引..."):
                    result = KnowledgeDeletionService(paths).delete(selected_item_id)
                st.session_state["delete_message"] = (
                    f"已删除《{result.title}》："
                    f"{result.deleted_chunks} 个知识块，"
                    f"{result.deleted_index_entries} 条索引。"
                )
                st.rerun()
            except Exception as exc:  # noqa: BLE001 - show user-facing failure
                st.error(f"删除失败：{exc}")

    rebuild_label = "补建知识块" if selected_chunk_count == 0 else "重新生成知识块"
    rebuild_help = "读取已保存的原始文件，为当前知识条目重新生成 chunks。"
    if st.button(rebuild_label, type="primary" if selected_chunk_count == 0 else "secondary", help=rebuild_help):
        try:
            with st.spinner("正在提交知识块任务..."):
                job = enqueue_rebuild_chunks(selected_item_id)
            st.session_state["chunk_rebuild_message"] = (
                f"已提交知识块任务：{job.id}。任务完成后会自动提交当前条目的索引任务。"
            )
            st.rerun()
        except Exception as exc:  # noqa: BLE001 - show user-facing failure
            st.error(f"提交知识块任务失败：{exc}")

    render_chunk_health(selected_chunks, selected_item.metadata)

    preview_limit = st.number_input("预览数量", min_value=1, max_value=100, value=10, step=1)
    chunks = selected_chunks[: int(preview_limit)]
    if not chunks:
        st.write("这个知识条目还没有生成知识块。")
    else:
        for chunk in chunks:
            heading = " / ".join(chunk.heading_path) if chunk.heading_path else "未命名片段"
            page = chunk.citation.page if chunk.citation and chunk.citation.page is not None else "-"
            with st.expander(f"#{chunk.ordinal} · p.{page} · {heading} · {chunk.char_count} 字"):
                st.text(chunk.text)

    st.subheader("检索测试")
    index_col, search_col = st.columns([1, 2])
    with index_col:
        try:
            retrieval_service = RetrievalService(paths)
            index_status = retrieval_service.embedding_status()
            st.write(f"Embedding：`{index_status['embedding_provider']}`")
            st.write(f"模型：`{index_status['embedding_model']}`")
            st.write(f"当前维度：`{index_status['embedding_dimensions'] or '未探测'}`")
            st.write(f"Ollama 批量/超时：`{index_status.get('embedding_batch_size') or '-'} / {index_status.get('embedding_timeout') or '-'}s`")
            st.write(f"Ollama num_gpu：`{index_status.get('embedding_num_gpu') if index_status.get('embedding_num_gpu') is not None else 'auto'}`")
            st.write(f"Chroma upsert 批量：`{index_status.get('chroma_upsert_batch_size') or '-'}`")
            st.write(f"索引任务超时：`{index_status.get('index_job_timeout_seconds') or '-'}s`")
            st.write(f"已索引 chunks：`{index_status['collection_count']}`")
            metadata = index_status.get("collection_metadata") or {}
            if metadata:
                st.caption(
                    "索引库："
                    f"{metadata.get('embedding_provider', 'unknown')} / "
                    f"{metadata.get('embedding_model', 'unknown')} / "
                    f"{metadata.get('embedding_dimensions', 'unknown')} 维"
                )
        except Exception as exc:  # noqa: BLE001 - show user-facing failure
            st.warning(f"索引状态读取失败：{exc}")
        force_item_index = st.checkbox(
            "强制重建当前条目索引",
            value=False,
            key=f"force_item_index_{selected_item_id}",
            help="默认会续建/补建缺失 chunks；勾选后会先删除当前条目的旧 Chroma 索引。",
        )
        if st.button("续建/补建当前知识条目索引"):
            try:
                with st.spinner("正在提交索引任务..."):
                    job = enqueue_index_knowledge(
                        selected_item_id,
                        force_rebuild=force_item_index,
                    )
                st.session_state["index_message"] = f"已提交索引任务：{job.id}"
                st.rerun()
            except Exception as exc:  # noqa: BLE001 - show user-facing failure
                st.error(f"提交索引任务失败：{exc}")
        force_all_index = st.checkbox(
            "强制清空后重建全部索引",
            value=False,
            key="force_all_index",
            help="默认会续建/补建缺失 chunks，并删除已经不存在的旧 chunk 索引。",
        )
        rebuild_index_label = "强制重建全部索引" if force_all_index else "续建/补建全部索引"
        if st.button(rebuild_index_label):
            try:
                total_chunks = sum(chunk_counts.values())
                st.info(f"将提交重建 {total_chunks} 个 chunks 的后台任务。")
                with st.spinner("正在提交重建索引任务..."):
                    job = enqueue_rebuild_index(force_rebuild=force_all_index)
                st.session_state["index_message"] = f"已提交重建索引任务：{job.id}"
                st.rerun()
            except Exception as exc:  # noqa: BLE001 - show user-facing failure
                st.error(f"提交重建索引任务失败：{exc}")

    with search_col:
        query = st.text_input("搜索问题或关键词")
        top_k = st.number_input("返回数量", min_value=1, max_value=20, value=5, step=1)
        if st.button("搜索知识块", type="primary"):
            try:
                retrieval_service = RetrievalService(paths)
                results = retrieval_service.search(query, top_k=int(top_k))
                if not results:
                    st.write("没有召回结果。")
                for result in results:
                    heading = " / ".join(result.heading_path) if result.heading_path else "未命名片段"
                    with st.expander(f"{result.score:.3f} · {heading} · #{result.ordinal or '-'}"):
                        st.caption(result.file_path or "")
                        st.text(result.text)
            except Exception as exc:  # noqa: BLE001 - show user-facing failure
                st.error(f"搜索失败：{exc}")

st.subheader("RAG 问答")
render_deepseek_account_status()
rag_question = st.text_area("输入一个基于知识库的问题", height=90)
rag_top_k = st.number_input("RAG 召回数量", min_value=1, max_value=20, value=5, step=1)
rag_actions = st.columns([1, 1, 3])
if rag_actions[0].button("提交 RAG 问答任务", type="primary"):
    try:
        job = enqueue_rag_answer(rag_question, top_k=int(rag_top_k))
        st.session_state["rag_message"] = f"已提交 RAG 问答任务：{job.id}"
        st.session_state["active_rag_job_id"] = job.id
        st.rerun()
    except Exception as exc:  # noqa: BLE001 - show user-facing failure
        st.error(f"提交 RAG 任务失败：{exc}")
if rag_actions[1].button("刷新 RAG 结果"):
    st.rerun()

rag_jobs = recent_rag_jobs(repo)
active_rag_job: Job | None = None
active_rag_job_id = st.session_state.get("active_rag_job_id")
if active_rag_job_id:
    try:
        active_rag_job = repo.get(str(active_rag_job_id))
    except Exception:
        active_rag_job = None

if active_rag_job is None and rag_jobs:
    active_rag_job = rag_jobs[0]
    st.session_state["active_rag_job_id"] = active_rag_job.id

if active_rag_job and all(job.id != active_rag_job.id for job in rag_jobs):
    rag_jobs = [active_rag_job, *rag_jobs]

if rag_jobs:
    st.caption("最近 RAG token 消耗")
    st.dataframe(
        [rag_usage_summary(job) for job in rag_jobs],
        width="stretch",
        hide_index=True,
    )
    rag_job_ids = [job.id for job in rag_jobs]
    selected_rag_job_id = st.selectbox(
        "查看历史 RAG 问答",
        options=rag_job_ids,
        index=(
            rag_job_ids.index(active_rag_job.id)
            if active_rag_job and active_rag_job.id in rag_job_ids
            else 0
        ),
        format_func=lambda job_id: rag_job_label(next(job for job in rag_jobs if job.id == job_id)),
    )
    if selected_rag_job_id != st.session_state.get("active_rag_job_id"):
        st.session_state["active_rag_job_id"] = selected_rag_job_id
        active_rag_job = repo.get(selected_rag_job_id)

if active_rag_job:
    render_rag_answer_job(active_rag_job)
else:
    st.info("还没有 RAG 问答结果。提交一个问题后，答案会显示在这里。")
