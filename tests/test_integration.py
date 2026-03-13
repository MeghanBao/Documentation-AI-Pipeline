"""
Integration tests — run the full pipeline on real PDF fixtures.

No mocks. Uses genuine PyMuPDF text extraction, keyword classification,
4-stage date scoring, and real file archiving.

Fixtures are pre-generated in tests/fixtures/ by generate_fixtures.py.
Each fixture exercises a distinct pipeline path:
  rechnung_strom.pdf          → Rechnungsdatum (score 100) → archiv/Rechnungen/
  versicherung_haftpflicht.pdf → Schreiben vom  (score  80) → archiv/Versicherung/
  lohnabrechnung_feb_2025.pdf → Abrechnungsmonat, month-name (score 65) → archiv/Arbeit/
"""
import shutil
from pathlib import Path

import pytest

from doc_pipeline.config import PipelineConfig
from doc_pipeline.pipeline import process_document

FIXTURES = Path(__file__).parent / "fixtures"


# ---------------------------------------------------------------------------
# Shared helper
# ---------------------------------------------------------------------------

def run(fixture: str, tmp_config: PipelineConfig) -> Path:
    """Copy fixture to input_manual/ and run the pipeline. Returns dest path."""
    src = FIXTURES / fixture
    assert src.exists(), f"Fixture not found: {src}  (run generate_fixtures.py)"
    dest = tmp_config.input_manual / fixture
    shutil.copy(src, dest)
    result = process_document(dest, tmp_config)
    assert result is not None, (
        f"Pipeline returned None for {fixture}. "
        f"Check input_error/: {list(tmp_config.input_error.iterdir())}"
    )
    return result


# ---------------------------------------------------------------------------
# Fixture 1: Rechnung Strom
#   Rechnungsdatum: 15.03.2025  →  score 100
#   Thema keyword: "strom"
# ---------------------------------------------------------------------------

class TestRechnungStrom:
    FIXTURE = "rechnung_strom.pdf"

    def test_archived_in_rechnungen(self, tmp_config):
        result = run(self.FIXTURE, tmp_config)
        assert result.parent == tmp_config.archive / "Rechnungen", (
            f"Expected archiv/Rechnungen/, got {result.parent}"
        )

    def test_not_in_review_or_error(self, tmp_config):
        result = run(self.FIXTURE, tmp_config)
        assert result.parent != tmp_config.review
        assert result.parent != tmp_config.input_error

    def test_full_date_prefix(self, tmp_config):
        result = run(self.FIXTURE, tmp_config)
        assert result.name.startswith("2025-03-15_"), (
            f"Expected 2025-03-15_ prefix, got: {result.name}"
        )

    def test_doc_type_in_filename(self, tmp_config):
        result = run(self.FIXTURE, tmp_config)
        assert "Rechnung" in result.name

    def test_thema_strom_in_filename(self, tmp_config):
        result = run(self.FIXTURE, tmp_config)
        assert "Strom" in result.name

    def test_no_unsicher_prefix(self, tmp_config):
        result = run(self.FIXTURE, tmp_config)
        assert not result.name.startswith("UNSICHER_")

    def test_pdf_extension(self, tmp_config):
        result = run(self.FIXTURE, tmp_config)
        assert result.suffix == ".pdf"

    def test_exact_filename(self, tmp_config):
        result = run(self.FIXTURE, tmp_config)
        assert result.name == "2025-03-15_Rechnung_Strom.pdf", (
            f"Unexpected filename: {result.name}"
        )


# ---------------------------------------------------------------------------
# Fixture 2: Versicherung Haftpflicht
#   Schreiben vom 20.01.2025  →  score 80
#   Thema keyword: "haftpflicht"
# ---------------------------------------------------------------------------

class TestVersicherungHaftpflicht:
    FIXTURE = "versicherung_haftpflicht.pdf"

    def test_archived_in_versicherung(self, tmp_config):
        result = run(self.FIXTURE, tmp_config)
        assert result.parent == tmp_config.archive / "Versicherung", (
            f"Expected archiv/Versicherung/, got {result.parent}"
        )

    def test_not_in_review_or_error(self, tmp_config):
        result = run(self.FIXTURE, tmp_config)
        assert result.parent != tmp_config.review
        assert result.parent != tmp_config.input_error

    def test_full_date_prefix(self, tmp_config):
        result = run(self.FIXTURE, tmp_config)
        assert result.name.startswith("2025-01-20_"), (
            f"Expected 2025-01-20_ prefix, got: {result.name}"
        )

    def test_doc_type_in_filename(self, tmp_config):
        result = run(self.FIXTURE, tmp_config)
        assert "Versicherung" in result.name

    def test_thema_haftpflicht_in_filename(self, tmp_config):
        result = run(self.FIXTURE, tmp_config)
        assert "Haftpflicht" in result.name

    def test_no_unsicher_prefix(self, tmp_config):
        result = run(self.FIXTURE, tmp_config)
        assert not result.name.startswith("UNSICHER_")

    def test_exact_filename(self, tmp_config):
        result = run(self.FIXTURE, tmp_config)
        assert result.name == "2025-01-20_Versicherung_Haftpflicht.pdf", (
            f"Unexpected filename: {result.name}"
        )


# ---------------------------------------------------------------------------
# Fixture 3: Lohnabrechnung Februar 2025
#   Abrechnungsmonat: Februar 2025  →  month-only, score 65
#   Tests the _RE_MONTH_NAME_ONLY fallback in date_extractor
# ---------------------------------------------------------------------------

class TestLohnabrechnung:
    FIXTURE = "lohnabrechnung_feb_2025.pdf"

    def test_archived_in_arbeit(self, tmp_config):
        result = run(self.FIXTURE, tmp_config)
        assert result.parent == tmp_config.archive / "Arbeit", (
            f"Expected archiv/Arbeit/, got {result.parent}"
        )

    def test_not_in_review_or_error(self, tmp_config):
        result = run(self.FIXTURE, tmp_config)
        assert result.parent != tmp_config.review
        assert result.parent != tmp_config.input_error

    def test_month_only_date_prefix(self, tmp_config):
        """Date is month-only → YYYY-MM_ prefix (no day)."""
        result = run(self.FIXTURE, tmp_config)
        assert result.name.startswith("2025-02_"), (
            f"Expected 2025-02_ prefix, got: {result.name}"
        )

    def test_no_full_date_prefix(self, tmp_config):
        """Must NOT look like a full-date prefix (YYYY-MM-DD)."""
        result = run(self.FIXTURE, tmp_config)
        assert not result.name.startswith("2025-02-"), (
            f"Should be month-only but got full date: {result.name}"
        )

    def test_doc_type_in_filename(self, tmp_config):
        result = run(self.FIXTURE, tmp_config)
        assert "Lohnabrechnung" in result.name

    def test_no_unsicher_prefix(self, tmp_config):
        """'Februar 2025' must be parsed → file must NOT go to review/."""
        result = run(self.FIXTURE, tmp_config)
        assert not result.name.startswith("UNSICHER_"), (
            "Abrechnungsmonat 'Februar 2025' was not extracted — "
            "check _RE_MONTH_NAME_ONLY in date_extractor.py"
        )

    def test_thema_gehalt_in_filename(self, tmp_config):
        """Payslip thema must be 'Gehalt', not the raw filename stem."""
        result = run(self.FIXTURE, tmp_config)
        assert "Gehalt" in result.name, (
            f"Expected 'Gehalt' in filename, got: {result.name}"
        )

    def test_exact_filename(self, tmp_config):
        result = run(self.FIXTURE, tmp_config)
        assert result.name == "2025-02_Lohnabrechnung_Gehalt.pdf", (
            f"Unexpected filename: {result.name}"
        )


# ---------------------------------------------------------------------------
# Cross-fixture: source files are consumed (moved), not copied
# ---------------------------------------------------------------------------

class TestFileHandling:

    def test_source_removed_after_archiving(self, tmp_config):
        src = FIXTURES / "rechnung_strom.pdf"
        dest = tmp_config.input_manual / "rechnung_strom.pdf"
        shutil.copy(src, dest)
        process_document(dest, tmp_config)
        assert not dest.exists(), "Source file should be moved, not copied"

    def test_processing_dir_cleared_after_success(self, tmp_config):
        src = FIXTURES / "versicherung_haftpflicht.pdf"
        dest = tmp_config.input_manual / src.name
        shutil.copy(src, dest)
        process_document(dest, tmp_config)
        assert list(tmp_config.processing.iterdir()) == [], (
            "processing/ should be empty after a successful run"
        )

    def test_two_copies_get_unique_names(self, tmp_config):
        """Processing the same document twice must not overwrite the first copy."""
        for i in range(2):
            src = FIXTURES / "rechnung_strom.pdf"
            copy = tmp_config.input_manual / f"rechnung_strom_{i}.pdf"
            shutil.copy(src, copy)
            process_document(copy, tmp_config)

        archived = list((tmp_config.archive / "Rechnungen").glob("*.pdf"))
        assert len(archived) == 2, (
            f"Expected 2 archived files, got {len(archived)}: {archived}"
        )
        assert len({f.name for f in archived}) == 2, "Filenames should be unique"
