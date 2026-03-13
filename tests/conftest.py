import pytest
from pathlib import Path

from doc_pipeline.config import PipelineConfig


@pytest.fixture
def tmp_config(tmp_path: Path) -> PipelineConfig:
    """A PipelineConfig wired to a fresh temporary directory."""
    config = PipelineConfig(base_dir=tmp_path / "_pipeline")
    config.ensure_dirs()
    return config
