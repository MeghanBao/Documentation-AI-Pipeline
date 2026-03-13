"""Text chunking: split document text into overlapping paragraph chunks."""
from __future__ import annotations

import re
from dataclasses import dataclass


@dataclass(frozen=True)
class Chunk:
    text: str
    index: int  # chunk index within the document


def _tokenize(text: str) -> list[str]:
    """Simple whitespace tokenizer — good enough for overlap bookkeeping."""
    return text.split()


def _paragraphs(text: str) -> list[str]:
    """Split on one or more blank lines; strip and drop empties."""
    parts = re.split(r"\n\s*\n", text)
    return [p.strip() for p in parts if p.strip()]


def chunk_text(text: str, max_tokens: int = 200, overlap_tokens: int = 50) -> list[Chunk]:
    """
    Split *text* into overlapping chunks of at most *max_tokens* whitespace-tokens.

    Strategy:
    1. Split into paragraphs (blank-line boundaries).
    2. Accumulate paragraphs into a window; when the window would exceed
       *max_tokens*, emit it as a chunk and start a new window that begins
       with the last *overlap_tokens* tokens of the previous chunk.

    Returns a list of :class:`Chunk` objects (empty list for blank input).
    """
    if not text or not text.strip():
        return []

    paragraphs = _paragraphs(text)
    if not paragraphs:
        return []

    chunks: list[Chunk] = []
    window_tokens: list[str] = []
    chunk_index = 0

    def _emit(tokens: list[str]) -> None:
        nonlocal chunk_index
        if tokens:
            chunks.append(Chunk(text=" ".join(tokens), index=chunk_index))
            chunk_index += 1

    for para in paragraphs:
        para_tokens = _tokenize(para)
        if not para_tokens:
            continue

        # If a single paragraph is already larger than max_tokens, split it.
        if len(para_tokens) > max_tokens:
            # Flush current window first
            _emit(window_tokens)
            window_tokens = []
            # Slide through the large paragraph
            start = 0
            while start < len(para_tokens):
                end = min(start + max_tokens, len(para_tokens))
                _emit(para_tokens[start:end])
                if end >= len(para_tokens):
                    break
                start = end - overlap_tokens
            # Carry overlap into next window
            window_tokens = para_tokens[max(0, len(para_tokens) - overlap_tokens):]
            continue

        # Normal paragraph: try to append to current window
        if window_tokens and len(window_tokens) + len(para_tokens) > max_tokens:
            _emit(window_tokens)
            # Start new window from overlap of previous
            window_tokens = window_tokens[max(0, len(window_tokens) - overlap_tokens):]

        window_tokens.extend(para_tokens)

    # Flush remaining tokens
    _emit(window_tokens)

    return chunks
