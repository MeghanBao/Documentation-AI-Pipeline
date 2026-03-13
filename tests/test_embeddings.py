"""Unit tests for doc_pipeline.embeddings — sentence-transformers is mocked."""
from unittest.mock import MagicMock, patch

import pytest


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_mock_model(dim: int = 8):
    """Return a mock SentenceTransformer whose .encode() returns numpy-like arrays."""
    import numpy as np

    mock_model = MagicMock()
    mock_model.encode.side_effect = lambda texts, **kw: np.random.rand(len(texts), dim).astype("float32")
    return mock_model


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

class TestEncode:
    def test_empty_list_returns_empty(self):
        from doc_pipeline.embeddings import encode

        result = encode([])
        assert result == []

    def test_returns_list_of_lists(self):
        mock_model = _make_mock_model(dim=8)
        with patch("doc_pipeline.embeddings._load_model", return_value=mock_model):
            # Clear module-level cache between tests
            import doc_pipeline.embeddings as emb_mod
            emb_mod._model_cache.clear()

            from doc_pipeline.embeddings import encode

            result = encode(["Hallo Welt", "Test"])

        assert isinstance(result, list)
        assert len(result) == 2
        for vec in result:
            assert isinstance(vec, list)
            assert all(isinstance(v, float) for v in vec)

    def test_vector_length_matches_model_dim(self):
        dim = 16
        mock_model = _make_mock_model(dim=dim)
        with patch("doc_pipeline.embeddings._load_model", return_value=mock_model):
            import doc_pipeline.embeddings as emb_mod
            emb_mod._model_cache.clear()

            from doc_pipeline.embeddings import encode

            result = encode(["Ein Satz."])

        assert len(result[0]) == dim

    def test_model_loaded_once_for_same_name(self):
        mock_model = _make_mock_model()
        with patch("doc_pipeline.embeddings._load_model", return_value=mock_model) as mock_load:
            import doc_pipeline.embeddings as emb_mod
            emb_mod._model_cache.clear()

            from doc_pipeline.embeddings import encode

            encode(["a"])
            encode(["b"])

        # _load_model must only be called once (cache hit on second call)
        mock_load.assert_called_once()

    def test_encode_calls_model_with_all_texts(self):
        mock_model = _make_mock_model(dim=4)
        with patch("doc_pipeline.embeddings._load_model", return_value=mock_model):
            import doc_pipeline.embeddings as emb_mod
            emb_mod._model_cache.clear()

            from doc_pipeline.embeddings import encode

            texts = ["Eins", "Zwei", "Drei"]
            encode(texts)

        call_args = mock_model.encode.call_args
        assert call_args[0][0] == texts


class TestGetModel:
    def test_get_model_uses_cache(self):
        """get_model must return the same object for repeated calls."""
        mock_model = _make_mock_model()
        with patch("doc_pipeline.embeddings._load_model", return_value=mock_model):
            import doc_pipeline.embeddings as emb_mod
            emb_mod._model_cache.clear()

            from doc_pipeline.embeddings import get_model

            m1 = get_model("test-model")
            m2 = get_model("test-model")

        assert m1 is m2
