"""Filename generation and document archiving."""
import logging
import re
import shutil
from pathlib import Path
from typing import Optional

from .classifier import Classification
from .date_extractor import DateResult

logger = logging.getLogger(__name__)

# Windows default MAX_PATH limit (characters including null terminator)
_MAX_PATH = 259


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
    review_reason: str = "",
    original_name: str = "",
) -> Path:
    """
    Move *src_path* to the correct destination with the generated filename.

    *review_reason* is written as a sidecar .reason.txt in review/ so the
    user knows why the document was flagged for manual inspection.
    *original_name* is used as the fallback stem (instead of the UUID-tagged
    processing filename) for UNSICHER_ filenames.

    Returns the final destination path.
    Raises OSError if the destination path exceeds the Windows 260-char limit.
    """
    fallback_stem = Path(original_name).stem if original_name else src_path.stem
    stem, uncertain = build_filename(classification, date_result, fallback_stem)
    dest_name = stem + src_path.suffix.lower()

    dest_dir = review_dir if uncertain else archive_base / classification.archive_subdir
    dest_path = _unique_path(dest_dir / dest_name)

    _check_path_length(dest_path)

    shutil.move(str(src_path), str(dest_path))
    logger.info("Archived: %s → %s", src_path.name, dest_path)

    # Write sidecar reason file so the user knows why this went to review/
    if uncertain and review_reason:
        reason_path = dest_path.with_suffix(".reason.txt")
        try:
            reason_path.write_text(
                f"Originaldatei: {original_name or src_path.name}\n"
                f"Grund: {review_reason}\n",
                encoding="utf-8",
            )
            logger.debug("Review reason written: %s", reason_path.name)
        except OSError as exc:
            logger.warning("Could not write review reason file: %s", exc)

    return dest_path


def _check_path_length(path: Path) -> None:
    """Raise OSError with a clear message if path exceeds the Windows 260-char limit."""
    length = len(str(path))
    if length > _MAX_PATH:
        raise OSError(
            f"Destination path exceeds Windows 260-character limit "
            f"({length} chars): {path}\n"
            "Tip: shorten PIPELINE_BASE_DIR or enable long path support in Windows."
        )


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
