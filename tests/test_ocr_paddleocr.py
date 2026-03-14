"""
Tests for PaddleOCR third-stage fallback in doc_pipeline.ocr.

All PaddleOCR calls are mocked — no real paddleocr installation required.
Tests cover:
  - PaddleOCR not triggered when native / Tesseract text is already sufficient
  - PaddleOCR triggered when both earlier stages give sparse output
  - Graceful degradation when PaddleOCR is not installed (ImportError)
  - Graceful degradation when PaddleOCR raises a runtime error
  - paddleocr_enabled=False flag disables Stage 3 entirely
  - Result parsing: multiline output, empty/None results
  - Language mapping (Tesseract "deu" → PaddleOCR "german")
  - PaddleOCR instance cache (_paddle_cache)
"""
from pathlib import Path
from unittest.mock import MagicMock, call, patch

import pytest

import doc_pipeline.ocr as ocr_mod
from doc_pipeline.ocr import (
    _TESSERACT_TO_PADDLE_LANG,
    _run_paddleocr,
    extract_text,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_page(text: str = "", number: int = 0) -> MagicMock:
    page = MagicMock()
    page.number = number
    page.get_text.return_value = text
    pix = MagicMock()
    pix.width = 10
    pix.height = 10
    pix.samples = bytes(10 * 10 * 3)
    page.get_pixmap.return_value = pix
    return page


def _make_doc(*pages: MagicMock) -> MagicMock:
    doc = MagicMock()
    doc.__iter__ = MagicMock(return_value=iter(pages))
    return doc


def _paddle_result(text: str) -> list:
    """Build a realistic PaddleOCR return value for a single text line."""
    bbox = [[0, 0], [100, 0], [100, 20], [0, 20]]
    return [[[bbox, (text, 0.97)]]]


def _paddle_multiline(*lines: str) -> list:
    """PaddleOCR result with multiple text lines."""
    bbox = [[0, 0], [100, 0], [100, 20], [0, 20]]
    return [[[bbox, (line, 0.97)] for line in lines]]


# ---------------------------------------------------------------------------
# Fixture: clear the PaddleOCR instance cache before/after every test
# ---------------------------------------------------------------------------

@pytest.fixture(autouse=True)
def clear_paddle_cache():
    ocr_mod._paddle_cache.clear()
    yield
    ocr_mod._paddle_cache.clear()


# ---------------------------------------------------------------------------
# Stage 3 not triggered when earlier stages succeed
# ---------------------------------------------------------------------------

class TestPaddleOCRNotTriggered:

    def test_rich_native_text_skips_all_ocr(self):
        """PyMuPDF extracts enough text → no Tesseract, no PaddleOCR."""
        page = _make_page("Rechnungsdatum: 15.03.2025 " * 5)  # >> 50 chars
        doc = _make_doc(page)

        with patch("doc_pipeline.ocr.fitz.open", return_value=doc), \
             patch("doc_pipeline.ocr._run_paddleocr") as mock_paddle:
            extract_text(Path("dummy.pdf"), min_chars_per_page=50)

        mock_paddle.assert_not_called()
        page.get_pixmap.assert_not_called()

    def test_sufficient_tesseract_output_skips_paddleocr(self):
        """Native too short, Tesseract returns enough text → PaddleOCR skipped."""
        page = _make_page("abc")  # < 50
        doc = _make_doc(page)
        long_tess = "Rechnung Strom 85,40 EUR " * 3  # > 50 chars

        with patch("doc_pipeline.ocr.fitz.open", return_value=doc), \
             patch("doc_pipeline.ocr.Image.frombytes"), \
             patch("doc_pipeline.ocr.pytesseract.image_to_string", return_value=long_tess), \
             patch("doc_pipeline.ocr._run_paddleocr") as mock_paddle:
            result = extract_text(Path("dummy.pdf"), min_chars_per_page=50)

        assert long_tess in result
        mock_paddle.assert_not_called()

    def test_paddleocr_disabled_flag_skips_stage3(self):
        """paddleocr_enabled=False → PaddleOCR never called even if Tesseract sparse."""
        page = _make_page("")
        doc = _make_doc(page)

        with patch("doc_pipeline.ocr.fitz.open", return_value=doc), \
             patch("doc_pipeline.ocr.Image.frombytes"), \
             patch("doc_pipeline.ocr.pytesseract.image_to_string", return_value="few"), \
             patch("doc_pipeline.ocr._run_paddleocr") as mock_paddle:
            result = extract_text(Path("dummy.pdf"), paddleocr_enabled=False)

        mock_paddle.assert_not_called()
        assert result == "few"


# ---------------------------------------------------------------------------
# Stage 3 triggered: both native and Tesseract are sparse
# ---------------------------------------------------------------------------

class TestPaddleOCRThirdStage:

    def test_sparse_tesseract_triggers_paddleocr(self):
        """Native="" and Tesseract="few" (both < threshold) → PaddleOCR called."""
        page = _make_page("")
        doc = _make_doc(page)

        with patch("doc_pipeline.ocr.fitz.open", return_value=doc), \
             patch("doc_pipeline.ocr.Image.frombytes"), \
             patch("doc_pipeline.ocr.pytesseract.image_to_string", return_value="few"), \
             patch("doc_pipeline.ocr._run_paddleocr", return_value="PaddleOCR text") as mock_paddle:
            result = extract_text(Path("dummy.pdf"), min_chars_per_page=50)

        mock_paddle.assert_called_once()
        assert result == "PaddleOCR text"

    def test_paddleocr_result_replaces_sparse_tesseract(self):
        """PaddleOCR gives richer output → PaddleOCR result is used."""
        page = _make_page("")
        doc = _make_doc(page)
        paddle_output = "Rechnungsdatum: 15.03.2025 Betrag: 85,40 EUR"

        with patch("doc_pipeline.ocr.fitz.open", return_value=doc), \
             patch("doc_pipeline.ocr.Image.frombytes"), \
             patch("doc_pipeline.ocr.pytesseract.image_to_string", return_value="x"), \
             patch("doc_pipeline.ocr._run_paddleocr", return_value=paddle_output):
            result = extract_text(Path("dummy.pdf"), min_chars_per_page=10)

        assert result == paddle_output

    def test_tesseract_result_kept_when_paddle_empty(self):
        """PaddleOCR returns empty → Tesseract result preserved."""
        page = _make_page("")
        doc = _make_doc(page)

        with patch("doc_pipeline.ocr.fitz.open", return_value=doc), \
             patch("doc_pipeline.ocr.Image.frombytes"), \
             patch("doc_pipeline.ocr.pytesseract.image_to_string", return_value="tess"), \
             patch("doc_pipeline.ocr._run_paddleocr", return_value=""):
            result = extract_text(Path("dummy.pdf"), min_chars_per_page=20)

        assert result == "tess"

    def test_tesseract_result_kept_when_paddle_none(self):
        """PaddleOCR returns None → Tesseract result preserved."""
        page = _make_page("")
        doc = _make_doc(page)

        with patch("doc_pipeline.ocr.fitz.open", return_value=doc), \
             patch("doc_pipeline.ocr.Image.frombytes"), \
             patch("doc_pipeline.ocr.pytesseract.image_to_string", return_value="tess_text"), \
             patch("doc_pipeline.ocr._run_paddleocr", return_value=None):
            result = extract_text(Path("dummy.pdf"), min_chars_per_page=20)

        assert result == "tess_text"

    def test_multipage_only_sparse_pages_use_paddleocr(self):
        """PaddleOCR is only called for pages where Tesseract was also sparse."""
        p1 = _make_page("Voll mit Text hier. " * 5, number=0)  # native rich
        p2 = _make_page("", number=1)                            # sparse → stage 2+3
        doc = _make_doc(p1, p2)

        with patch("doc_pipeline.ocr.fitz.open", return_value=doc), \
             patch("doc_pipeline.ocr.Image.frombytes"), \
             patch("doc_pipeline.ocr.pytesseract.image_to_string", return_value="x"), \
             patch("doc_pipeline.ocr._run_paddleocr", return_value="Paddle p2") as mock_p:
            result = extract_text(Path("dummy.pdf"), min_chars_per_page=30)

        mock_p.assert_called_once()
        assert "Voll mit Text" in result
        assert "Paddle p2" in result


# ---------------------------------------------------------------------------
# Graceful degradation
# ---------------------------------------------------------------------------

class TestGracefulDegradation:

    def test_import_error_falls_back_to_tesseract(self):
        """paddleocr not installed → ImportError caught → Tesseract result used."""
        page = _make_page("")
        doc = _make_doc(page)

        with patch("doc_pipeline.ocr.fitz.open", return_value=doc), \
             patch("doc_pipeline.ocr.Image.frombytes"), \
             patch("doc_pipeline.ocr.pytesseract.image_to_string", return_value="tess_fallback"), \
             patch("doc_pipeline.ocr._load_paddleocr", side_effect=ImportError("no module")):
            result = extract_text(Path("dummy.pdf"), min_chars_per_page=50)

        assert result == "tess_fallback"

    def test_runtime_error_falls_back_to_tesseract(self):
        """PaddleOCR raises RuntimeError → warning logged, Tesseract result kept."""
        page = _make_page("")
        doc = _make_doc(page)

        with patch("doc_pipeline.ocr.fitz.open", return_value=doc), \
             patch("doc_pipeline.ocr.Image.frombytes"), \
             patch("doc_pipeline.ocr.pytesseract.image_to_string", return_value="tess_ok"), \
             patch("doc_pipeline.ocr._load_paddleocr", side_effect=RuntimeError("GPU error")):
            result = extract_text(Path("dummy.pdf"), min_chars_per_page=50)

        assert result == "tess_ok"

    def test_paddle_failure_does_not_raise(self):
        """_ocr_page_paddle raising an unhandled exception must not crash the pipeline.

        _extract_from_pdf wraps the paddle call in its own try/except as
        defense-in-depth, so even if _run_paddleocr's internal guard is
        bypassed the pipeline stays alive and falls back to the Tesseract result.
        """
        page = _make_page("")
        doc = _make_doc(page)

        with patch("doc_pipeline.ocr.fitz.open", return_value=doc), \
             patch("doc_pipeline.ocr.Image.frombytes"), \
             patch("doc_pipeline.ocr.pytesseract.image_to_string", return_value="safe_tess"), \
             patch("doc_pipeline.ocr._run_paddleocr", side_effect=Exception("crash")):
            result = extract_text(Path("dummy.pdf"), min_chars_per_page=50)

        assert result == "safe_tess"  # Tesseract result preserved despite paddle crash

    def test_run_paddleocr_catches_import_error(self):
        """_run_paddleocr itself catches ImportError from _load_paddleocr."""
        mock_img = MagicMock()
        with patch("doc_pipeline.ocr._load_paddleocr", side_effect=ImportError("not installed")):
            result = _run_paddleocr(mock_img, "deu")
        assert result == ""

    def test_run_paddleocr_catches_runtime_error(self):
        """_run_paddleocr itself catches any runtime exception."""
        mock_img = MagicMock()
        with patch("doc_pipeline.ocr._load_paddleocr", side_effect=RuntimeError("crash")):
            result = _run_paddleocr(mock_img, "deu")
        assert result == ""


# ---------------------------------------------------------------------------
# _run_paddleocr result parsing
# ---------------------------------------------------------------------------

class TestRunPaddleOCR:

    def test_single_line_result(self):
        """Single text line extracted correctly."""
        mock_ocr = MagicMock()
        mock_ocr.ocr.return_value = _paddle_result("Rechnungsdatum: 15.03.2025")
        mock_img = MagicMock()

        with patch("doc_pipeline.ocr._load_paddleocr", return_value=mock_ocr):
            result = _run_paddleocr(mock_img, "deu")

        assert result == "Rechnungsdatum: 15.03.2025"

    def test_multiline_result_joined_with_newline(self):
        """Multiple text lines joined by '\\n'."""
        mock_ocr = MagicMock()
        mock_ocr.ocr.return_value = _paddle_multiline("Zeile 1", "Zeile 2", "Zeile 3")
        mock_img = MagicMock()

        with patch("doc_pipeline.ocr._load_paddleocr", return_value=mock_ocr):
            result = _run_paddleocr(mock_img, "deu")

        assert result == "Zeile 1\nZeile 2\nZeile 3"

    def test_empty_result_list_returns_empty_string(self):
        """ocr() returns [] → empty string."""
        mock_ocr = MagicMock()
        mock_ocr.ocr.return_value = []
        mock_img = MagicMock()

        with patch("doc_pipeline.ocr._load_paddleocr", return_value=mock_ocr):
            result = _run_paddleocr(mock_img, "deu")

        assert result == ""

    def test_none_result_returns_empty_string(self):
        """ocr() returns None → empty string."""
        mock_ocr = MagicMock()
        mock_ocr.ocr.return_value = None
        mock_img = MagicMock()

        with patch("doc_pipeline.ocr._load_paddleocr", return_value=mock_ocr):
            result = _run_paddleocr(mock_img, "deu")

        assert result == ""

    def test_none_page_result_returns_empty_string(self):
        """ocr() returns [[None]] (blank page) → empty string."""
        mock_ocr = MagicMock()
        mock_ocr.ocr.return_value = [[None]]
        mock_img = MagicMock()

        with patch("doc_pipeline.ocr._load_paddleocr", return_value=mock_ocr):
            result = _run_paddleocr(mock_img, "deu")

        assert result == ""

    def test_model_called_with_cls_true(self):
        """PaddleOCR.ocr() must be called with cls=True for angle classification."""
        mock_ocr = MagicMock()
        mock_ocr.ocr.return_value = _paddle_result("text")
        mock_img = MagicMock()

        with patch("doc_pipeline.ocr._load_paddleocr", return_value=mock_ocr):
            _run_paddleocr(mock_img, "deu")

        mock_ocr.ocr.assert_called_once()
        _, kwargs = mock_ocr.ocr.call_args
        assert kwargs.get("cls") is True


# ---------------------------------------------------------------------------
# Language mapping
# ---------------------------------------------------------------------------

class TestLangMapping:

    def test_deu_maps_to_german(self):
        assert _TESSERACT_TO_PADDLE_LANG["deu"] == "german"

    def test_eng_maps_to_en(self):
        assert _TESSERACT_TO_PADDLE_LANG["eng"] == "en"

    def test_unknown_lang_defaults_to_german(self):
        """Any unsupported Tesseract lang falls back to 'german'."""
        mock_ocr = MagicMock()
        mock_ocr.ocr.return_value = _paddle_result("text")

        with patch("doc_pipeline.ocr._load_paddleocr", return_value=mock_ocr) as mock_load:
            _run_paddleocr(MagicMock(), "xyz")  # unknown lang

        mock_load.assert_called_once_with("german")

    def test_known_lang_uses_mapped_name(self):
        mock_ocr = MagicMock()
        mock_ocr.ocr.return_value = _paddle_result("text")

        with patch("doc_pipeline.ocr._load_paddleocr", return_value=mock_ocr) as mock_load:
            _run_paddleocr(MagicMock(), "eng")

        mock_load.assert_called_once_with("en")


# ---------------------------------------------------------------------------
# PaddleOCR instance cache
# ---------------------------------------------------------------------------

class TestPaddleCache:

    def test_same_lang_reuses_instance(self):
        """_load_paddleocr called only once per language."""
        mock_ocr = MagicMock()
        mock_ocr.ocr.return_value = _paddle_result("x")

        with patch("doc_pipeline.ocr._load_paddleocr", return_value=mock_ocr) as mock_load:
            _run_paddleocr(MagicMock(), "deu")
            _run_paddleocr(MagicMock(), "deu")

        mock_load.assert_called_once()

    def test_different_langs_create_separate_instances(self):
        """_load_paddleocr called separately for different language codes."""
        mock_ocr = MagicMock()
        mock_ocr.ocr.return_value = _paddle_result("x")

        with patch("doc_pipeline.ocr._load_paddleocr", return_value=mock_ocr) as mock_load:
            _run_paddleocr(MagicMock(), "deu")   # → "german"
            _run_paddleocr(MagicMock(), "eng")   # → "en"

        assert mock_load.call_count == 2

    def test_clear_cache_forces_reload(self):
        """Clearing _paddle_cache causes a fresh _load_paddleocr call."""
        mock_ocr = MagicMock()
        mock_ocr.ocr.return_value = _paddle_result("x")

        with patch("doc_pipeline.ocr._load_paddleocr", return_value=mock_ocr) as mock_load:
            _run_paddleocr(MagicMock(), "deu")
            ocr_mod._paddle_cache.clear()
            _run_paddleocr(MagicMock(), "deu")

        assert mock_load.call_count == 2
