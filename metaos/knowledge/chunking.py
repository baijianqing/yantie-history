"""Document chunking for retrieval-ready knowledge items."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Literal

from metaos.core.schemas import Asset, Chunk, Citation, Source
from metaos.documents.service import ParsedDocument


ChunkerVersion = Literal["v1", "v2"]
DEFAULT_CHUNKER_VERSION: ChunkerVersion = "v2"

HEADING_RE = re.compile(r"^(#{1,6})\s+(.+?)\s*#*\s*$")
PAGE_MARKER_RE = re.compile(r"^\s*<!--\s*metaos:page=(\d+)\s*-->\s*$")
PAGE_HEADING_RE = re.compile(r"^第\s*(\d+)\s*页$")
CODE_FENCE_RE = re.compile(r"^\s*(`{3,}|~{3,})")
CJK_RE = re.compile(r"[\u3400-\u4dbf\u4e00-\u9fff\uf900-\ufaff]+")
LATIN_RE = re.compile(r"[A-Za-z0-9_]+")
TOKEN_RE = re.compile(r"[\u3400-\u4dbf\u4e00-\u9fff\uf900-\ufaff]+|[A-Za-z0-9_]+|[^\s]")

V1_TARGET_CHARS = 1600
V1_HARD_MAX_CHARS = 2200

V2_TARGET_TOKENS = 700
V2_MAX_TOKENS = 1000
V2_OVERLAP_TOKENS = 100


@dataclass(frozen=True)
class DocumentSection:
    heading_path: list[str]
    text: str


@dataclass(frozen=True)
class MarkdownBlock:
    kind: str
    text: str
    splittable: bool = True
    page: int | None = None


@dataclass(frozen=True)
class ChunkCandidate:
    text: str
    page: int | None = None


@dataclass(frozen=True)
class ChunkerV2Settings:
    target_tokens: int = V2_TARGET_TOKENS
    max_tokens: int = V2_MAX_TOKENS
    overlap_tokens: int = V2_OVERLAP_TOKENS
    inject_heading_context: bool = True


def normalize_chunk_text(text: str) -> str:
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    text = re.sub(r"[ \t]+\n", "\n", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def normalize_heading(text: str) -> str:
    text = re.sub(r"\s+", " ", text).strip()
    return text[:120]


def parse_page_marker(line: str) -> int | None:
    match = PAGE_MARKER_RE.match(line.strip())
    return int(match.group(1)) if match else None


def parse_page_heading(heading: str) -> int | None:
    match = PAGE_HEADING_RE.match(heading.strip())
    return int(match.group(1)) if match else None


def page_marker(page: int) -> str:
    return f"<!-- metaos:page={page} -->"


def estimate_tokens(text: str) -> int:
    total = 0
    for part in TOKEN_RE.findall(text):
        if CJK_RE.fullmatch(part):
            total += len(part)
        elif LATIN_RE.fullmatch(part):
            total += max(1, (len(part) + 3) // 4)
        else:
            total += 1
    return total


def detect_fence(line: str) -> tuple[str, int] | None:
    match = CODE_FENCE_RE.match(line)
    if not match:
        return None
    marker = match.group(1)
    return marker[0], len(marker)


def split_into_sections(document: ParsedDocument) -> list[DocumentSection]:
    if document.extension not in {".md", ".markdown"}:
        text = normalize_chunk_text(document.text)
        return [DocumentSection([document.title], text)] if text else []

    sections: list[DocumentSection] = []
    heading_stack: list[tuple[int, str]] = []
    current_lines: list[str] = []
    current_path = [document.title]
    in_fence = False
    fence_char = ""
    fence_len = 0

    def flush_current() -> None:
        section_text = normalize_chunk_text("\n".join(current_lines))
        if section_text:
            sections.append(DocumentSection(current_path.copy(), section_text))

    for line in document.text.splitlines():
        fence = detect_fence(line)
        if fence:
            char, length = fence
            current_lines.append(line)
            if in_fence and char == fence_char and length >= fence_len:
                in_fence = False
                fence_char = ""
                fence_len = 0
            elif not in_fence:
                in_fence = True
                fence_char = char
                fence_len = length
            continue

        match = HEADING_RE.match(line.strip()) if not in_fence else None
        if not match:
            current_lines.append(line)
            continue

        heading = normalize_heading(match.group(2))
        if not heading:
            current_lines.append(line)
            continue
        page = parse_page_heading(heading)
        if page is not None:
            current_lines.append(page_marker(page))
            continue

        flush_current()
        level = len(match.group(1))
        heading_stack[:] = [(old_level, title) for old_level, title in heading_stack if old_level < level]
        heading_stack.append((level, heading))
        current_path = [title for _, title in heading_stack] or [document.title]
        current_lines = []

    flush_current()

    if sections:
        return sections

    text = normalize_chunk_text(document.text)
    return [DocumentSection([document.title], text)] if text else []


def split_long_text(
    text: str,
    target_chars: int = V1_TARGET_CHARS,
    hard_max_chars: int = V1_HARD_MAX_CHARS,
) -> list[str]:
    text = normalize_chunk_text(text)
    if not text:
        return []
    if len(text) <= hard_max_chars:
        return [text]

    chunks: list[str] = []
    buffer: list[str] = []
    paragraphs = [paragraph.strip() for paragraph in re.split(r"\n\s*\n", text) if paragraph.strip()]

    def flush_buffer() -> None:
        if buffer:
            chunks.append(normalize_chunk_text("\n\n".join(buffer)))
            buffer.clear()

    for paragraph in paragraphs:
        if len(paragraph) > hard_max_chars:
            flush_buffer()
            start = 0
            while start < len(paragraph):
                chunks.append(paragraph[start : start + hard_max_chars].strip())
                start += hard_max_chars
            continue

        candidate = "\n\n".join([*buffer, paragraph]) if buffer else paragraph
        if buffer and len(candidate) > target_chars:
            flush_buffer()
        buffer.append(paragraph)

    flush_buffer()
    return [chunk for chunk in chunks if chunk]


def is_table_row(line: str) -> bool:
    stripped = line.strip()
    return stripped.count("|") >= 2


def is_table_separator(line: str) -> bool:
    stripped = line.strip().strip("|")
    parts = [part.strip() for part in stripped.split("|")]
    return len(parts) >= 2 and all(re.fullmatch(r":?-{3,}:?", part or "") for part in parts)


def split_markdown_blocks(text: str) -> list[MarkdownBlock]:
    lines = text.splitlines()
    blocks: list[MarkdownBlock] = []
    paragraph: list[str] = []
    current_page: int | None = None
    index = 0

    def flush_paragraph() -> None:
        block_text = normalize_chunk_text("\n".join(paragraph))
        if block_text:
            blocks.append(MarkdownBlock("paragraph", block_text, True, current_page))
        paragraph.clear()

    while index < len(lines):
        line = lines[index]
        page = parse_page_marker(line)
        if page is not None:
            flush_paragraph()
            current_page = page
            index += 1
            continue

        fence = detect_fence(line)
        if fence:
            flush_paragraph()
            char, length = fence
            code_lines = [line]
            index += 1
            while index < len(lines):
                code_lines.append(lines[index])
                closing = detect_fence(lines[index])
                if closing and closing[0] == char and closing[1] >= length:
                    index += 1
                    break
                index += 1
            blocks.append(MarkdownBlock("code", "\n".join(code_lines).strip(), False, current_page))
            continue

        if is_table_row(line) and index + 1 < len(lines) and is_table_separator(lines[index + 1]):
            flush_paragraph()
            table_lines = [line, lines[index + 1]]
            index += 2
            while index < len(lines) and is_table_row(lines[index]):
                table_lines.append(lines[index])
                index += 1
            blocks.append(MarkdownBlock("table", "\n".join(table_lines).strip(), False, current_page))
            continue

        if not line.strip():
            flush_paragraph()
            index += 1
            continue

        paragraph.append(line)
        index += 1

    flush_paragraph()
    return blocks


def split_plain_blocks(text: str) -> list[MarkdownBlock]:
    blocks = []
    for paragraph in re.split(r"\n\s*\n", text):
        block_text = normalize_chunk_text(paragraph)
        if block_text:
            blocks.append(MarkdownBlock("paragraph", block_text, True))
    return blocks


def heading_context(heading_path: list[str], enabled: bool = True) -> str:
    if not enabled or not heading_path:
        return ""
    return "# " + " / ".join(heading_path)


def chunk_text_from_blocks(
    heading_path: list[str],
    blocks: list[MarkdownBlock],
    settings: ChunkerV2Settings,
) -> str:
    body = normalize_chunk_text("\n\n".join(block.text for block in blocks))
    if not body:
        return ""
    context = heading_context(heading_path, settings.inject_heading_context)
    return f"{context}\n\n{body}" if context else body


def first_page_from_blocks(blocks: list[MarkdownBlock]) -> int | None:
    for block in blocks:
        if block.page is not None:
            return block.page
    return None


def find_token_limited_end(text: str, start: int, token_limit: int) -> int:
    low = start + 1
    high = len(text)
    best = low
    while low <= high:
        mid = (low + high) // 2
        if estimate_tokens(text[start:mid]) <= token_limit:
            best = mid
            low = mid + 1
        else:
            high = mid - 1
    return max(best, start + 1)


def refine_split_end(text: str, start: int, end: int) -> int:
    if end >= len(text):
        return len(text)
    minimum = start + max(1, int((end - start) * 0.65))
    best_end = -1
    for separator in ("\n\n", "\n", "。", "！", "？", ".", "!", "?", "；", ";", "，", ",", " "):
        position = text.rfind(separator, start, end)
        candidate_end = position + len(separator)
        if position >= minimum and candidate_end > best_end:
            best_end = candidate_end
    return best_end if best_end > start else end


def find_overlap_start(text: str, start: int, end: int, token_limit: int) -> int:
    if token_limit <= 0:
        return end
    low = start
    high = end
    best = end
    while low <= high:
        mid = (low + high) // 2
        if estimate_tokens(text[mid:end]) <= token_limit:
            best = mid
            high = mid - 1
        else:
            low = mid + 1
    return best


def split_text_by_token_limit(text: str, token_limit: int, overlap_tokens: int) -> list[str]:
    text = normalize_chunk_text(text)
    if not text:
        return []
    if estimate_tokens(text) <= token_limit:
        return [text]

    pieces: list[str] = []
    start = 0
    while start < len(text):
        end = find_token_limited_end(text, start, token_limit)
        end = refine_split_end(text, start, end)
        piece = text[start:end].strip()
        if piece:
            pieces.append(piece)
        if end >= len(text):
            break
        next_start = find_overlap_start(text, start, end, overlap_tokens)
        start = next_start if next_start > start else end
    return pieces


def tail_text_by_tokens(text: str, token_limit: int) -> str:
    text = text.strip()
    if not text or estimate_tokens(text) <= token_limit:
        return text
    start = find_overlap_start(text, 0, len(text), token_limit)
    return text[start:].strip()


def expand_oversized_block(
    block: MarkdownBlock,
    content_token_limit: int,
    overlap_tokens: int,
) -> list[MarkdownBlock]:
    if estimate_tokens(block.text) <= content_token_limit or not block.splittable:
        return [block]
    return [
        MarkdownBlock(block.kind, piece, block.splittable, block.page)
        for piece in split_text_by_token_limit(block.text, content_token_limit, overlap_tokens)
    ]


def trailing_overlap_blocks(blocks: list[MarkdownBlock], settings: ChunkerV2Settings) -> list[MarkdownBlock]:
    if settings.overlap_tokens <= 0:
        return []

    selected: list[MarkdownBlock] = []
    total = 0
    for block in reversed(blocks):
        block_tokens = estimate_tokens(block.text)
        if block.kind in {"code", "table"} and block_tokens > settings.overlap_tokens:
            continue
        if block_tokens > settings.overlap_tokens * 2:
            if not selected and block.splittable:
                tail = tail_text_by_tokens(block.text, settings.overlap_tokens)
                if tail:
                    selected.append(MarkdownBlock(block.kind, tail, block.splittable, block.page))
            break
        selected.append(block)
        total += block_tokens
        if total >= settings.overlap_tokens:
            break
    return list(reversed(selected))


def split_blocks_v2(
    blocks: list[MarkdownBlock],
    heading_path: list[str],
    settings: ChunkerV2Settings,
) -> list[ChunkCandidate]:
    context_tokens = estimate_tokens(heading_context(heading_path, settings.inject_heading_context))
    content_token_limit = max(200, settings.max_tokens - context_tokens - 2)
    expanded_blocks: list[MarkdownBlock] = []
    for block in blocks:
        expanded_blocks.extend(
            expand_oversized_block(block, content_token_limit, settings.overlap_tokens)
        )

    chunk_texts: list[ChunkCandidate] = []
    current: list[MarkdownBlock] = []
    added_since_flush = False

    def flush_current() -> None:
        nonlocal current, added_since_flush
        chunk_text = chunk_text_from_blocks(heading_path, current, settings)
        if chunk_text:
            chunk_texts.append(ChunkCandidate(chunk_text, first_page_from_blocks(current)))
        current = trailing_overlap_blocks(current, settings)
        added_since_flush = False

    for index, block in enumerate(expanded_blocks):
        if estimate_tokens(block.text) > content_token_limit and not block.splittable:
            if current and added_since_flush:
                flush_current()
            chunk_text = chunk_text_from_blocks(heading_path, [block], settings)
            if chunk_text:
                chunk_texts.append(ChunkCandidate(chunk_text, block.page))
            current = trailing_overlap_blocks([block], settings)
            added_since_flush = False
            continue

        candidate = chunk_text_from_blocks(heading_path, [*current, block], settings)
        if current and estimate_tokens(candidate) > settings.max_tokens:
            if added_since_flush:
                flush_current()
            else:
                current = []
            candidate = chunk_text_from_blocks(heading_path, [*current, block], settings)
            if current and estimate_tokens(candidate) > settings.max_tokens:
                current = []

        current.append(block)
        added_since_flush = True
        current_text = chunk_text_from_blocks(heading_path, current, settings)
        if estimate_tokens(current_text) >= settings.target_tokens and index < len(expanded_blocks) - 1:
            flush_current()

    if current and added_since_flush:
        chunk_text = chunk_text_from_blocks(heading_path, current, settings)
        if chunk_text:
            chunk_texts.append(ChunkCandidate(chunk_text, first_page_from_blocks(current)))

    return chunk_texts


def build_chunks_v1(
    *,
    knowledge_item_id: str,
    source: Source,
    asset: Asset,
    document: ParsedDocument,
) -> list[Chunk]:
    chunks: list[Chunk] = []
    ordinal = 0
    for section in split_into_sections(document):
        for chunk_text in split_long_text(section.text):
            ordinal += 1
            chunks.append(
                make_chunk(
                    knowledge_item_id=knowledge_item_id,
                    source=source,
                    asset=asset,
                    heading_path=section.heading_path,
                    ordinal=ordinal,
                    chunk_text=chunk_text,
                )
            )
    return chunks


def build_chunks_v2(
    *,
    knowledge_item_id: str,
    source: Source,
    asset: Asset,
    document: ParsedDocument,
    settings: ChunkerV2Settings | None = None,
) -> list[Chunk]:
    settings = settings or ChunkerV2Settings()
    is_markdown = document.extension in {".md", ".markdown"}
    chunks: list[Chunk] = []
    ordinal = 0
    for section in split_into_sections(document):
        blocks = split_markdown_blocks(section.text) if is_markdown else split_plain_blocks(section.text)
        for candidate in split_blocks_v2(blocks, section.heading_path, settings):
            ordinal += 1
            chunks.append(
                make_chunk(
                    knowledge_item_id=knowledge_item_id,
                    source=source,
                    asset=asset,
                    heading_path=section.heading_path,
                    ordinal=ordinal,
                    chunk_text=candidate.text,
                    page=candidate.page,
                )
            )
    return chunks


def make_chunk(
    *,
    knowledge_item_id: str,
    source: Source,
    asset: Asset,
    heading_path: list[str],
    ordinal: int,
    chunk_text: str,
    page: int | None = None,
) -> Chunk:
    return Chunk(
        knowledge_item_id=knowledge_item_id,
        text=chunk_text,
        heading_path=heading_path,
        ordinal=ordinal,
        char_count=len(chunk_text),
        citation=Citation(
            source_id=source.id,
            asset_id=asset.id,
            file_path=asset.path,
            page=page,
            excerpt=chunk_text[:160],
        ),
    )


def build_chunks(
    *,
    knowledge_item_id: str,
    source: Source,
    asset: Asset,
    document: ParsedDocument,
    version: ChunkerVersion = DEFAULT_CHUNKER_VERSION,
) -> list[Chunk]:
    if version == "v1":
        return build_chunks_v1(
            knowledge_item_id=knowledge_item_id,
            source=source,
            asset=asset,
            document=document,
        )
    return build_chunks_v2(
        knowledge_item_id=knowledge_item_id,
        source=source,
        asset=asset,
        document=document,
    )
