"""Local embedding providers for retrieval indexing."""

from __future__ import annotations

import hashlib
import json
import math
import re
from dataclasses import dataclass
from typing import Any
from typing import Protocol
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from metaos.core.config import Settings, get_settings
from metaos.core.errors import ConfigurationError, EmbeddingProviderError


CJK_RE = re.compile(r"[\u3400-\u4dbf\u4e00-\u9fff\uf900-\ufaff]")
LATIN_RE = re.compile(r"[A-Za-z0-9_]+")


class EmbeddingProvider(Protocol):
    name: str
    model: str

    @property
    def dimensions(self) -> int | None:
        """Return known vector dimensions, or None before the first embedding call."""

    def embed(self, texts: list[str]) -> list[list[float]]:
        """Return one vector per text."""


@dataclass(frozen=True)
class HashEmbeddingProvider:
    """Small deterministic embedding for local retrieval smoke tests.

    This is not a semantic model. It is intentionally dependency-free and is
    meant to make the Chroma pipeline usable before a stronger embedding model
    is selected.
    """

    dimensions: int = 384
    name: str = "hash-embedding-v1"
    model: str = "hash"

    def embed(self, texts: list[str]) -> list[list[float]]:
        return [self.embed_one(text) for text in texts]

    def embed_one(self, text: str) -> list[float]:
        vector = [0.0] * self.dimensions
        for token in tokenize(text):
            index, sign = hash_token(token, self.dimensions)
            vector[index] += sign
        norm = math.sqrt(sum(value * value for value in vector))
        if norm <= 0:
            return vector
        return [value / norm for value in vector]


def tokenize(text: str) -> list[str]:
    lowered = text.lower()
    tokens = LATIN_RE.findall(lowered)
    cjk_chars = CJK_RE.findall(lowered)
    tokens.extend(cjk_chars)
    tokens.extend(
        "".join(pair)
        for pair in zip(cjk_chars, cjk_chars[1:])
    )
    return tokens


def hash_token(token: str, dimensions: int) -> tuple[int, float]:
    digest = hashlib.blake2b(token.encode("utf-8"), digest_size=8).digest()
    number = int.from_bytes(digest, "big")
    return number % dimensions, 1.0 if number & 1 else -1.0


class OllamaEmbeddingProvider:
    def __init__(
        self,
        *,
        base_url: str = "http://localhost:11434",
        model: str = "bge-m3",
        timeout: float = 300,
        batch_size: int = 8,
    ):
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.timeout = timeout
        self.batch_size = max(1, batch_size)
        self.name = f"ollama-{model}"
        self._dimensions: int | None = None

    @property
    def dimensions(self) -> int | None:
        return self._dimensions

    def embed(self, texts: list[str]) -> list[list[float]]:
        if not texts:
            return []
        all_embeddings: list[list[float]] = []
        for start in range(0, len(texts), self.batch_size):
            batch = texts[start : start + self.batch_size]
            all_embeddings.extend(self._embed_batch(batch))
        return all_embeddings

    def _embed_batch(self, texts: list[str]) -> list[list[float]]:
        payload = {
            "model": self.model,
            "input": texts,
        }
        response = self._post_json("/api/embed", payload)
        embeddings = parse_ollama_embeddings(response)
        if len(embeddings) != len(texts):
            raise EmbeddingProviderError(
                f"Ollama returned {len(embeddings)} embeddings for {len(texts)} texts."
            )
        dimensions = {len(embedding) for embedding in embeddings}
        if len(dimensions) != 1:
            raise EmbeddingProviderError("Ollama returned embeddings with inconsistent dimensions.")
        dimensions_value = dimensions.pop()
        if self._dimensions is not None and self._dimensions != dimensions_value:
            raise EmbeddingProviderError(
                f"Ollama embedding dimensions changed from {self._dimensions} to {dimensions_value}."
            )
        self._dimensions = dimensions_value
        return embeddings

    def _post_json(self, path: str, payload: dict[str, Any]) -> dict[str, Any]:
        url = f"{self.base_url}{path}"
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        request = Request(
            url,
            data=body,
            method="POST",
            headers={"Content-Type": "application/json"},
        )
        try:
            with urlopen(request, timeout=self.timeout) as response:
                return json.loads(response.read().decode("utf-8"))
        except HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="replace")
            raise EmbeddingProviderError(
                f"Ollama embedding request failed with HTTP {exc.code}: {detail}"
            ) from exc
        except URLError as exc:
            raise EmbeddingProviderError(
                f"Cannot connect to Ollama at {self.base_url}. "
                "Make sure Ollama is running and bge-m3 is installed."
            ) from exc
        except TimeoutError as exc:
            raise EmbeddingProviderError(
                f"Ollama embedding request timed out after {self.timeout} seconds "
                f"(model={self.model}, batch_size={self.batch_size}). "
                "Try lowering OLLAMA_EMBED_BATCH_SIZE or increasing OLLAMA_EMBED_TIMEOUT."
            ) from exc
        except json.JSONDecodeError as exc:
            raise EmbeddingProviderError("Ollama returned invalid JSON.") from exc


def parse_ollama_embeddings(response: dict[str, Any]) -> list[list[float]]:
    raw_embeddings = response.get("embeddings")
    if raw_embeddings is None and "embedding" in response:
        raw_embeddings = [response["embedding"]]
    if not isinstance(raw_embeddings, list) or not raw_embeddings:
        raise EmbeddingProviderError("Ollama response did not contain embeddings.")

    embeddings: list[list[float]] = []
    for embedding in raw_embeddings:
        if not isinstance(embedding, list):
            raise EmbeddingProviderError("Ollama returned a malformed embedding.")
        embeddings.append([float(value) for value in embedding])
    return embeddings


def make_embedding_provider(settings: Settings | None = None) -> EmbeddingProvider:
    settings = settings or get_settings()
    provider = settings.embedding_provider.strip().lower()
    if provider == "hash":
        return HashEmbeddingProvider()
    if provider == "ollama":
        return OllamaEmbeddingProvider(
            base_url=settings.ollama_base_url,
            model=settings.ollama_embed_model,
            timeout=settings.ollama_embed_timeout,
            batch_size=settings.ollama_embed_batch_size,
        )
    raise ConfigurationError(f"Unsupported EMBEDDING_PROVIDER: {settings.embedding_provider}")
