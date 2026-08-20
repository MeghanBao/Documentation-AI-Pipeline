"""RAG (Retrieval-Augmented Generation) query interface.

Indexes archived documents and retrieves relevant chunks for natural-language
questions — fully offline, no external API required.
"""
from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

from .chunker import chunk_text
from .embeddings import _DEFAULT_MODEL, encode
from .vector_store import VectorStore

logger = logging.getLogger(__name__)


class RAGEngine:
    """High-level RAG interface: index documents, query by natural language.

    Parameters
    ----------
    store:
        The :class:`VectorStore` instance to use.
    model_name:
        Sentence-transformer model name (must be the same at index and query
        time for distances to be meaningful).
    """

    def __init__(self, store: VectorStore, model_name: str = _DEFAULT_MODEL) -> None:
        self._store = store
        self._model_name = model_name

    # ------------------------------------------------------------------
    # Factory
    # ------------------------------------------------------------------

    @classmethod
    def from_dir(
        cls,
        persist_dir: Path,
        model_name: str = _DEFAULT_MODEL,
    ) -> RAGEngine:
        """Create a persistent :class:`RAGEngine` backed by *persist_dir*."""
        store = VectorStore(persist_dir=persist_dir)
        return cls(store=store, model_name=model_name)

    # ------------------------------------------------------------------
    # Indexing
    # ------------------------------------------------------------------

    def index_document(
        self,
        doc_id: str,
        text: str,
        metadata: dict[str, Any] | None = None,
    ) -> int:
        """Chunk *text*, compute embeddings, and store in the vector DB.

        Parameters
        ----------
        doc_id:
            Stable identifier for the document (e.g. the archive path as
            a string). Used to detect and replace stale chunks.
        text:
            Full extracted text of the document.
        metadata:
            Optional dict stored alongside every chunk
            (e.g. ``{"filename": "...", "doc_type": "...", "date": "..."}``)

        Returns
        -------
        int
            Number of chunks indexed (0 if text was empty).
        """
        chunks = chunk_text(text)
        if not chunks:
            logger.debug("No chunks for doc_id=%s — nothing indexed", doc_id)
            return 0

        chunk_texts = [c.text for c in chunks]
        embeddings = encode(chunk_texts, model_name=self._model_name)
        self._store.add_document(doc_id, chunk_texts, embeddings, metadata)
        logger.info("Indexed %d chunks for %s", len(chunks), doc_id)
        return len(chunks)

    def delete_document(self, doc_id: str) -> None:
        """Remove all indexed chunks for *doc_id*."""
        self._store.delete_document(doc_id)

    # ------------------------------------------------------------------
    # Querying
    # ------------------------------------------------------------------

    def query(
        self,
        question: str,
        n_results: int = 5,
    ) -> list[dict[str, Any]]:
        """Retrieve the most relevant chunks for a natural-language *question*.

        Returns a list of result dicts (see :meth:`VectorStore.query`), each
        with keys ``text``, ``metadata``, ``distance``.  An empty list is
        returned when the index is empty or *question* is blank.
        """
        if not question or not question.strip():
            return []

        q_embeddings = encode([question], model_name=self._model_name)
        if not q_embeddings:
            return []

        return self._store.query(q_embeddings[0], n_results=n_results)

    # ------------------------------------------------------------------
    # Introspection
    # ------------------------------------------------------------------

    @property
    def chunk_count(self) -> int:
        return self._store.chunk_count
