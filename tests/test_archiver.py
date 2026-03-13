"""Tests for filename generation, routing, and collision handling."""
import pytest
from pathlib import Path

from doc_pipeline.archiver import _unique_path, archive_document, build_filename
from doc_pipeline.classifier import Classification
from doc_pipeline.date_extractor import DateResult


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def cls(doc_type="Rechnung", archive_subdir="Rechnungen", thema="Strom", confident=True):
    return Classification(doc_type=doc_type, archive_subdir=archive_subdir,
                          thema=thema, confident=confident)

def dr(date_str="2021-02-18", score=100, month_only=False):
    return DateResult(date_str=date_str, score=score, month_only=month_only)


# ---------------------------------------------------------------------------
# build_filename — normal cases
# ---------------------------------------------------------------------------

class TestBuildFilenameNormal:

    def test_full_date_format(self):
        stem, uncertain = build_filename(cls(), dr("2021-02-18"), "original")
        assert stem == "2021-02-18_Rechnung_Strom"
        assert uncertain is False

    def test_month_only_format(self):
        stem, uncertain = build_filename(cls(), dr("2021-02", month_only=True), "original")
        assert stem == "2021-02_Rechnung_Strom"
        assert uncertain is False

    def test_different_doc_type_and_thema(self):
        c = cls(doc_type="Versicherung", archive_subdir="Versicherung", thema="Haftpflicht")
        stem, uncertain = build_filename(c, dr("2024-11-03"), "original")
        assert stem == "2024-11-03_Versicherung_Haftpflicht"
        assert uncertain is False

    def test_stem_contains_date_type_thema(self):
        stem, _ = build_filename(cls(), dr("2025-01-31"), "x")
        parts = stem.split("_")
        assert parts[0] == "2025-01-31"
        assert parts[1] == "Rechnung"
        assert parts[2] == "Strom"


# ---------------------------------------------------------------------------
# build_filename — uncertain cases (UNSICHER prefix)
# ---------------------------------------------------------------------------

class TestBuildFilenameUnsicher:

    def test_uncertain_when_not_confident(self):
        stem, uncertain = build_filename(cls(confident=False), dr(), "scan_001")
        assert stem.startswith("UNSICHER_")
        assert uncertain is True

    def test_uncertain_when_no_date(self):
        stem, uncertain = build_filename(cls(), None, "scan_001")
        assert stem.startswith("UNSICHER_")
        assert uncertain is True

    def test_uncertain_contains_known_doc_type(self):
        stem, _ = build_filename(cls(doc_type="Rechnung", confident=False), None, "scan")
        assert "Rechnung" in stem

    def test_uncertain_uses_dokument_when_type_unknown(self):
        c = cls(doc_type="Dokument", confident=False)
        stem, _ = build_filename(c, None, "scan")
        assert "Dokument" in stem

    def test_uncertain_contains_sanitized_stem(self):
        stem, _ = build_filename(cls(), None, "my scan 001")
        # Spaces and special chars should be sanitized
        assert " " not in stem

    def test_both_no_date_and_not_confident(self):
        stem, uncertain = build_filename(cls(confident=False), None, "scan")
        assert stem.startswith("UNSICHER_")
        assert uncertain is True


# ---------------------------------------------------------------------------
# _unique_path — collision handling
# ---------------------------------------------------------------------------

class TestUniquePath:

    def test_no_collision_returns_original(self, tmp_path):
        p = tmp_path / "doc.pdf"
        assert _unique_path(p) == p

    def test_one_existing_file_appends_counter(self, tmp_path):
        p = tmp_path / "doc.pdf"
        p.touch()
        result = _unique_path(p)
        assert result == tmp_path / "doc_1.pdf"
        assert result != p

    def test_two_existing_files(self, tmp_path):
        p = tmp_path / "doc.pdf"
        p.touch()
        (tmp_path / "doc_1.pdf").touch()
        assert _unique_path(p) == tmp_path / "doc_2.pdf"

    def test_three_existing_files(self, tmp_path):
        p = tmp_path / "doc.pdf"
        p.touch()
        (tmp_path / "doc_1.pdf").touch()
        (tmp_path / "doc_2.pdf").touch()
        assert _unique_path(p) == tmp_path / "doc_3.pdf"

    def test_extension_preserved(self, tmp_path):
        p = tmp_path / "scan.tiff"
        p.touch()
        result = _unique_path(p)
        assert result.suffix == ".tiff"


# ---------------------------------------------------------------------------
# archive_document — integration (real file moves)
# ---------------------------------------------------------------------------

class TestArchiveDocument:

    def test_moves_to_correct_archive_subdir(self, tmp_path):
        archive_base = tmp_path / "archiv"
        (archive_base / "Rechnungen").mkdir(parents=True)
        review_dir = tmp_path / "review"
        review_dir.mkdir()

        src = tmp_path / "test.pdf"
        src.write_text("PDF content")

        result = archive_document(src, cls(), dr("2021-02-18"), archive_base, review_dir)

        assert result.parent == archive_base / "Rechnungen"
        assert result.name == "2021-02-18_Rechnung_Strom.pdf"
        assert result.exists()
        assert not src.exists()  # original moved

    def test_routes_uncertain_to_review(self, tmp_path):
        archive_base = tmp_path / "archiv"
        archive_base.mkdir()
        review_dir = tmp_path / "review"
        review_dir.mkdir()

        src = tmp_path / "scan.pdf"
        src.write_text("unclear content")

        result = archive_document(src, cls(confident=False), None, archive_base, review_dir)

        assert result.parent == review_dir
        assert result.name.startswith("UNSICHER_")
        assert result.exists()

    def test_lowercase_extension_applied(self, tmp_path):
        archive_base = tmp_path / "archiv"
        (archive_base / "Rechnungen").mkdir(parents=True)
        review_dir = tmp_path / "review"
        review_dir.mkdir()

        src = tmp_path / "scan.PDF"   # uppercase extension
        src.write_text("content")

        result = archive_document(src, cls(), dr("2021-02-18"), archive_base, review_dir)
        assert result.suffix == ".pdf"

    def test_collision_resolved_automatically(self, tmp_path):
        archive_base = tmp_path / "archiv"
        dest_dir = archive_base / "Rechnungen"
        dest_dir.mkdir(parents=True)
        review_dir = tmp_path / "review"
        review_dir.mkdir()

        # Pre-create a file that would collide
        (dest_dir / "2021-02-18_Rechnung_Strom.pdf").write_text("existing")

        src = tmp_path / "test.pdf"
        src.write_text("new content")

        result = archive_document(src, cls(), dr("2021-02-18"), archive_base, review_dir)

        assert result.name == "2021-02-18_Rechnung_Strom_1.pdf"
        assert result.exists()

    def test_image_file_extension_preserved(self, tmp_path):
        archive_base = tmp_path / "archiv"
        (archive_base / "Rechnungen").mkdir(parents=True)
        review_dir = tmp_path / "review"
        review_dir.mkdir()

        src = tmp_path / "scan.png"
        src.write_bytes(b"\x89PNG")

        result = archive_document(src, cls(), dr("2021-02-18"), archive_base, review_dir)
        assert result.suffix == ".png"
