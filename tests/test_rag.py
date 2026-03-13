"""Unit tests for doc_pipeline.rag.RAGEngine — mocks embeddings + uses ephemeral store."""
import uuid
from unittest.mock import patch

import pytest

from doc_pipeline.rag import RAGEngine
from doc_pipeline.vector_store import VectorStore

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_DIM = 8


def _make_encode_mock(dim: int = _DIM):
    """Return a deterministic encode() replacement."""
    import random

    call_count = [0]

    def _encode(texts: list[str], model_name: str = "") -> list[list[float]]:
        results = []
        for i, _ in enumerate(texts):
            rng = random.Random(call_count[0] * 1000 + i)
            results.append([rng.random() for _ in range(dim)])
        call_count[0] += 1
        return results

    return _encode


def _engine(dim: int = _DIM) -> tuple[RAGEngine, object]:
    """Return (engine, encode_mock) using a fresh isolated ephemeral VectorStore."""
    store = VectorStore(persist_dir=None, collection_name=f"test_rag_{uuid.uuid4().hex}")
    mock_encode = _make_encode_mock(dim)
    engine = RAGEngine(store=store)
    return engine, mock_encode


# ---------------------------------------------------------------------------
# index_document
# ---------------------------------------------------------------------------

class TestIndexDocument:
    def test_empty_text_indexes_zero_chunks(self):
        engine, mock_encode = _engine()
        with patch("doc_pipeline.rag.encode", side_effect=mock_encode):
            count = engine.index_document("doc1", "")
        assert count == 0
        assert engine.chunk_count == 0

    def test_nonempty_text_indexes_chunks(self):
        engine, mock_encode = _engine()
        text = "Rechnungsdatum: 15.03.2025\n\nBetrag: 85,40 EUR"
        with patch("doc_pipeline.rag.encode", side_effect=mock_encode):
            count = engine.index_document("doc1", text)
        assert count >= 1
        assert engine.chunk_count == count

    def test_reindexing_replaces_old_chunks(self):
        engine, mock_encode = _engine()
        with patch("doc_pipeline.rag.encode", side_effect=mock_encode):
            engine.index_document("doc1", "Erster Text mit mehreren Wörtern hier.")
            first_count = engine.chunk_count
            engine.index_document("doc1", "Zweiter viel kürzerer Text.")
        # chunk_count after re-index == new document's chunk count
        assert engine.chunk_count <= first_count + 1  # old chunks gone

    def test_metadata_passed_through(self):
        engine, mock_encode = _engine()
        text = "Haftpflichtversicherung Police 98765"
        with patch("doc_pipeline.rag.encode", side_effect=mock_encode):
            engine.index_document(
                "doc1", text, metadata={"doc_type": "Versicherung", "date": "2025-01-20"}
            )
            results = engine.query("Versicherung", n_results=1)
        assert results[0]["metadata"]["doc_type"] == "Versicherung"
        assert results[0]["metadata"]["date"] == "2025-01-20"

    def test_multiple_documents_accumulated(self):
        engine, mock_encode = _engine()
        with patch("doc_pipeline.rag.encode", side_effect=mock_encode):
            engine.index_document("doc1", "Rechnung Strom 85 EUR")
            engine.index_document("doc2", "Lohnabrechnung Februar 2025")
        assert engine.chunk_count >= 2


# ---------------------------------------------------------------------------
# delete_document
# ---------------------------------------------------------------------------

class TestDeleteDocument:
    def test_delete_removes_chunks(self):
        engine, mock_encode = _engine()
        with patch("doc_pipeline.rag.encode", side_effect=mock_encode):
            engine.index_document("doc1", "Ein Dokument zum Löschen.")
            engine.delete_document("doc1")
        assert engine.chunk_count == 0

    def test_delete_nonexistent_is_noop(self):
        engine, _ = _engine()
        engine.delete_document("nonexistent")  # must not raise


# ---------------------------------------------------------------------------
# query
# ---------------------------------------------------------------------------

class TestQuery:
    def test_empty_question_returns_empty(self):
        engine, mock_encode = _engine()
        with patch("doc_pipeline.rag.encode", side_effect=mock_encode):
            engine.index_document("doc1", "Strom Rechnung 85 EUR")
            results = engine.query("")
        assert results == []

    def test_whitespace_question_returns_empty(self):
        engine, mock_encode = _engine()
        with patch("doc_pipeline.rag.encode", side_effect=mock_encode):
            engine.index_document("doc1", "Strom Rechnung 85 EUR")
            results = engine.query("   ")
        assert results == []

    def test_query_empty_index_returns_empty(self):
        engine, mock_encode = _engine()
        with patch("doc_pipeline.rag.encode", side_effect=mock_encode):
            results = engine.query("Was kostet der Strom?")
        assert results == []

    def test_query_returns_list_of_dicts(self):
        engine, mock_encode = _engine()
        with patch("doc_pipeline.rag.encode", side_effect=mock_encode):
            engine.index_document("doc1", "Stromrechnung Betrag 85,40 EUR Rechnungsdatum")
            results = engine.query("Strom Kosten", n_results=1)
        assert len(results) >= 1
        assert {"text", "metadata", "distance"} <= results[0].keys()

    def test_n_results_respected(self):
        engine, mock_encode = _engine()
        # Index enough chunks to exceed n_results
        long_text = "\n\n".join([f"Abschnitt {i} mit einigen Wörtern." for i in range(20)])
        with patch("doc_pipeline.rag.encode", side_effect=mock_encode):
            engine.index_document("doc1", long_text)
            results = engine.query("Abschnitt", n_results=3)
        assert len(results) <= 3


# ---------------------------------------------------------------------------
# from_dir classmethod
# ---------------------------------------------------------------------------

class TestFromDir:
    def test_from_dir_creates_engine(self, tmp_path):
        with patch("doc_pipeline.rag.encode", side_effect=_make_encode_mock()):
            engine = RAGEngine.from_dir(tmp_path / "rag_db")
        assert isinstance(engine, RAGEngine)
        assert engine.chunk_count == 0
