"""Tests for OCR text extraction — real fitz/Tesseract calls are fully mocked."""
import pytest
from pathlib import Path
from unittest.mock import MagicMock, call, patch

import pytesseract

from doc_pipeline.ocr import extract_text


# ---------------------------------------------------------------------------
# Helpers — mock PDF page / document
# ---------------------------------------------------------------------------

def make_page(text: str = "", number: int = 0) -> MagicMock:
    """Return a mock fitz.Page."""
    page = MagicMock()
    page.number = number
    page.get_text.return_value = text
    # pixmap for OCR fallback
    pix = MagicMock()
    pix.width = 10
    pix.height = 10
    pix.samples = bytes(10 * 10 * 3)  # dummy RGB bytes
    page.get_pixmap.return_value = pix
    return page


def make_doc(*pages: MagicMock) -> MagicMock:
    """Return a mock fitz.Document that iterates over *pages*."""
    doc = MagicMock()
    doc.__iter__ = MagicMock(return_value=iter(pages))
    return doc


# ---------------------------------------------------------------------------
# PDF: native text path
# ---------------------------------------------------------------------------

class TestNativeTextExtraction:

    def test_rich_page_uses_pymupdf_not_tesseract(self):
        page = make_page("Rechnungsdatum: 18.02.2021 " * 5)  # well above 50 chars
        doc = make_doc(page)

        with patch("doc_pipeline.ocr.fitz.open", return_value=doc):
            result = extract_text(Path("dummy.pdf"), min_chars_per_page=50)

        assert "Rechnungsdatum" in result
        page.get_pixmap.assert_not_called()   # no OCR needed

    def test_result_contains_page_text(self):
        page = make_page("Dies ist ein ausreichend langer Text für die native Extraktion.")
        doc = make_doc(page)

        with patch("doc_pipeline.ocr.fitz.open", return_value=doc):
            result = extract_text(Path("dummy.pdf"), min_chars_per_page=30)

        assert "native Extraktion" in result

    def test_multipage_native_text_joined(self):
        p1 = make_page("Seite eins mit viel Text hier drin. " * 2, number=0)
        p2 = make_page("Seite zwei ebenfalls voll mit Inhalt. " * 2, number=1)
        doc = make_doc(p1, p2)

        with patch("doc_pipeline.ocr.fitz.open", return_value=doc):
            result = extract_text(Path("dummy.pdf"), min_chars_per_page=30)

        assert "Seite eins" in result
        assert "Seite zwei" in result

    def test_doc_close_always_called(self):
        page = make_page("Long enough native text content here. " * 2)
        doc = make_doc(page)

        with patch("doc_pipeline.ocr.fitz.open", return_value=doc):
            extract_text(Path("dummy.pdf"))

        doc.close.assert_called_once()


# ---------------------------------------------------------------------------
# PDF: Tesseract OCR fallback
# ---------------------------------------------------------------------------

class TestTesseractFallback:

    def test_sparse_page_triggers_ocr(self):
        page = make_page("abc")  # 3 chars < default 50 → OCR
        doc = make_doc(page)

        with patch("doc_pipeline.ocr.fitz.open", return_value=doc), \
             patch("doc_pipeline.ocr.Image.frombytes"), \
             patch("doc_pipeline.ocr.pytesseract.image_to_string", return_value="OCR text"):
            result = extract_text(Path("dummy.pdf"), min_chars_per_page=50)

        assert result == "OCR text"
        page.get_pixmap.assert_called_once()

    def test_empty_page_triggers_ocr(self):
        page = make_page("")
        doc = make_doc(page)

        with patch("doc_pipeline.ocr.fitz.open", return_value=doc), \
             patch("doc_pipeline.ocr.Image.frombytes"), \
             patch("doc_pipeline.ocr.pytesseract.image_to_string", return_value="scanned"):
            result = extract_text(Path("dummy.pdf"))

        assert result == "scanned"

    def test_mixed_pages_first_native_second_ocr(self):
        p1 = make_page("Voll mit Text. " * 5, number=0)   # native
        p2 = make_page("", number=1)                        # OCR fallback
        doc = make_doc(p1, p2)

        with patch("doc_pipeline.ocr.fitz.open", return_value=doc), \
             patch("doc_pipeline.ocr.Image.frombytes"), \
             patch("doc_pipeline.ocr.pytesseract.image_to_string", return_value="OCR page 2"):
            result = extract_text(Path("dummy.pdf"), min_chars_per_page=30)

        assert "Voll mit Text" in result
        assert "OCR page 2" in result
        p1.get_pixmap.assert_not_called()
        p2.get_pixmap.assert_called_once()

    def test_tesseract_receives_correct_language(self):
        page = make_page("")
        doc = make_doc(page)

        with patch("doc_pipeline.ocr.fitz.open", return_value=doc), \
             patch("doc_pipeline.ocr.Image.frombytes"), \
             patch("doc_pipeline.ocr.pytesseract.image_to_string", return_value="") as mock_ts:
            extract_text(Path("dummy.pdf"), lang="deu")

        call_kwargs = mock_ts.call_args
        assert "deu" in call_kwargs[1].get("config", "")

    def test_tesseract_error_returns_empty_string(self):
        """Tesseract failures must not crash the pipeline — return empty string."""
        page = make_page("")
        doc = make_doc(page)

        with patch("doc_pipeline.ocr.fitz.open", return_value=doc), \
             patch("doc_pipeline.ocr.Image.frombytes"), \
             patch("doc_pipeline.ocr.pytesseract.image_to_string",
                   side_effect=pytesseract.TesseractError(1, "not found")):
            result = extract_text(Path("dummy.pdf"))

        assert result == ""   # graceful degradation, no exception


# ---------------------------------------------------------------------------
# Image file input
# ---------------------------------------------------------------------------

class TestImageFileInput:

    def test_png_goes_directly_to_tesseract(self, tmp_path):
        img_path = tmp_path / "scan.png"
        img_path.write_bytes(b"\x89PNG dummy")

        mock_img = MagicMock()
        with patch("doc_pipeline.ocr.Image.open", return_value=mock_img), \
             patch("doc_pipeline.ocr.pytesseract.image_to_string", return_value="image text"):
            result = extract_text(img_path)

        assert result == "image text"

    def test_jpg_supported(self, tmp_path):
        img_path = tmp_path / "photo.jpg"
        img_path.write_bytes(b"\xff\xd8 jpeg")

        with patch("doc_pipeline.ocr.Image.open", return_value=MagicMock()), \
             patch("doc_pipeline.ocr.pytesseract.image_to_string", return_value="jpg text"):
            result = extract_text(img_path)

        assert result == "jpg text"

    def test_tiff_supported(self, tmp_path):
        img_path = tmp_path / "scan.tiff"
        img_path.write_bytes(b"II dummy tiff")

        with patch("doc_pipeline.ocr.Image.open", return_value=MagicMock()), \
             patch("doc_pipeline.ocr.pytesseract.image_to_string", return_value="tiff text"):
            result = extract_text(img_path)

        assert result == "tiff text"

    def test_image_open_failure_raises_runtime_error(self, tmp_path):
        img_path = tmp_path / "bad.png"
        img_path.write_bytes(b"garbage")

        with patch("doc_pipeline.ocr.Image.open", side_effect=Exception("corrupt image")):
            with pytest.raises(RuntimeError, match="Cannot open image"):
                extract_text(img_path)


# ---------------------------------------------------------------------------
# Error handling
# ---------------------------------------------------------------------------

class TestErrorHandling:

    def test_pdf_open_failure_raises_runtime_error(self):
        with patch("doc_pipeline.ocr.fitz.open", side_effect=Exception("not a PDF")):
            with pytest.raises(RuntimeError, match="Cannot open PDF"):
                extract_text(Path("broken.pdf"))

    def test_unsupported_extension_raises_value_error(self):
        with pytest.raises(ValueError, match="Unsupported file type"):
            extract_text(Path("document.docx"))

    def test_unsupported_extension_txt(self):
        with pytest.raises(ValueError):
            extract_text(Path("notes.txt"))
