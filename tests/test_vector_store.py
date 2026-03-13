"""Unit tests for doc_pipeline.vector_store — uses ChromaDB EphemeralClient."""
import uuid

import pytest

from doc_pipeline.vector_store import VectorStore

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_DIM = 8


def _rand_vec(seed: int = 0) -> list[float]:
    import random
    rng = random.Random(seed)
    return [rng.random() for _ in range(_DIM)]


def _store() -> VectorStore:
    """Return a fresh isolated in-memory VectorStore per call."""
    return VectorStore(persist_dir=None, collection_name=f"test_{uuid.uuid4().hex}")


# ---------------------------------------------------------------------------
# chunk_count
# ---------------------------------------------------------------------------

class TestChunkCount:
    def test_empty_store_count_zero(self):
        assert _store().chunk_count == 0

    def test_count_after_add(self):
        vs = _store()
        vs.add_document("doc1", ["chunk A", "chunk B"], [_rand_vec(0), _rand_vec(1)])
        assert vs.chunk_count == 2

    def test_count_after_delete(self):
        vs = _store()
        vs.add_document("doc1", ["chunk A"], [_rand_vec(0)])
        vs.delete_document("doc1")
        assert vs.chunk_count == 0


# ---------------------------------------------------------------------------
# add_document / delete_document
# ---------------------------------------------------------------------------

class TestAddDelete:
    def test_add_single_document(self):
        vs = _store()
        vs.add_document("doc1", ["Hallo Welt"], [_rand_vec()])
        assert vs.chunk_count == 1

    def test_add_multiple_chunks(self):
        vs = _store()
        chunks = [f"chunk {i}" for i in range(5)]
        embeddings = [_rand_vec(i) for i in range(5)]
        vs.add_document("docA", chunks, embeddings)
        assert vs.chunk_count == 5

    def test_add_empty_chunks_noop(self):
        vs = _store()
        vs.add_document("doc1", [], [])
        assert vs.chunk_count == 0

    def test_add_replaces_existing_document(self):
        vs = _store()
        vs.add_document("doc1", ["old chunk 1", "old chunk 2"], [_rand_vec(0), _rand_vec(1)])
        vs.add_document("doc1", ["new chunk"], [_rand_vec(2)])
        assert vs.chunk_count == 1  # old 2 removed, new 1 added

    def test_delete_nonexistent_is_noop(self):
        vs = _store()
        vs.delete_document("does_not_exist")  # must not raise
        assert vs.chunk_count == 0

    def test_two_documents_independent(self):
        vs = _store()
        vs.add_document("docA", ["a1", "a2"], [_rand_vec(0), _rand_vec(1)])
        vs.add_document("docB", ["b1"], [_rand_vec(2)])
        vs.delete_document("docA")
        assert vs.chunk_count == 1

    def test_metadata_stored(self):
        vs = _store()
        vs.add_document(
            "doc1",
            ["text"],
            [_rand_vec()],
            metadata={"filename": "test.pdf", "doc_type": "Rechnung"},
        )
        results = vs.query(_rand_vec(), n_results=1)
        assert results[0]["metadata"]["filename"] == "test.pdf"
        assert results[0]["metadata"]["doc_id"] == "doc1"


# ---------------------------------------------------------------------------
# query
# ---------------------------------------------------------------------------

class TestQuery:
    def test_query_empty_store_returns_empty(self):
        vs = _store()
        result = vs.query(_rand_vec(), n_results=5)
        assert result == []

    def test_query_returns_correct_structure(self):
        vs = _store()
        vs.add_document("doc1", ["Hallo Welt"], [_rand_vec()])
        results = vs.query(_rand_vec(), n_results=1)
        assert len(results) == 1
        assert "text" in results[0]
        assert "metadata" in results[0]
        assert "distance" in results[0]

    def test_query_n_results_capped_at_chunk_count(self):
        vs = _store()
        vs.add_document("doc1", ["a", "b"], [_rand_vec(0), _rand_vec(1)])
        results = vs.query(_rand_vec(), n_results=10)
        assert len(results) == 2  # only 2 chunks exist

    def test_query_text_matches_stored_chunk(self):
        vs = _store()
        text = "Rechnungsdatum: 15.03.2025"
        vs.add_document("doc1", [text], [_rand_vec()])
        results = vs.query(_rand_vec(), n_results=1)
        assert results[0]["text"] == text
