"""Embedding provider abstraction.

The default provider uses sentence-transformers, but the model is loaded
lazily on first use so that importing this module never downloads a model.
Tests inject a fake provider instead of touching the real one.
"""
from typing import List, Protocol

from services.embedding_config import get_dimension, get_model_name


class EmbeddingProvider(Protocol):
    """Minimal contract a provider must satisfy."""

    @property
    def dimension(self) -> int: ...

    @property
    def model_name(self) -> str: ...

    def embed(self, texts: List[str]) -> List[List[float]]:
        """Return one vector per input text, in the same order."""
        ...


class SentenceTransformerProvider:
    """Local sentence-transformers provider (lazy model loading)."""

    def __init__(self, model_name: str = None, dimension: int = None):
        self._model_name = model_name or get_model_name()
        self._dimension = dimension or get_dimension()
        self._model = None

    @property
    def dimension(self) -> int:
        return self._dimension

    @property
    def model_name(self) -> str:
        return self._model_name

    def _load(self):
        if self._model is None:
            from sentence_transformers import SentenceTransformer
            self._model = SentenceTransformer(self._model_name)
        return self._model

    def embed(self, texts: List[str]) -> List[List[float]]:
        if not texts:
            return []
        model = self._load()
        # normalize_embeddings=True so cosine similarity is a plain dot product
        vectors = model.encode(
            texts,
            normalize_embeddings=True,
            convert_to_numpy=True,
            show_progress_bar=False,
        )
        return [vector.tolist() for vector in vectors]


_default_provider = None


def get_provider() -> EmbeddingProvider:
    """Return the process-wide provider, creating it on first use."""
    global _default_provider
    if _default_provider is None:
        _default_provider = SentenceTransformerProvider()
    return _default_provider


def set_provider(provider) -> None:
    """Override the provider (used by tests and future configuration)."""
    global _default_provider
    _default_provider = provider
