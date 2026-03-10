"""OCR module: native PDF text extraction (PyMuPDF) with Tesseract fallback."""
import logging
from pathlib import Path

import fitz  # PyMuPDF
import pytesseract
from PIL import Image

logger = logging.getLogger(__name__)

_IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".tif", ".tiff"}


def extract_text(
    file_path: Path,
    lang: str = "deu",
    min_chars_per_page: int = 50,
) -> str:
    """
    Extract full text from a PDF or image file.

    For PDFs: uses native embedded text first; falls back to Tesseract OCR
    per page when the embedded text is too short (likely a scanned page).
    For images: runs Tesseract directly.
    """
    suffix = file_path.suffix.lower()
    if suffix == ".pdf":
        return _extract_from_pdf(file_path, lang, min_chars_per_page)
    if suffix in _IMAGE_EXTENSIONS:
        return _ocr_image_file(file_path, lang)
    raise ValueError(f"Unsupported file type: {suffix}")


def _extract_from_pdf(pdf_path: Path, lang: str, min_chars_per_page: int) -> str:
    try:
        doc = fitz.open(str(pdf_path))
    except Exception as exc:
        raise RuntimeError(f"Cannot open PDF: {pdf_path}") from exc

    pages: list[str] = []
    for page in doc:
        native = page.get_text().strip()
        if len(native) >= min_chars_per_page:
            pages.append(native)
        else:
            logger.debug("Page %d: native text too short (%d chars), running OCR", page.number, len(native))
            pages.append(_ocr_page(page, lang))

    doc.close()
    return "\n".join(pages)


def _ocr_page(page: fitz.Page, lang: str) -> str:
    """Render a PDF page at 2× resolution and run Tesseract."""
    matrix = fitz.Matrix(2.0, 2.0)
    pix = page.get_pixmap(matrix=matrix)
    img = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)
    return _run_tesseract(img, lang)


def _ocr_image_file(image_path: Path, lang: str) -> str:
    try:
        img = Image.open(str(image_path))
    except Exception as exc:
        raise RuntimeError(f"Cannot open image: {image_path}") from exc
    return _run_tesseract(img, lang)


def _run_tesseract(img: Image.Image, lang: str) -> str:
    config = f"--oem 3 --psm 3 -l {lang}"
    try:
        return pytesseract.image_to_string(img, config=config)
    except pytesseract.TesseractError as exc:
        logger.warning("Tesseract failed: %s", exc)
        return ""
