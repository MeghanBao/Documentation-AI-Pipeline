"""Tests for PipelineConfig: derived paths and ensure_dirs."""
from pathlib import Path

import pytest

from doc_pipeline.config import PipelineConfig


class TestDerivedPaths:
    def setup_method(self):
        self.base = Path("/tmp/pipeline")
        self.cfg = PipelineConfig(base_dir=self.base)

    def test_input_scanner(self):
        assert self.cfg.input_scanner == self.base / "input_scanner"

    def test_input_manual(self):
        assert self.cfg.input_manual == self.base / "input_manual"

    def test_processing(self):
        assert self.cfg.processing == self.base / "processing"

    def test_review(self):
        assert self.cfg.review == self.base / "review"

    def test_input_error(self):
        assert self.cfg.input_error == self.base / "input_error"

    def test_archive(self):
        assert self.cfg.archive == self.base / "archiv"


class TestEnsureDirs:
    def test_creates_all_top_level_folders(self, tmp_path):
        cfg = PipelineConfig(base_dir=tmp_path / "_pipeline")
        cfg.ensure_dirs()

        assert cfg.input_scanner.is_dir()
        assert cfg.input_manual.is_dir()
        assert cfg.processing.is_dir()
        assert cfg.review.is_dir()
        assert cfg.input_error.is_dir()
        assert cfg.archive.is_dir()

    def test_creates_all_archive_subdirs(self, tmp_path):
        cfg = PipelineConfig(base_dir=tmp_path / "_pipeline")
        cfg.ensure_dirs()

        for subdir in ["Rechnungen", "Versicherung", "Steuer", "Arbeit", "Verträge", "Sonstiges"]:
            assert (cfg.archive / subdir).is_dir(), f"Missing: {subdir}"

    def test_idempotent(self, tmp_path):
        """Calling ensure_dirs() twice must not raise."""
        cfg = PipelineConfig(base_dir=tmp_path / "_pipeline")
        cfg.ensure_dirs()
        cfg.ensure_dirs()

    def test_creates_nested_base_dir(self, tmp_path):
        """base_dir may not exist yet — it should be created recursively."""
        cfg = PipelineConfig(base_dir=tmp_path / "deep" / "nested" / "_pipeline")
        cfg.ensure_dirs()
        assert cfg.input_scanner.is_dir()


class TestDefaults:
    def test_default_ocr_lang(self):
        assert PipelineConfig().ocr_lang == "deu"

    def test_default_min_chars_per_page(self):
        assert PipelineConfig().ocr_min_chars_per_page == 50

    def test_default_date_min_score(self):
        assert PipelineConfig().date_min_score == 30

    def test_default_enable_rag_false(self):
        assert PipelineConfig().enable_rag is False

    def test_default_rag_persist_dir_none(self):
        assert PipelineConfig().rag_persist_dir is None

    def test_custom_base_dir(self, tmp_path):
        cfg = PipelineConfig(base_dir=tmp_path / "custom")
        assert cfg.base_dir == tmp_path / "custom"


class TestRagPaths:
    def test_rag_db_defaults_to_base_dir(self, tmp_path):
        cfg = PipelineConfig(base_dir=tmp_path / "_pipeline")
        assert cfg.rag_db == tmp_path / "_pipeline" / "rag_db"

    def test_rag_db_uses_custom_persist_dir(self, tmp_path):
        custom = tmp_path / "my_rag"
        cfg = PipelineConfig(base_dir=tmp_path / "_pipeline", rag_persist_dir=custom)
        assert cfg.rag_db == custom

    def test_enable_rag_can_be_set(self):
        cfg = PipelineConfig(enable_rag=True)
        assert cfg.enable_rag is True
