"""Filename generation and document archiving."""
import logging
import re
import shutil
from pathlib import Path
from typing import Optional

from .classifier import Classification
from .date_extractor import DateResult

logger = logging.getLogger(__name__)


def build_filename(
    classification: Classification,
    date_result: Optional[DateResult],
    original_stem: str,
) -> tuple[str, bool]:
    """
    Build the archive filename stem (without extension).

    Returns (stem, is_uncertain).
    Uncertain documents get the UNSICHER_ prefix and are routed to review/.

    Normal:    YYYY-MM-DD_Rechnung_Strom
    Uncertain: UNSICHER_Rechnung_scan_001
    """
    uncertain = not classification.confident or date_result is None

    if uncertain:
        type_part = classification.doc_type  # always show detected type per spec
        safe_stem = _sanitize(original_stem)[:30]
        return f"UNSICHER_{type_part}_{safe_stem}", True

    date_part = date_result.date_str  # "YYYY-MM-DD" or "YYYY-MM"
    return f"{date_part}_{classification.doc_type}_{classification.thema}", False


def archive_document(
    src_path: Path,
    classification: Classification,
    date_result: Optional[DateResult],
    archive_base: Path,
    review_dir: Path,
) -> Path:
    """
    Move *src_path* to the correct destination with the generated filename.

    Returns the final destination path.
    """
    stem, uncertain = build_filename(classification, date_result, src_path.stem)
    dest_name = stem + src_path.suffix.lower()

    dest_dir = review_dir if uncertain else archive_base / classification.archive_subdir
    dest_path = _unique_path(dest_dir / dest_name)

    shutil.move(str(src_path), str(dest_path))
    logger.info("Archived: %s → %s", src_path.name, dest_path)
    return dest_path


def _unique_path(path: Path) -> Path:
    """Append an incrementing counter if a file with this name already exists."""
    if not path.exists():
        return path
    stem, suffix = path.stem, path.suffix
    counter = 1
    while True:
        candidate = path.parent / f"{stem}_{counter}{suffix}"
        if not candidate.exists():
            return candidate
        counter += 1


def _sanitize(name: str) -> str:
    name = re.sub(r"[^\w\-]", "_", name, flags=re.UNICODE)
    return re.sub(r"_+", "_", name).strip("_") or "Dokument"
