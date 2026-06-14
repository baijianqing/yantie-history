"""Single-turn RAG answer generation."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from metaos.llm_gateway.client import ChatMessage, LLMGateway
from metaos.llm_gateway.pricing import estimate_usage_cost
from metaos.retrieval.service import RetrievalService, SearchResult
from metaos.workspace.paths import WorkspacePaths, ensure_workspace


@dataclass(frozen=True)
class RagAnswer:
    answer: str
    citations: list[dict[str, Any]]
    retrieved_chunks: list[dict[str, Any]]
    llm_usage: dict[str, Any] | None = None
    llm_model: str | None = None
    llm_cost_estimate: dict[str, Any] | None = None

    def as_dict(self) -> dict[str, Any]:
        return {
            "answer": self.answer,
            "citations": self.citations,
            "retrieved_chunks": self.retrieved_chunks,
            "llm_usage": self.llm_usage or {},
            "llm_model": self.llm_model,
            "llm_cost_estimate": self.llm_cost_estimate or {},
        }


class RagService:
    def __init__(
        self,
        paths: WorkspacePaths | None = None,
        retrieval: RetrievalService | None = None,
        llm: LLMGateway | None = None,
    ):
        self.paths = paths or ensure_workspace()
        self.retrieval = retrieval or RetrievalService(self.paths)
        self.llm = llm or LLMGateway()

    def answer(self, question: str, top_k: int = 5) -> RagAnswer:
        question = question.strip()
        if not question:
            raise ValueError("问题不能为空。")
        results = self.retrieval.search(question, top_k=top_k)
        if not results:
            return RagAnswer(
                answer="资料不足，无法基于当前知识库回答。",
                citations=[],
                retrieved_chunks=[],
                llm_usage={},
                llm_model=None,
                llm_cost_estimate={},
            )
        prompt = build_prompt(question, results)
        chat_result = self.llm.chat(
            [
                ChatMessage(
                    role="system",
                    content=(
                        "你是 MetaOS Lite 的研究助手。只能依据用户知识库片段回答。"
                        "如果片段不足以回答，必须明确说资料不足。"
                        "回答要简洁，并在关键结论后标注引用编号，如 [1]。"
                    ),
                ),
                ChatMessage(role="user", content=prompt),
            ],
            temperature=0.2,
        )
        return RagAnswer(
            answer=chat_result.content,
            citations=[citation_for_result(index, result) for index, result in enumerate(results, start=1)],
            retrieved_chunks=[result.as_dict() for result in results],
            llm_usage=chat_result.usage,
            llm_model=chat_result.model,
            llm_cost_estimate=estimate_usage_cost(chat_result.model, chat_result.usage),
        )


def build_prompt(question: str, results: list[SearchResult]) -> str:
    context_blocks = []
    for index, result in enumerate(results, start=1):
        heading = " / ".join(result.heading_path) if result.heading_path else "未命名片段"
        context_blocks.append(
            "\n".join(
                [
                    f"[{index}] {heading}",
                    f"来源文件：{result.file_path or '未知'}",
                    result.text,
                ]
            )
        )
    return "\n\n".join(
        [
            f"问题：{question}",
            "资料片段：",
            "\n\n---\n\n".join(context_blocks),
            "请只依据以上资料回答，并给出引用编号。",
        ]
    )


def citation_for_result(index: int, result: SearchResult) -> dict[str, Any]:
    return {
        "index": index,
        "chunk_id": result.chunk_id,
        "knowledge_item_id": result.knowledge_item_id,
        "heading_path": result.heading_path,
        "ordinal": result.ordinal,
        "score": result.score,
        "file_path": result.file_path,
    }
