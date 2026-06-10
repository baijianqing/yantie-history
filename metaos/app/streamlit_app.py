"""Streamlit dashboard for the MetaOS Lite local workspace."""

from __future__ import annotations

import sys
from pathlib import Path

import streamlit as st
import faulthandler
f = open("crash.log", "w")
faulthandler.enable(file=f, all_threads=True)
PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from metaos import __version__
from metaos.core.schemas import JobType
from metaos.ingest.pipeline import DocumentIngestPipeline
from metaos.knowledge.service import KnowledgeService
from metaos.retrieval.service import RetrievalService
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
pipeline = DocumentIngestPipeline(paths)
knowledge_service = KnowledgeService(paths)
retrieval_service = RetrievalService(paths)

if "chunk_rebuild_message" in st.session_state:
    st.success(st.session_state.pop("chunk_rebuild_message"))
if "index_message" in st.session_state:
    st.success(st.session_state.pop("index_message"))

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

st.subheader("上传 TXT / Markdown")
uploaded_file = st.file_uploader(
    "选择一个 .txt、.md 或 .markdown 文件",
    type=["txt", "md", "markdown"],
)
if uploaded_file is not None:
    if st.button("入库并生成知识条目", type="primary"):
        try:
            with st.spinner("正在解析、归档并生成知识块..."):
                result = pipeline.ingest_upload(
                    filename=uploaded_file.name,
                    content=uploaded_file.getvalue(),
                )
            chunk_count = result.knowledge_item.metadata.get(
                "chunk_count",
                chunk_repo.count_by_knowledge_item(result.knowledge_item.id),
            )
            st.success(f"入库完成：{result.knowledge_item.title}")
            st.write(f"分类：`{result.knowledge_item.category.value}`")
            st.write(f"知识块：`{chunk_count}`")
            st.write(f"Markdown：`{result.knowledge_item.markdown_path}`")
        except Exception as exc:  # noqa: BLE001 - show user-facing failure
            st.error(f"入库失败：{exc}")

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
                "summary": item.summary,
                "tags": "、".join(item.tags),
                "markdown_path": str(item.markdown_path or ""),
                "created_at": item.created_at.isoformat(),
            }
            for item in knowledge_items
        ],
        use_container_width=True,
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
    rebuild_label = "补建知识块" if selected_chunk_count == 0 else "重新生成知识块"
    rebuild_help = "读取已保存的原始文件，为当前知识条目重新生成 chunks。"
    if st.button(rebuild_label, type="primary" if selected_chunk_count == 0 else "secondary", help=rebuild_help):
        try:
            with st.spinner("正在补建知识块..."):
                rebuilt_item, rebuilt_count = knowledge_service.rebuild_chunks(selected_item_id)
            st.session_state["chunk_rebuild_message"] = (
                f"已为《{rebuilt_item.title}》生成 {rebuilt_count} 个知识块。"
            )
            st.rerun()
        except Exception as exc:  # noqa: BLE001 - show user-facing failure
            st.error(f"补建失败：{exc}")

    preview_limit = st.number_input("预览数量", min_value=1, max_value=100, value=10, step=1)
    chunks = chunk_repo.list_by_knowledge_item(selected_item_id, limit=int(preview_limit))
    if not chunks:
        st.write("这个知识条目还没有生成知识块。")
    else:
        for chunk in chunks:
            heading = " / ".join(chunk.heading_path) if chunk.heading_path else "未命名片段"
            with st.expander(f"#{chunk.ordinal} · {heading} · {chunk.char_count} 字"):
                st.text(chunk.text)

    st.subheader("检索测试")
    index_col, search_col = st.columns([1, 2])
    with index_col:
        try:
            index_status = retrieval_service.embedding_status()
            st.write(f"Embedding：`{index_status['embedding_provider']}`")
            st.write(f"模型：`{index_status['embedding_model']}`")
            st.write(f"当前维度：`{index_status['embedding_dimensions'] or '未探测'}`")
            st.write(f"Ollama 批量/超时：`{index_status.get('embedding_batch_size') or '-'} / {index_status.get('embedding_timeout') or '-'}s`")
            st.write(f"Chroma upsert 批量：`{index_status.get('chroma_upsert_batch_size') or '-'}`")
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
        if st.button("索引当前知识条目"):
            try:
                progress_bar = st.progress(0)
                progress_text = st.empty()

                def update_progress(done: int, total: int) -> None:
                    progress = 1.0 if total <= 0 else min(1.0, done / total)
                    progress_bar.progress(progress)
                    progress_text.write(f"索引进度：{done}/{total} chunks")

                with st.spinner("正在索引当前知识条目..."):
                    stats = retrieval_service.index_knowledge_item(
                        selected_item_id,
                        progress_callback=update_progress,
                    )
                st.session_state["index_message"] = (
                    f"已索引 {stats.indexed_chunks} 个 chunks，"
                    f"索引库共 {stats.collection_count} 个 chunks，"
                    f"provider={stats.embedding_provider}，维度={stats.embedding_dimensions}。"
                )
                st.rerun()
            except Exception as exc:  # noqa: BLE001 - show user-facing failure
                st.error(f"索引失败：{exc}")
        if st.button("重建全部索引"):
            try:
                total_chunks = sum(chunk_counts.values())
                st.info(f"将重建 {total_chunks} 个 chunks。大文档可能需要几分钟，请保持 Ollama 运行。")
                progress_bar = st.progress(0)
                progress_text = st.empty()

                def update_progress(done: int, total: int) -> None:
                    progress = 1.0 if total <= 0 else min(1.0, done / total)
                    progress_bar.progress(progress)
                    progress_text.write(f"重建进度：{done}/{total} chunks")

                with st.spinner("正在重建全部索引..."):
                    stats = retrieval_service.rebuild_all(progress_callback=update_progress)
                st.session_state["index_message"] = (
                    f"已重建索引：{stats.collection_count} 个 chunks，"
                    f"provider={stats.embedding_provider}，维度={stats.embedding_dimensions}。"
                )
                st.rerun()
            except Exception as exc:  # noqa: BLE001 - show user-facing failure
                import traceback
                st.error(f"重建失败：{exc}")
                st.code(traceback.format_exc())
    

    with search_col:
        query = st.text_input("搜索问题或关键词")
        top_k = st.number_input("返回数量", min_value=1, max_value=20, value=5, step=1)
        if st.button("搜索知识块", type="primary"):
            try:
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

st.subheader("任务列表")
jobs = repo.list(limit=50)
if not jobs:
    st.write("暂无任务。")
else:
    st.dataframe(
        [
            {
                "id": job.id,
                "type": job.type.value,
                "status": job.status.value,
                "progress": job.progress,
                "message": job.message,
                "updated_at": job.updated_at.isoformat(),
            }
            for job in jobs
        ],
        use_container_width=True,
        hide_index=True,
    )
