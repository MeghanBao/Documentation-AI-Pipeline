"""
4-stage date extraction with confidence scoring.

Stage 1: Explicit labeled date fields (Rechnungsdatum, Ausstellungsdatum, …)
Stage 2: Document-type-specific fields — handled by score weights in _LABELED_FIELDS
Stage 3: All dates in the full text, assigned a generic score
Stage 4: No plausible date found → return None (document → review/)
"""
import logging
import re
from dataclasses import dataclass
from datetime import date

logger = logging.getLogger(__name__)

_MONTH_NAMES_DE: dict[str, int] = {
    "januar": 1, "februar": 2, "märz": 3, "april": 4,
    "mai": 5, "juni": 6, "juli": 7, "august": 8,
    "september": 9, "oktober": 10, "november": 11, "dezember": 12,
}

# --- Date format regexes ---
_RE_DMY_DOT    = re.compile(r"\b(\d{1,2})\.(\d{1,2})\.(\d{4})\b")
_RE_ISO        = re.compile(r"\b(\d{4})-(\d{2})-(\d{2})\b")
_RE_DMY_DASH   = re.compile(r"\b(\d{2})-(\d{2})-(\d{4})\b")
_RE_DMY_SLASH  = re.compile(r"\b(\d{2})/(\d{2})/(\d{4})\b")
_RE_MONTH_YEAR = re.compile(r"\b(\d{1,2})\.(\d{4})\b")           # month-only: 02.2025
_RE_MONTH_NAME = re.compile(                                       # day + name + year
    r"\b(\d{1,2})\s+(" + "|".join(_MONTH_NAMES_DE) + r")\s+(\d{4})\b",
    re.IGNORECASE,
)
_RE_MONTH_NAME_ONLY = re.compile(                                  # name + year, no day
    r"\b(" + "|".join(_MONTH_NAMES_DE) + r")\s+(\d{4})\b",
    re.IGNORECASE,
)

# --- Labeled fields with score weights (Stage 1 + 2) ---
# Higher score = higher confidence that this is the authoritative document date.
_LABELED_FIELDS: list[tuple[re.Pattern[str], int]] = [
    (re.compile(r"rechnungsdatum\s*[:=]?\s*",    re.IGNORECASE), 100),
    (re.compile(r"ausstellungsdatum\s*[:=]?\s*", re.IGNORECASE),  90),
    (re.compile(r"bescheiddatum\s*[:=]?\s*",     re.IGNORECASE),  90),
    (re.compile(r"vertragsdatum\s*[:=]?\s*",     re.IGNORECASE),  85),
    (re.compile(r"schreiben\s+vom\s*[:=]?\s*",   re.IGNORECASE),  80),
    (re.compile(r"(?<!\w)datum\s*[:=]?\s*",      re.IGNORECASE),  70),
    (re.compile(r"abrechnungsmonat\s*[:=]?\s*",  re.IGNORECASE),  65),
    (re.compile(r"fälligkeitsdatum\s*[:=]?\s*",  re.IGNORECASE),  30),
    (re.compile(r"fällig\s+am\s*[:=]?\s*",       re.IGNORECASE),  30),
    (re.compile(r"geburtsdatum\s*[:=]?\s*",      re.IGNORECASE),  10),
]

# Score assigned to every date found during the generic full-text scan (Stage 3)
_GENERIC_DATE_SCORE = 40


@dataclass
class DateResult:
    date_str: str    # "YYYY-MM-DD" or "YYYY-MM" (month-only)
    score: int
    month_only: bool = False


def extract_date(text: str, min_score: int = 30) -> DateResult | None:
    """
    Return the most confident DateResult found in *text*, or None.

    None means no date met the minimum confidence threshold → document
    should be routed to the review/ folder.
    """
    candidates: list[DateResult] = []

    # Stage 1 + 2: scan for labeled fields and extract the date that follows.
    # Snippet is capped at 20 chars — enough for any supported date format
    # ("18 Februar 2021" = 15 chars) without bleeding into adjacent content.
    for label_re, base_score in _LABELED_FIELDS:
        for m in label_re.finditer(text):
            snippet = text[m.end(): m.end() + 20]
            result = _first_date_in(snippet, base_score)
            if result:
                logger.debug("Labeled date (score=%d): %s", result.score, result.date_str)
                candidates.append(result)

    # Stage 3: generic full-text scan — only runs when Stage 1+2 found nothing.
    # Per spec: "Falls kein Feld erkannt wird: alle Datumsangaben analysieren."
    if not candidates:
        for m in _RE_DMY_DOT.finditer(text):
            d = _to_date(int(m[1]), int(m[2]), int(m[3]))
            if d:
                candidates.append(DateResult(d.isoformat(), _GENERIC_DATE_SCORE))

        for m in _RE_ISO.finditer(text):
            d = _to_date(int(m[3]), int(m[2]), int(m[1]))  # YYYY-MM-DD → day=m[3]
            if d:
                candidates.append(DateResult(d.isoformat(), _GENERIC_DATE_SCORE))

        for m in _RE_DMY_DASH.finditer(text):
            d = _to_date(int(m[1]), int(m[2]), int(m[3]))
            if d:
                candidates.append(DateResult(d.isoformat(), _GENERIC_DATE_SCORE))

        for m in _RE_DMY_SLASH.finditer(text):
            d = _to_date(int(m[1]), int(m[2]), int(m[3]))
            if d:
                candidates.append(DateResult(d.isoformat(), _GENERIC_DATE_SCORE))

        for m in _RE_MONTH_NAME.finditer(text):
            d = _to_date(int(m[1]), _MONTH_NAMES_DE[m[2].lower()], int(m[3]))
            if d:
                candidates.append(DateResult(d.isoformat(), _GENERIC_DATE_SCORE))

    # Stage 4: no plausible date
    if not candidates:
        logger.debug("No date candidates found in document")
        return None

    best = max(candidates, key=lambda r: r.score)
    if best.score < min_score:
        logger.debug("Best date score %d < threshold %d", best.score, min_score)
        return None

    logger.debug("Selected date: %s (score=%d)", best.date_str, best.score)
    return best


def _first_date_in(text: str, base_score: int) -> DateResult | None:
    """Parse the first recognizable date format from a short snippet."""
    checks: list[tuple[re.Pattern[str], object]] = [
        (_RE_DMY_DOT,    lambda m: _to_date(int(m[1]), int(m[2]), int(m[3]))),
        (_RE_ISO,        lambda m: _to_date(int(m[3]), int(m[2]), int(m[1]))),
        (_RE_DMY_DASH,   lambda m: _to_date(int(m[1]), int(m[2]), int(m[3]))),
        (_RE_DMY_SLASH,  lambda m: _to_date(int(m[1]), int(m[2]), int(m[3]))),
        (_RE_MONTH_NAME, lambda m: _to_date(int(m[1]), _MONTH_NAMES_DE[m[2].lower()], int(m[3]))),
    ]
    for regex, mk in checks:
        m = regex.search(text)
        if m:
            d = mk(m)  # type: ignore[operator]
            if d:
                return DateResult(d.isoformat(), base_score)

    # Month-only: numeric "02.2025"
    m = _RE_MONTH_YEAR.search(text)
    if m:
        month, year = int(m[1]), int(m[2])
        if 1 <= month <= 12 and 1900 <= year <= 2100:
            return DateResult(f"{year:04d}-{month:02d}", base_score, month_only=True)

    # Month-only: named "Februar 2025" (used in payslip Abrechnungsmonat fields)
    m = _RE_MONTH_NAME_ONLY.search(text)
    if m:
        month = _MONTH_NAMES_DE[m[1].lower()]
        year = int(m[2])
        if 1900 <= year <= 2100:
            return DateResult(f"{year:04d}-{month:02d}", base_score, month_only=True)

    return None


def _to_date(day: int, month: int, year: int) -> date | None:
    try:
        return date(year, month, day)
    except ValueError:
        return None
