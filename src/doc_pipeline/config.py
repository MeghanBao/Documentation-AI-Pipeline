from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional


@dataclass
class PipelineConfig:
    base_dir: Path = field(default_factory=lambda: Path("N:/_pipeline"))
    tesseract_cmd: str = "tesseract"
    ocr_lang: str = "deu"
    # Pages with fewer chars than this threshold are re-processed via OCR
    ocr_min_chars_per_page: int = 50
    # Minimum score for a date to be considered reliable (Stage 4 threshold)
    date_min_score: int = 30
    # OCR engine priority (controls which engines are attempted in order)
    ocr_engine_priority: list[str] = field(
        default_factory=lambda: ["pymupdf", "tesseract", "paddleocr"]
    )
    paddleocr_enabled: bool = True
    # RAG settings (opt-in)
    enable_rag: bool = False
    rag_persist_dir: Optional[Path] = None
    # Append-only provenance journal enabling `why` / `undo` (see ledger.py)
    enable_journal: bool = True

    # --- Derived folder paths ---
    @property
    def input_scanner(self) -> Path:
        return self.base_dir / "input_scanner"

    @property
    def input_manual(self) -> Path:
        return self.base_dir / "input_manual"

    @property
    def processing(self) -> Path:
        return self.base_dir / "processing"

    @property
    def review(self) -> Path:
        return self.base_dir / "review"

    @property
    def input_error(self) -> Path:
        return self.base_dir / "input_error"

    @property
    def archive(self) -> Path:
        return self.base_dir / "archiv"

    @property
    def rag_db(self) -> Path:
        """Directory for ChromaDB persistence (defaults to <base_dir>/rag_db)."""
        if self.rag_persist_dir is not None:
            return self.rag_persist_dir
        return self.base_dir / "rag_db"

    def ensure_dirs(self) -> None:
        """Create all required pipeline folders if they do not exist."""
        for p in [
            self.input_scanner,
            self.input_manual,
            self.processing,
            self.review,
            self.input_error,
            self.archive,
        ]:
            p.mkdir(parents=True, exist_ok=True)

        for subdir in ["Rechnungen", "Versicherung", "Steuer", "Arbeit", "Verträge", "Sonstiges"]:
            (self.archive / subdir).mkdir(parents=True, exist_ok=True)
