"""Tests for keyword-based document classification."""
import pytest

from doc_pipeline.classifier import Classification, classify


# ---------------------------------------------------------------------------
# Document type detection
# ---------------------------------------------------------------------------

class TestDocumentTypeDetection:

    def test_rechnung(self):
        result = classify("Rechnung Nr. 1234. Betrag: 150 EUR inkl. MwSt.")
        assert result.doc_type == "Rechnung"
        assert result.archive_subdir == "Rechnungen"
        assert result.confident is True

    def test_rechnung_invoice_keyword(self):
        result = classify("Invoice 2025-001. Total amount 200 EUR.")
        assert result.doc_type == "Rechnung"

    def test_versicherung(self):
        result = classify("Ihre Versicherungspolice Nr. 54321. Jahresbeitrag 320 EUR.")
        assert result.doc_type == "Versicherung"
        assert result.archive_subdir == "Versicherung"
        assert result.confident is True

    def test_versicherung_police_keyword(self):
        result = classify("Police Nr. 99. Beitrag fällig am 01.01.2025.")
        assert result.doc_type == "Versicherung"

    def test_steuerbescheid(self):
        result = classify("Einkommensteuerbescheid 2023. Finanzamt Bamberg.")
        assert result.doc_type == "Steuerbescheid"
        assert result.archive_subdir == "Steuer"
        assert result.confident is True

    def test_finanzamt_keyword(self):
        result = classify("Bescheid des Finanzamts über Einkommensteuer.")
        assert result.doc_type == "Steuerbescheid"

    def test_lohnabrechnung(self):
        result = classify("Lohnabrechnung für den Monat März 2025. Bruttogehalt: 3500 EUR.")
        assert result.doc_type == "Lohnabrechnung"
        assert result.archive_subdir == "Arbeit"
        assert result.confident is True

    def test_gehaltsabrechnung_synonym(self):
        result = classify("Gehaltsabrechnung April 2025. Nettogehalt 2800 EUR.")
        assert result.doc_type == "Lohnabrechnung"

    def test_entgeltabrechnung_synonym(self):
        result = classify("Entgeltabrechnung Mai 2025.")
        assert result.doc_type == "Lohnabrechnung"

    def test_vertrag(self):
        result = classify("Mietvertrag zwischen Vermieter und Mieter. Vertragsbeginn 01.01.2025.")
        assert result.doc_type == "Vertrag"
        assert result.archive_subdir == "Verträge"
        assert result.confident is True

    def test_kuendigung_keyword(self):
        result = classify("Hiermit kündigen wir den Vertrag zum 31.12.2025.")
        assert result.doc_type == "Vertrag"

    def test_bescheid(self):
        result = classify("Ablehnungsbescheid Ihres Widerspruchs vom 01.12.2024.")
        assert result.doc_type == "Bescheid"
        assert result.archive_subdir == "Steuer"
        assert result.confident is True

    def test_unknown_returns_sonstiges(self):
        result = classify("Hallo Welt! Das Wetter ist heute wunderschön.", fallback_stem="random")
        assert result.doc_type == "Dokument"
        assert result.archive_subdir == "Sonstiges"
        assert result.confident is False

    def test_empty_text_returns_sonstiges(self):
        result = classify("", fallback_stem="leer")
        assert result.archive_subdir == "Sonstiges"
        assert result.confident is False


class TestPriorityOrdering:
    """More specific types must beat general ones when keywords overlap."""

    def test_lohnabrechnung_beats_rechnung(self):
        # Both "Lohnabrechnung" and "Rechnung" keywords are present
        text = "Lohnabrechnung Bruttogehalt Rechnung"
        assert classify(text).doc_type == "Lohnabrechnung"

    def test_steuerbescheid_beats_bescheid(self):
        text = "Steuerbescheid Finanzamt Bescheid Bewilligung"
        assert classify(text).doc_type == "Steuerbescheid"


class TestThemaDetection:

    def test_strom(self):
        result = classify("Rechnung für Stromlieferung im Monat Januar.")
        assert result.thema == "Strom"

    def test_gas(self):
        result = classify("Rechnung für Erdgaslieferung.")
        assert result.thema == "Gas"

    def test_internet(self):
        result = classify("Rechnung für Internet-Anschluss. Betrag 40 EUR.")
        assert result.thema == "Internet"

    def test_haftpflicht(self):
        result = classify("Haftpflichtversicherung. Jahresbeitrag 80 EUR.")
        assert result.thema == "Haftpflicht"

    def test_hausrat(self):
        result = classify("Hausratversicherung Schaden.")
        assert result.thema == "Hausrat"

    def test_kfz(self):
        result = classify("KFZ-Versicherung für Ihr Fahrzeug.")
        assert result.thema == "KFZ"

    def test_mietvertrag(self):
        result = classify("Mietvertrag Wohnung Laufzeit 12 Monate.")
        assert result.thema == "Mietvertrag"

    def test_thema_fallback_to_sanitized_stem(self):
        result = classify("Rechnung ohne bekanntes Thema.", fallback_stem="scan_2025_01")
        assert result.thema == "scan_2025_01"

    def test_thema_stem_sanitized(self):
        result = classify("Rechnung ohne Thema.", fallback_stem="scan 2025!@#")
        # Special chars should be replaced with underscores
        assert " " not in result.thema
        assert "!" not in result.thema


class TestCaseInsensitivity:

    def test_uppercase_keywords_matched(self):
        result = classify("RECHNUNG NR. 1234. BETRAG 150 EUR INKL. MWST.")
        assert result.doc_type == "Rechnung"

    def test_mixed_case_keywords(self):
        result = classify("VeRsIcHeRuNg Police 12345")
        assert result.doc_type == "Versicherung"
