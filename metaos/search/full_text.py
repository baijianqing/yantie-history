"""SQLite FTS5 full-text search over MetaOS chunks."""

from __future__ import annotations

import re
import sqlite3
from collections.abc import Sequence
from pathlib import Path

from pydantic import BaseModel, Field, field_validator

from metaos.core.schemas import Chunk, Citation


class FullTextSearchFilters(BaseModel):
    knowledge_item_id: str | None = None
    source_id: str | None = None
    asset_id: str | None = None
    file_path: str | None = None

    @field_validator("knowledge_item_id", "source_id", "asset_id", "file_path")
    @classmethod
    def clean_optional_text(cls, value: str | None) -> str | None:
        if value is None:
            return None
        return value.strip() or None

    def as_sql_filters(self) -> tuple[str, list[str]]:
        clauses: list[str] = []
        values: list[str] = []
        for field_name, value in self.model_dump(exclude_none=True).items():
            clauses.append(f"{field_name} = ?")
            values.append(str(value))
        if not clauses:
            return "", []
        return " AND " + " AND ".join(clauses), values


class FullTextSearchResult(BaseModel):
    chunk_id: str
    knowledge_item_id: str
    text: str
    heading_path: list[str] = Field(default_factory=list)
    ordinal: int | None = None
    score: float
    citation: Citation | None = None


def full_text_search(
    query: str,
    *,
    chunks: Sequence[Chunk],
    filters: FullTextSearchFilters | dict | None = None,
    top_k: int = 5,
) -> list[FullTextSearchResult]:
    query = query.strip()
    if not query or not chunks or top_k <= 0:
        return []

    normalized_filters = normalize_filters(filters)
    fts_query = to_fts_query(query)
    with sqlite3.connect(":memory:") as connection:
        connection.row_factory = sqlite3.Row
        create_fts_table(connection)
        chunk_by_id = {chunk.id: chunk for chunk in chunks}
        insert_chunks(connection, chunks)
        filter_sql, filter_values = normalized_filters.as_sql_filters()
        rows = connection.execute(
            f"""
            SELECT
                chunk_id,
                bm25(chunk_fts) AS rank
            FROM chunk_fts
            WHERE chunk_fts MATCH ?{filter_sql}
            ORDER BY rank ASC, ordinal ASC
            LIMIT ?
            """,
            [fts_query, *filter_values, max(1, top_k)],
        ).fetchall()

    return [
        result_from_chunk(chunk_by_id[str(row["chunk_id"])], rank=float(row["rank"]))
        for row in rows
        if str(row["chunk_id"]) in chunk_by_id
    ]


def normalize_filters(filters: FullTextSearchFilters | dict | None) -> FullTextSearchFilters:
    if filters is None:
        return FullTextSearchFilters()
    if isinstance(filters, FullTextSearchFilters):
        return filters
    return FullTextSearchFilters.model_validate(filters)


def create_fts_table(connection: sqlite3.Connection) -> None:
    connection.execute(
        """
        CREATE VIRTUAL TABLE chunk_fts USING fts5(
            chunk_id UNINDEXED,
            knowledge_item_id UNINDEXED,
            source_id UNINDEXED,
            asset_id UNINDEXED,
            file_path UNINDEXED,
            heading_path UNINDEXED,
            ordinal UNINDEXED,
            text,
            tokenize='unicode61'
        )
        """
    )


def insert_chunks(connection: sqlite3.Connection, chunks: Sequence[Chunk]) -> None:
    connection.executemany(
        """
        INSERT INTO chunk_fts (
            chunk_id, knowledge_item_id, source_id, asset_id,
            file_path, heading_path, ordinal, text
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
        [
            (
                chunk.id,
                chunk.knowledge_item_id,
                citation_value(chunk.citation, "source_id"),
                citation_value(chunk.citation, "asset_id"),
                citation_file_path(chunk.citation),
                " / ".join(chunk.heading_path),
                int(chunk.ordinal),
                chunk.text,
            )
            for chunk in chunks
        ],
    )


def result_from_chunk(chunk: Chunk, *, rank: float) -> FullTextSearchResult:
    return FullTextSearchResult(
        chunk_id=chunk.id,
        knowledge_item_id=chunk.knowledge_item_id,
        text=chunk.text,
        heading_path=chunk.heading_path,
        ordinal=chunk.ordinal,
        score=rank_to_score(rank),
        citation=chunk.citation,
    )


def citation_value(citation: Citation | None, field_name: str) -> str:
    if citation is None:
        return ""
    value = getattr(citation, field_name)
    return str(value) if value else ""


def citation_file_path(citation: Citation | None) -> str:
    if citation is None or citation.file_path is None:
        return ""
    return str(Path(citation.file_path))


def to_fts_query(query: str) -> str:
    terms = [term for term in re.split(r"\s+", query.strip()) if term]
    if not terms:
        return '""'
    return " OR ".join(f'"{escape_fts_term(term)}"' for term in terms)


def escape_fts_term(term: str) -> str:
    return term.replace('"', '""')


def rank_to_score(rank: float) -> float:
    if rank < 0:
        return round(abs(rank), 6)
    return round(1 / (1 + rank), 6)
