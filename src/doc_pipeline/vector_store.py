"""ChromaDB-backed vector store for document chunk embeddings."""
from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


def _create_client(persist_dir: Path | None):
    """Create a ChromaDB client. Separate function for testability."""
    import chromadb

    if persist_dir is None:
        return chromadb.EphemeralClient()
    persist_dir.mkdir(parents=True, exist_ok=True)
    return chromadb.PersistentClient(path=str(persist_dir))


class VectorStore:
    """Thin wrapper around a single ChromaDB collection.

    Parameters
    ----------
    persist_dir:
        Directory for on-disk persistence.  ``None`` → in-memory only
        (useful for tests).
    collection_name:
        Name of the ChromaDB collection.
    """

    COLLECTION = "doc_chunks"

    def __init__(
        self,
        persist_dir: Path | None = None,
        collection_name: str = COLLECTION,
    ) -> None:
        self._client = _create_client(persist_dir)
        self._collection = self._client.get_or_create_collection(
            name=collection_name,
            metadata={"hnsw:space": "cosine"},
        )

    # ------------------------------------------------------------------
    # Properties
    # ------------------------------------------------------------------

    @property
    def chunk_count(self) -> int:
        return self._collection.count()

    # ------------------------------------------------------------------
    # Write operations
    # ------------------------------------------------------------------

    def add_document(
        self,
        doc_id: str,
        chunks: list[str],
        embeddings: list[list[float]],
        metadata: dict[str, Any] | None = None,
    ) -> None:
        """Store all chunks for one document.

        Existing chunks for *doc_id* are replaced (delete + add).
        """
        if not chunks:
            return

        self.delete_document(doc_id)

        base_meta = metadata or {}
        ids = [f"{doc_id}__chunk_{i}" for i in range(len(chunks))]
        metas = [{**base_meta, "doc_id": doc_id, "chunk_index": i} for i in range(len(chunks))]

        self._collection.add(
            ids=ids,
            embeddings=embeddings,
            documents=chunks,
            metadatas=metas,
        )
        logger.debug("Stored %d chunks for doc_id=%s", len(chunks), doc_id)

    def delete_document(self, doc_id: str) -> None:
        """Remove all chunks belonging to *doc_id*."""
        try:
            results = self._collection.get(where={"doc_id": doc_id})
            if results["ids"]:
                self._collection.delete(ids=results["ids"])
                logger.debug("Deleted %d chunks for doc_id=%s", len(results["ids"]), doc_id)
        except Exception as exc:  # noqa: BLE001
            logger.warning("delete_document(%s) failed: %s", doc_id, exc)

    # ------------------------------------------------------------------
    # Query
    # ------------------------------------------------------------------

    def query(
        self,
        embedding: list[float],
        n_results: int = 5,
    ) -> list[dict[str, Any]]:
        """Return the top-*n_results* most similar chunks.

        Each result dict has keys: ``text``, ``metadata``, ``distance``.
        Returns an empty list when the collection is empty.
        """
        if self.chunk_count == 0:
            return []

        n = min(n_results, self.chunk_count)
        results = self._collection.query(
            query_embeddings=[embedding],
            n_results=n,
            include=["documents", "metadatas", "distances"],
        )

        hits: list[dict[str, Any]] = []
        for text, meta, dist in zip(
            results["documents"][0],
            results["metadatas"][0],
            results["distances"][0],
        ):
            hits.append({"text": text, "metadata": meta, "distance": dist})
        return hits
