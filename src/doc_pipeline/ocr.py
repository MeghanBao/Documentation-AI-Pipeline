"""OCR module: PyMuPDF native extraction → Tesseract fallback → PaddleOCR fallback."""
import logging
from pathlib import Path

import fitz  # PyMuPDF
import pytesseract
from PIL import Image

logger = logging.getLogger(__name__)

_IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".tif", ".tiff"}

# Tesseract language code → PaddleOCR language name
_TESSERACT_TO_PADDLE_LANG: dict[str, str] = {
    "deu": "german",
    "eng": "en",
    "fra": "french",
    "chi_sim": "ch",
    "chi_tra": "chinese_cht",
    "jpn": "japan",
    "kor": "korean",
}

# Module-level PaddleOCR instance cache (keyed by PaddleOCR language name)
_paddle_cache: dict[str, object] = {}


def extract_text(
    file_path: Path,
    lang: str = "deu",
    min_chars_per_page: int = 50,
    paddleocr_enabled: bool = True,
) -> str:
    """
    Extract full text from a PDF or image file using a 3-stage engine chain.

    Stage 1 — PyMuPDF: use embedded text when the page has enough characters.
    Stage 2 — Tesseract: re-OCR sparse/scanned pages.
    Stage 3 — PaddleOCR: if Tesseract output is still sparse and
               ``paddleocr_enabled=True``, try PaddleOCR as a final fallback.
               PaddleOCR is an optional dependency; import failures are
               silently skipped so existing functionality is unaffected.

    For image files (PNG/JPG/TIFF): Tesseract only (no PaddleOCR fallback).
    """
    suffix = file_path.suffix.lower()
    if suffix == ".pdf":
        return _extract_from_pdf(file_path, lang, min_chars_per_page, paddleocr_enabled)
    if suffix in _IMAGE_EXTENSIONS:
        return _ocr_image_file(file_path, lang)
    raise ValueError(f"Unsupported file type: {suffix}")


def _extract_from_pdf(
    pdf_path: Path,
    lang: str,
    min_chars_per_page: int,
    paddleocr_enabled: bool,
) -> str:
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
            logger.debug(
                "Page %d: native text too short (%d chars), running Tesseract",
                page.number, len(native),
            )
            tess_text = _ocr_page(page, lang)

            if len(tess_text) >= min_chars_per_page or not paddleocr_enabled:
                pages.append(tess_text)
            else:
                # Stage 3: both native and Tesseract gave sparse output
                logger.debug(
                    "Page %d: Tesseract gave %d chars, trying PaddleOCR",
                    page.number, len(tess_text),
                )
                try:
                    paddle_text = _ocr_page_paddle(page, lang)
                except Exception as exc:  # noqa: BLE001
                    logger.warning("PaddleOCR page %d failed: %s", page.number, exc)
                    paddle_text = ""
                # Prefer PaddleOCR result only if it produced something
                pages.append(paddle_text if paddle_text else tess_text)

    doc.close()
    return "\n".join(pages)


def _ocr_page(page: fitz.Page, lang: str) -> str:
    """Render a PDF page at 2× resolution and run Tesseract."""
    matrix = fitz.Matrix(2.0, 2.0)
    pix = page.get_pixmap(matrix=matrix)
    img = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)
    return _run_tesseract(img, lang)


def _ocr_page_paddle(page: fitz.Page, lang: str) -> str:
    """Render a PDF page at 2× resolution and run PaddleOCR."""
    matrix = fitz.Matrix(2.0, 2.0)
    pix = page.get_pixmap(matrix=matrix)
    img = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)
    return _run_paddleocr(img, lang)


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


# ---------------------------------------------------------------------------
# PaddleOCR — optional third-stage engine
# ---------------------------------------------------------------------------

def _load_paddleocr(paddle_lang: str) -> object:
    """Instantiate a PaddleOCR object. Raises ImportError if not installed."""
    from paddleocr import PaddleOCR  # noqa: PLC0415
    return PaddleOCR(lang=paddle_lang, use_angle_cls=True, use_gpu=False, show_log=False)


def _get_paddleocr(lang: str) -> object:
    """Return a cached PaddleOCR instance, creating one on first call."""
    paddle_lang = _TESSERACT_TO_PADDLE_LANG.get(lang, "german")
    if paddle_lang not in _paddle_cache:
        _paddle_cache[paddle_lang] = _load_paddleocr(paddle_lang)
    return _paddle_cache[paddle_lang]


def _run_paddleocr(img: Image.Image, lang: str) -> str:
    """
    Run PaddleOCR on *img*.

    Returns the recognised text joined by newlines, or an empty string when:
    - PaddleOCR is not installed (ImportError silently caught)
    - PaddleOCR produces no output
    - Any runtime error occurs (logged as warning, not re-raised)
    """
    try:
        import numpy as np  # noqa: PLC0415

        ocr = _get_paddleocr(lang)
        arr = np.array(img)
        results = ocr.ocr(arr, cls=True)
        if not results or not results[0]:
            return ""
        lines = [line[1][0] for line in results[0] if line and len(line) > 1]
        return "\n".join(lines)
    except ImportError:
        logger.debug("PaddleOCR not installed — skipping third-stage OCR")
        return ""
    except Exception as exc:  # noqa: BLE001
        logger.warning("PaddleOCR failed: %s", exc)
        return ""
