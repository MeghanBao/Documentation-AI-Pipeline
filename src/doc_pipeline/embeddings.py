"""Sentence embedding using sentence-transformers (fully offline after first download)."""
from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from sentence_transformers import SentenceTransformer

_DEFAULT_MODEL = "paraphrase-multilingual-MiniLM-L12-v2"


def _load_model(model_name: str) -> "SentenceTransformer":
    """Load (or retrieve from cache) a SentenceTransformer model.

    Kept as a separate function so tests can patch it without importing
    sentence_transformers at module level.
    """
    from sentence_transformers import SentenceTransformer  # noqa: PLC0415

    return SentenceTransformer(model_name)


_model_cache: dict[str, "SentenceTransformer"] = {}


def get_model(model_name: str = _DEFAULT_MODEL) -> "SentenceTransformer":
    """Return a cached SentenceTransformer instance."""
    if model_name not in _model_cache:
        _model_cache[model_name] = _load_model(model_name)
    return _model_cache[model_name]


def encode(texts: list[str], model_name: str = _DEFAULT_MODEL) -> list[list[float]]:
    """Encode a list of strings into embedding vectors.

    Returns a list of plain Python float lists (JSON-serialisable).
    """
    if not texts:
        return []
    model = get_model(model_name)
    vectors = model.encode(texts, show_progress_bar=False, convert_to_numpy=True)
    return [v.tolist() for v in vectors]
