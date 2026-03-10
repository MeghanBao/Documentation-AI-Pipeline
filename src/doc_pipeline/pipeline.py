"""Main pipeline: ties OCR → classify → date extraction → archiving together."""
import logging
import shutil
from pathlib import Path
from typing import Optional

from .archiver import archive_document
from .classifier import classify
from .config import PipelineConfig
from .date_extractor import extract_date
from .ocr import extract_text

logger = logging.getLogger(__name__)


def process_document(file_path: Path, config: PipelineConfig) -> Optional[Path]:
    """
    Process a single document through the full pipeline.

    Flow:
      1. Move to processing/ (prevents double-processing)
      2. OCR → full text
      3. Classify document type + thema
      4. Extract document date (4-stage scoring)
      5. Build filename and move to archive/ or review/

    Returns the final destination Path on success, or None on hard failure.
    On OCR failure the file is moved to input_error/.
    Uncertain classification or missing date → review/ with UNSICHER_ prefix.
    """
    processing_path = config.processing / file_path.name

    try:
        shutil.move(str(file_path), str(processing_path))
    except OSError as exc:
        logger.error("Cannot move %s to processing: %s", file_path.name, exc)
        return None

    logger.info("Processing: %s", processing_path.name)

    # --- Step 1: OCR ---
    try:
        text = extract_text(
            processing_path,
            lang=config.ocr_lang,
            min_chars_per_page=config.ocr_min_chars_per_page,
        )
    except Exception as exc:
        logger.error("OCR failed for %s: %s", processing_path.name, exc)
        _move_to_error(processing_path, config.input_error)
        return None

    # --- Step 2: Classify ---
    classification = classify(text, fallback_stem=file_path.stem)
    if not classification.confident:
        logger.warning("No document type detected for %s → review", processing_path.name)

    # --- Step 3: Extract date ---
    date_result = extract_date(text, min_score=config.date_min_score)
    if date_result is None:
        logger.warning("No reliable date found for %s → review", processing_path.name)

    # --- Step 4: Archive ---
    try:
        dest = archive_document(
            src_path=processing_path,
            classification=classification,
            date_result=date_result,
            archive_base=config.archive,
            review_dir=config.review,
        )
        logger.info("Done: %s", dest.name)
        return dest
    except Exception as exc:
        logger.error("Archiving failed for %s: %s", processing_path.name, exc)
        _move_to_error(processing_path, config.input_error)
        return None


def _move_to_error(src: Path, error_dir: Path) -> None:
    dest = error_dir / src.name
    try:
        shutil.move(str(src), str(dest))
        logger.info("Moved to input_error: %s", dest.name)
    except OSError as exc:
        logger.error("Could not move %s to input_error: %s", src.name, exc)
