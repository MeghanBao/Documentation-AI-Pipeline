"""Document classification via keyword matching."""
import re
from dataclasses import dataclass


@dataclass
class Classification:
    doc_type: str       # e.g. "Rechnung"
    archive_subdir: str # e.g. "Rechnungen"
    thema: str          # e.g. "Strom"
    confident: bool     # False → document goes to review/
    matched_keyword: str = ""  # the type keyword that triggered this (for provenance)


# (doc_type, archive_subdir, keyword_list)
# Order matters: more specific types first (Lohnabrechnung before Rechnung).
_TYPE_RULES: list[tuple[str, str, list[str]]] = [
    ("Lohnabrechnung", "Arbeit",       ["lohnabrechnung", "gehaltsabrechnung", "entgeltabrechnung",
                                         "bruttogehalt", "nettogehalt", "bruttolohn", "nettolohn"]),
    ("Steuerbescheid", "Steuer",       ["steuerbescheid", "einkommensteuerbescheid",
                                         "finanzamt", "steuererkl", "lohnsteuer", "einkommensteuer"]),
    ("Bescheid",       "Steuer",       ["bescheid", "bewilligung", "ablehnungsbescheid"]),
    ("Rechnung",       "Rechnungen",   ["rechnung", "invoice", "rechnungsbetrag",
                                         "mehrwertsteuer", "mwst"]),
    ("Versicherung",   "Versicherung", ["versicherung", "versicherungsschein", "police",
                                         "versicherungsbeitrag", "schadensfall"]),
    ("Vertrag",        "Verträge",     ["vertrag", "vereinbarung", "vertragslaufzeit",
                                         "vertragspartner", "kündigung"]),
]

# Thema keywords searched across all document types.
# More specific terms first.
_THEMA_RULES: list[tuple[str, str]] = [
    ("mietvertrag",        "Mietvertrag"),
    ("arbeitsvertrag",     "Arbeitsvertrag"),
    ("darlehen",           "Darlehen"),
    ("kredit",             "Kredit"),
    ("haftpflicht",        "Haftpflicht"),
    ("hausrat",            "Hausrat"),
    ("rechtsschutz",       "Rechtsschutz"),
    ("lebensversicherung", "Lebensversicherung"),
    ("rentenversicherung", "Rentenversicherung"),
    ("unfallversicherung", "Unfall"),
    ("krankenversicherung","Krankenversicherung"),
    ("kfz",                "KFZ"),
    ("zahnarzt",           "Zahnarzt"),
    ("apotheke",           "Apotheke"),
    ("arzt",               "Arzt"),
    ("bruttogehalt",       "Gehalt"),
    ("bruttolohn",         "Gehalt"),
    ("nettogehalt",        "Gehalt"),
    ("nettolohn",          "Gehalt"),
    ("strom",              "Strom"),
    ("erdgas",             "Gas"),
    ("gas",                "Gas"),
    ("wasser",             "Wasser"),
    ("internet",           "Internet"),
    ("mobilfunk",          "Mobilfunk"),
    ("handy",              "Mobilfunk"),
    ("telefon",            "Telefon"),
    ("miete",              "Miete"),
    ("nebenkosten",        "Nebenkosten"),
    ("amazon",             "Amazon"),
    ("ebay",               "Ebay"),
]


def classify(text: str, fallback_stem: str = "Dokument") -> Classification:
    """
    Classify a document by keyword matching.

    Returns a Classification with confident=False when no type is detected
    (document will be routed to review/).
    """
    lower = text.lower()

    matched_type: str | None = None
    matched_subdir: str | None = None
    matched_kw: str | None = None
    for doc_type, archive_subdir, keywords in _TYPE_RULES:
        hit = next((kw for kw in keywords if kw in lower), None)
        if hit is not None:
            matched_type = doc_type
            matched_subdir = archive_subdir
            matched_kw = hit
            break

    if matched_type is None:
        return Classification(
            doc_type="Dokument",
            archive_subdir="Sonstiges",
            thema=_sanitize(fallback_stem),
            confident=False,
        )

    thema: str | None = None
    for keyword, label in _THEMA_RULES:
        if keyword in lower:
            thema = label
            break

    return Classification(
        doc_type=matched_type,
        archive_subdir=matched_subdir,
        thema=thema or _sanitize(fallback_stem),
        confident=True,
        matched_keyword=matched_kw or "",
    )


def _sanitize(name: str) -> str:
    """Strip characters unsafe for filenames and truncate."""
    name = re.sub(r"[^\w\-]", "_", name, flags=re.UNICODE)
    name = re.sub(r"_+", "_", name).strip("_")
    return name[:40] or "Dokument"
