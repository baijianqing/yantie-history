"""Rule-based knowledge item creation for stage 1."""

from __future__ import annotations

import re
from pathlib import Path

from metaos.core.errors import WorkspaceError
from metaos.core.schemas import Asset, Citation, KnowledgeCategory, KnowledgeItem, Source
from metaos.documents.service import ParsedDocument, parse_text_document
from metaos.knowledge.chunking import DEFAULT_CHUNKER_VERSION, build_chunks
from metaos.workspace.catalog import AssetRepository, ChunkRepository, KnowledgeRepository, SourceRepository
from metaos.workspace.paths import WorkspacePaths, ensure_workspace


CATEGORY_KEYWORDS: dict[KnowledgeCategory, tuple[str, ...]] = {
    KnowledgeCategory.ai: ("ai", "人工智能", "模型", "openai", "deepseek", "anthropic", "agent", "llm"),
    KnowledgeCategory.entrepreneurship: ("创业", "商业模式", "增长", "用户", "付费", "mvp", "市场"),
    KnowledgeCategory.product: ("产品", "需求", "体验", "路线图", "功能", "用户反馈"),
    KnowledgeCategory.technology: ("技术", "架构", "工程", "系统", "服务", "接口", "自动化"),
    KnowledgeCategory.investment: ("投资", "估值", "融资", "资本", "回报", "行业研究"),
    KnowledgeCategory.philosophy: (
        "哲学",
        "孔子",
        "庄子",
        "康德",
        "尼采",
        "苏格拉底",
        "道德经",
        "鬼谷子",
        "黄帝内经",
        "黄帝四经",
        "阴符经",
        "易经",
        "周易",
        "理想国",
        "柏拉图",
    ),
    KnowledgeCategory.history: ("历史", "文明", "战争", "朝代", "帝国", "制度", "资治通鉴"),
    KnowledgeCategory.economics: ("经济", "货币", "通胀", "价格", "供需", "市场"),
    KnowledgeCategory.computer_science: ("计算机", "算法", "数据库", "编程", "python", "代码", "软件"),
    KnowledgeCategory.mathematics: ("数学", "概率", "统计", "代数", "几何", "微积分"),
}


def plain_lines(text: str) -> list[str]:
    lines: list[str] = []
    for line in text.splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or stripped.startswith("<!-- metaos:page="):
            continue
        lines.append(stripped)
    return lines


def summarize_text(text: str, limit: int = 260) -> str:
    joined = " ".join(plain_lines(text))
    joined = re.sub(r"\s+", " ", joined).strip()
    if len(joined) <= limit:
        return joined
    return joined[:limit].rstrip() + "..."


def classify_text(title: str, text: str) -> KnowledgeCategory:
    haystack = f"{title}\n{text}".lower()
    scores: dict[KnowledgeCategory, int] = {}
    for category, keywords in CATEGORY_KEYWORDS.items():
        scores[category] = sum(haystack.count(keyword.lower()) for keyword in keywords)
    best_category, best_score = max(scores.items(), key=lambda item: item[1])
    if best_score <= 0:
        return KnowledgeCategory.uncategorized
    return best_category


def infer_tags(title: str, text: str, category: KnowledgeCategory) -> list[str]:
    tags = []
    if category != KnowledgeCategory.uncategorized:
        tags.append(category.value)
    haystack = f"{title}\n{text}".lower()
    for keyword in CATEGORY_KEYWORDS.get(category, ()):
        if keyword.lower() in haystack and keyword not in tags:
            tags.append(keyword)
        if len(tags) >= 6:
            break
    return tags


def markdown_filename(title: str, item_id: str) -> str:
    safe_title = re.sub(r'[<>:"/\\|?*\x00-\x1f]', "_", title).strip() or "untitled"
    return f"{item_id}_{safe_title[:80]}.md"


def build_standard_markdown(
    *,
    source: Source,
    asset: Asset,
    item: KnowledgeItem,
    document: ParsedDocument,
) -> str:
    tags = "、".join(item.tags) if item.tags else "未标注"
    summary = item.summary or "暂无摘要"
    return "\n".join(
        [
            f"# {item.title}",
            "",
            f"> 分类：{item.category.value}",
            f"> 标签：{tags}",
            f"> 来源：{source.title or source.uri}",
            f"> 原始文件：{asset.path}",
            "",
            "## 摘要",
            "",
            summary,
            "",
            "## 原文",
            "",
            document.text,
            "",
        ]
    )


class KnowledgeService:
    def __init__(self, paths: WorkspacePaths | None = None):
        self.paths = paths or ensure_workspace()
        self.repository = KnowledgeRepository(self.paths.database)
        self.chunk_repository = ChunkRepository(self.paths.database)
        self.asset_repository = AssetRepository(self.paths.database)
        self.source_repository = SourceRepository(self.paths.database)

    def create_from_document(
        self,
        *,
        source: Source,
        asset: Asset,
        document: ParsedDocument,
    ) -> KnowledgeItem:
        category = classify_text(document.title, document.text)
        summary = summarize_text(document.text)
        item = KnowledgeItem(
            title=document.title,
            summary=summary,
            category=category,
            tags=infer_tags(document.title, document.text, category),
            citations=[
                Citation(
                    source_id=source.id,
                    asset_id=asset.id,
                    file_path=asset.path,
                    excerpt=summary[:160] if summary else None,
                )
            ],
            metadata={
                "source_id": source.id,
                "asset_id": asset.id,
                "source_uri": source.uri,
                "parser": "text_v1",
            },
        )
        chunks = build_chunks(
            knowledge_item_id=item.id,
            source=source,
            asset=asset,
            document=document,
        )
        item.metadata["chunk_count"] = len(chunks)
        item.metadata["chunker"] = DEFAULT_CHUNKER_VERSION
        markdown_path = self.paths.markdown / markdown_filename(item.title, item.id)
        item.markdown_path = markdown_path
        markdown_path.write_text(
            build_standard_markdown(source=source, asset=asset, item=item, document=document),
            encoding="utf-8",
            newline="\n",
        )
        self.repository.add(item)
        self.chunk_repository.delete_by_knowledge_item(item.id)
        self.chunk_repository.add_many(chunks)
        return item

    def rebuild_chunks(self, item_id: str) -> tuple[KnowledgeItem, int]:
        item = self.repository.get(item_id)
        asset_id = item.metadata.get("asset_id")
        source_id = item.metadata.get("source_id")
        if not asset_id and item.citations:
            asset_id = item.citations[0].asset_id
        if not source_id and item.citations:
            source_id = item.citations[0].source_id
        if not asset_id:
            raise WorkspaceError(f"Knowledge item has no asset_id: {item_id}")

        asset = self.asset_repository.get(str(asset_id))
        if not asset.path.exists():
            raise WorkspaceError(f"Original asset file not found: {asset.path}")

        source = self.source_repository.get(str(source_id or asset.source_id))
        parsed_document = parse_text_document(asset)
        document = ParsedDocument(
            title=item.title,
            text=parsed_document.text,
            source_path=parsed_document.source_path,
            extension=parsed_document.extension,
        )
        chunks = build_chunks(
            knowledge_item_id=item.id,
            source=source,
            asset=asset,
            document=document,
        )

        self.chunk_repository.delete_by_knowledge_item(item.id)
        self.chunk_repository.add_many(chunks)
        item.metadata["chunk_count"] = len(chunks)
        item.metadata["chunker"] = DEFAULT_CHUNKER_VERSION
        self.repository.add(item)
        return item, len(chunks)
