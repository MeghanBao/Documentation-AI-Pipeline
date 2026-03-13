"""Unit tests for doc_pipeline.chunker."""
import pytest

from doc_pipeline.chunker import Chunk, chunk_text


class TestEmptyInput:
    def test_empty_string(self):
        assert chunk_text("") == []

    def test_whitespace_only(self):
        assert chunk_text("   \n\n  ") == []


class TestSingleChunk:
    def test_short_text_becomes_one_chunk(self):
        text = "Dies ist ein kurzer Text."
        chunks = chunk_text(text)
        assert len(chunks) == 1
        assert chunks[0].text == "Dies ist ein kurzer Text."
        assert chunks[0].index == 0

    def test_index_starts_at_zero(self):
        chunks = chunk_text("Ein Satz.")
        assert chunks[0].index == 0


class TestParagraphSplitting:
    def test_two_paragraphs_stay_together_when_small(self):
        text = "Erster Absatz.\n\nZweiter Absatz."
        chunks = chunk_text(text, max_tokens=50)
        # Both paragraphs together are 6 tokens — should be one chunk
        assert len(chunks) == 1
        assert "Erster" in chunks[0].text
        assert "Zweiter" in chunks[0].text

    def test_large_paragraphs_split_into_multiple_chunks(self):
        # 300-word paragraph → must produce >1 chunks with max_tokens=100
        words = " ".join([f"Wort{i}" for i in range(300)])
        chunks = chunk_text(words, max_tokens=100, overlap_tokens=20)
        assert len(chunks) > 1

    def test_chunk_indices_are_sequential(self):
        words = " ".join([f"w{i}" for i in range(500)])
        chunks = chunk_text(words, max_tokens=100, overlap_tokens=20)
        assert [c.index for c in chunks] == list(range(len(chunks)))


class TestOverlap:
    def test_overlap_tokens_appear_in_consecutive_chunks(self):
        """The last N tokens of chunk k must reappear at the start of chunk k+1."""
        # Build text with clearly identifiable tokens
        tokens = [f"T{i:03d}" for i in range(60)]
        text = " ".join(tokens)
        chunks = chunk_text(text, max_tokens=20, overlap_tokens=5)

        assert len(chunks) >= 2
        prev_tokens = chunks[0].text.split()
        next_tokens = chunks[1].text.split()
        # Last 5 of chunk 0 should appear at start of chunk 1
        overlap = prev_tokens[-5:]
        assert next_tokens[: len(overlap)] == overlap

    def test_no_overlap_when_overlap_zero(self):
        tokens = [f"W{i}" for i in range(40)]
        text = " ".join(tokens)
        chunks = chunk_text(text, max_tokens=20, overlap_tokens=0)
        # No token should appear in two consecutive chunks
        for i in range(len(chunks) - 1):
            a = set(chunks[i].text.split())
            b = set(chunks[i + 1].text.split())
            assert a.isdisjoint(b), f"Unexpected overlap between chunk {i} and {i+1}"


class TestChunkDataclass:
    def test_chunk_is_frozen(self):
        c = Chunk(text="Hallo", index=0)
        with pytest.raises((AttributeError, TypeError)):
            c.text = "Welt"  # type: ignore[misc]

    def test_chunk_equality(self):
        assert Chunk("Hallo", 0) == Chunk("Hallo", 0)
        assert Chunk("Hallo", 0) != Chunk("Welt", 0)
