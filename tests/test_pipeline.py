"""
Tests for the full pipeline orchestration.

All external I/O (OCR, classify, date extraction, archiving) is mocked so
these tests run without Tesseract, PyMuPDF, or real documents.
"""
import shutil
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from doc_pipeline.classifier import Classification
from doc_pipeline.config import PipelineConfig
from doc_pipeline.date_extractor import DateResult
from doc_pipeline.pipeline import process_document


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def make_src(config: PipelineConfig, name: str = "test.pdf") -> Path:
    """Create a dummy source file in input_manual/."""
    path = config.input_manual / name
    path.write_bytes(b"%PDF-1.4 dummy")
    return path


def confident_classification() -> Classification:
    return Classification(doc_type="Rechnung", archive_subdir="Rechnungen",
                          thema="Strom", confident=True)


def good_date() -> DateResult:
    return DateResult(date_str="2021-02-18", score=100)


# ---------------------------------------------------------------------------
# Success path
# ---------------------------------------------------------------------------

class TestSuccessPath:

    def test_returns_destination_path(self, tmp_config):
        src = make_src(tmp_config)
        expected = tmp_config.archive / "Rechnungen" / "2021-02-18_Rechnung_Strom.pdf"

        with patch("doc_pipeline.pipeline.extract_text", return_value="Rechnung text"), \
             patch("doc_pipeline.pipeline.classify", return_value=confident_classification()), \
             patch("doc_pipeline.pipeline.extract_date", return_value=good_date()), \
             patch("doc_pipeline.pipeline.archive_document", return_value=expected):
            result = process_document(src, tmp_config)

        assert result == expected

    def test_calls_each_stage_once(self, tmp_config):
        src = make_src(tmp_config)

        with patch("doc_pipeline.pipeline.extract_text", return_value="text") as m_ocr, \
             patch("doc_pipeline.pipeline.classify", return_value=confident_classification()) as m_cls, \
             patch("doc_pipeline.pipeline.extract_date", return_value=good_date()) as m_date, \
             patch("doc_pipeline.pipeline.archive_document",
                   return_value=tmp_config.archive / "Rechnungen" / "out.pdf") as m_arch:
            process_document(src, tmp_config)

        m_ocr.assert_called_once()
        m_cls.assert_called_once()
        m_date.assert_called_once()
        m_arch.assert_called_once()

    def test_file_staged_through_processing_dir(self, tmp_config):
        """OCR must receive the processing/ path, not the original input path."""
        src = make_src(tmp_config)
        captured: list[Path] = []

        def capturing_ocr(path, **kwargs):
            captured.append(path)
            return "text"

        with patch("doc_pipeline.pipeline.extract_text", side_effect=capturing_ocr), \
             patch("doc_pipeline.pipeline.classify", return_value=confident_classification()), \
             patch("doc_pipeline.pipeline.extract_date", return_value=good_date()), \
             patch("doc_pipeline.pipeline.archive_document",
                   return_value=tmp_config.archive / "Rechnungen" / "out.pdf"):
            process_document(src, tmp_config)

        assert len(captured) == 1
        assert captured[0].parent == tmp_config.processing

    def test_ocr_called_with_correct_lang(self, tmp_config):
        src = make_src(tmp_config)

        with patch("doc_pipeline.pipeline.extract_text", return_value="text") as m_ocr, \
             patch("doc_pipeline.pipeline.classify", return_value=confident_classification()), \
             patch("doc_pipeline.pipeline.extract_date", return_value=good_date()), \
             patch("doc_pipeline.pipeline.archive_document",
                   return_value=tmp_config.archive / "Rechnungen" / "out.pdf"):
            process_document(src, tmp_config)

        _, kwargs = m_ocr.call_args
        assert kwargs.get("lang") == tmp_config.ocr_lang


# ---------------------------------------------------------------------------
# Review path (uncertain result, but no hard error)
# ---------------------------------------------------------------------------

class TestReviewPath:

    def test_uncertain_classification_routes_to_review(self, tmp_config):
        src = make_src(tmp_config)
        uncertain_cls = Classification("Dokument", "Sonstiges", "test", confident=False)
        review_dest = tmp_config.review / "UNSICHER_Dokument_test.pdf"

        with patch("doc_pipeline.pipeline.extract_text", return_value="random text"), \
             patch("doc_pipeline.pipeline.classify", return_value=uncertain_cls), \
             patch("doc_pipeline.pipeline.extract_date", return_value=None), \
             patch("doc_pipeline.pipeline.archive_document", return_value=review_dest):
            result = process_document(src, tmp_config)

        assert result == review_dest

    def test_no_date_still_returns_destination(self, tmp_config):
        src = make_src(tmp_config)
        review_dest = tmp_config.review / "UNSICHER_Rechnung_test.pdf"

        with patch("doc_pipeline.pipeline.extract_text", return_value="Rechnung text"), \
             patch("doc_pipeline.pipeline.classify", return_value=confident_classification()), \
             patch("doc_pipeline.pipeline.extract_date", return_value=None), \
             patch("doc_pipeline.pipeline.archive_document", return_value=review_dest):
            result = process_document(src, tmp_config)

        assert result == review_dest

    def test_pipeline_still_calls_archive_document_when_uncertain(self, tmp_config):
        """archive_document decides routing; pipeline should always call it."""
        src = make_src(tmp_config)
        uncertain_cls = Classification("Dokument", "Sonstiges", "x", confident=False)

        with patch("doc_pipeline.pipeline.extract_text", return_value=""), \
             patch("doc_pipeline.pipeline.classify", return_value=uncertain_cls), \
             patch("doc_pipeline.pipeline.extract_date", return_value=None), \
             patch("doc_pipeline.pipeline.archive_document",
                   return_value=tmp_config.review / "UNSICHER_x.pdf") as m_arch:
            process_document(src, tmp_config)

        m_arch.assert_called_once()


# ---------------------------------------------------------------------------
# Error path (hard failures → input_error/)
# ---------------------------------------------------------------------------

class TestErrorPath:

    def test_ocr_failure_returns_none(self, tmp_config):
        src = make_src(tmp_config)

        with patch("doc_pipeline.pipeline.extract_text",
                   side_effect=RuntimeError("Tesseract not found")):
            result = process_document(src, tmp_config)

        assert result is None

    def test_ocr_failure_moves_file_to_input_error(self, tmp_config):
        src = make_src(tmp_config)

        with patch("doc_pipeline.pipeline.extract_text",
                   side_effect=RuntimeError("OCR failed")):
            process_document(src, tmp_config)

        error_files = list(tmp_config.input_error.glob("*.pdf"))
        assert len(error_files) == 1
        assert error_files[0].name == "test.pdf"

    def test_archive_failure_returns_none(self, tmp_config):
        src = make_src(tmp_config)

        with patch("doc_pipeline.pipeline.extract_text", return_value="text"), \
             patch("doc_pipeline.pipeline.classify", return_value=confident_classification()), \
             patch("doc_pipeline.pipeline.extract_date", return_value=good_date()), \
             patch("doc_pipeline.pipeline.archive_document",
                   side_effect=OSError("disk full")):
            result = process_document(src, tmp_config)

        assert result is None

    def test_archive_failure_moves_to_input_error(self, tmp_config):
        src = make_src(tmp_config)

        with patch("doc_pipeline.pipeline.extract_text", return_value="text"), \
             patch("doc_pipeline.pipeline.classify", return_value=confident_classification()), \
             patch("doc_pipeline.pipeline.extract_date", return_value=good_date()), \
             patch("doc_pipeline.pipeline.archive_document",
                   side_effect=OSError("disk full")):
            process_document(src, tmp_config)

        assert len(list(tmp_config.input_error.glob("*.pdf"))) == 1

    def test_missing_source_file_returns_none(self, tmp_config):
        nonexistent = tmp_config.input_manual / "ghost.pdf"
        result = process_document(nonexistent, tmp_config)
        assert result is None

    def test_missing_source_does_not_create_error_file(self, tmp_config):
        nonexistent = tmp_config.input_manual / "ghost.pdf"
        process_document(nonexistent, tmp_config)
        assert list(tmp_config.input_error.glob("*")) == []


# ---------------------------------------------------------------------------
# Multiple files — isolation
# ---------------------------------------------------------------------------

class TestIsolation:

    def test_two_files_processed_independently(self, tmp_config):
        src1 = make_src(tmp_config, "doc1.pdf")
        src2 = make_src(tmp_config, "doc2.pdf")

        dest1 = tmp_config.archive / "Rechnungen" / "2021-01-01_Rechnung_Strom.pdf"
        dest2 = tmp_config.archive / "Rechnungen" / "2021-02-01_Rechnung_Strom.pdf"

        with patch("doc_pipeline.pipeline.extract_text", return_value="Rechnung text"), \
             patch("doc_pipeline.pipeline.classify", return_value=confident_classification()), \
             patch("doc_pipeline.pipeline.extract_date", return_value=good_date()), \
             patch("doc_pipeline.pipeline.archive_document",
                   side_effect=[dest1, dest2]):
            r1 = process_document(src1, tmp_config)
            r2 = process_document(src2, tmp_config)

        assert r1 == dest1
        assert r2 == dest2
