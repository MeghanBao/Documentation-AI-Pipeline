"""Tests for the 4-stage date extraction and scoring system."""
import pytest

from doc_pipeline.date_extractor import DateResult, extract_date


# ---------------------------------------------------------------------------
# Stage 1: Explicit labeled date fields — score correctness
# ---------------------------------------------------------------------------

class TestLabeledFields:

    def test_rechnungsdatum_score_100(self):
        result = extract_date("Rechnungsdatum: 18.02.2021")
        assert result is not None
        assert result.score == 100
        assert result.date_str == "2021-02-18"

    def test_ausstellungsdatum_score_90(self):
        result = extract_date("Ausstellungsdatum: 18.02.2021")
        assert result is not None
        assert result.score == 90
        assert result.date_str == "2021-02-18"

    def test_bescheiddatum_score_90(self):
        result = extract_date("Bescheiddatum: 18.02.2021")
        assert result is not None
        assert result.score == 90

    def test_vertragsdatum_score_85(self):
        result = extract_date("Vertragsdatum: 18.02.2021")
        assert result is not None
        assert result.score == 85

    def test_schreiben_vom_score_80(self):
        result = extract_date("Schreiben vom 18.02.2021")
        assert result is not None
        assert result.score == 80

    def test_datum_label_score_70(self):
        result = extract_date("Datum: 18.02.2021")
        assert result is not None
        assert result.score == 70

    def test_faelligkeitsdatum_score_30(self):
        # Score 30 == default min_score; should still be returned
        result = extract_date("Fälligkeitsdatum: 18.02.2021", min_score=30)
        assert result is not None
        assert result.score == 30

    def test_geburtsdatum_score_10_below_threshold(self):
        # Score 10 < default min_score 30 → should be filtered out
        result = extract_date("Geburtsdatum: 01.01.1980", min_score=30)
        assert result is None

    def test_geburtsdatum_returned_with_low_threshold(self):
        result = extract_date("Geburtsdatum: 01.01.1980", min_score=5)
        assert result is not None
        assert result.date_str == "1980-01-01"

    def test_label_with_equals_separator(self):
        result = extract_date("Rechnungsdatum = 18.02.2021")
        assert result is not None
        assert result.date_str == "2021-02-18"

    def test_label_without_separator(self):
        result = extract_date("Rechnungsdatum 18.02.2021")
        assert result is not None
        assert result.date_str == "2021-02-18"


# ---------------------------------------------------------------------------
# Stage 2: Document-type-specific — Abrechnungsmonat (month-only)
# ---------------------------------------------------------------------------

class TestAbrechnungsmonat:

    def test_month_only_date_str(self):
        result = extract_date("Abrechnungsmonat: 02.2021")
        assert result is not None
        assert result.date_str == "2021-02"
        assert result.month_only is True

    def test_month_only_score_65(self):
        result = extract_date("Abrechnungsmonat: 02.2021")
        assert result is not None
        assert result.score == 65

    def test_month_only_beats_generic_full_date(self):
        # Generic full date score=40 should lose to Abrechnungsmonat score=65
        text = "Abrechnungsmonat: 02.2021\nZahlungsdatum 05.01.2020"
        result = extract_date(text)
        assert result is not None
        assert result.date_str == "2021-02"


# ---------------------------------------------------------------------------
# Stage 3: Generic full-text scan
# ---------------------------------------------------------------------------

class TestGenericDateScan:

    def test_generic_date_score_40(self):
        result = extract_date("Der Vertrag gilt ab 18.02.2021 bis auf Weiteres.")
        assert result is not None
        assert result.score == 40

    def test_multiple_unlabeled_dates_returns_a_result(self):
        # Both dates have score 40; any valid result is acceptable
        text = "Erstellt am 01.01.2020. Gültig bis 31.12.2025."
        result = extract_date(text)
        assert result is not None
        assert result.score == 40

    def test_labeled_beats_generic(self):
        text = "Zahlungsziel 01.01.2020\nRechnungsdatum: 15.02.2021"
        result = extract_date(text)
        assert result is not None
        assert result.date_str == "2021-02-15"
        assert result.score == 100


# ---------------------------------------------------------------------------
# Stage 4: No date found
# ---------------------------------------------------------------------------

class TestNoDatFound:

    def test_no_date_returns_none(self):
        assert extract_date("Kein Datum in diesem Text vorhanden.") is None

    def test_empty_text_returns_none(self):
        assert extract_date("") is None

    def test_score_below_threshold_returns_none(self):
        # Only a Geburtsdatum (score=10) present, threshold=30
        result = extract_date("Geburtsdatum: 01.01.1980", min_score=30)
        assert result is None

    def test_invalid_date_ignored(self):
        # 32.13.2021 is not a valid calendar date
        result = extract_date("Datum: 32.13.2021")
        assert result is None

    def test_invalid_month_zero_ignored(self):
        result = extract_date("Datum: 01.00.2021")
        assert result is None


# ---------------------------------------------------------------------------
# Date format coverage
# ---------------------------------------------------------------------------

class TestDateFormats:

    def test_dmy_dot(self):
        result = extract_date("Datum: 18.02.2021")
        assert result is not None
        assert result.date_str == "2021-02-18"

    def test_iso(self):
        result = extract_date("Rechnungsdatum: 2021-02-18")
        assert result is not None
        assert result.date_str == "2021-02-18"

    def test_dmy_dash(self):
        result = extract_date("Datum: 18-02-2021")
        assert result is not None
        assert result.date_str == "2021-02-18"

    def test_dmy_slash(self):
        result = extract_date("Datum: 18/02/2021")
        assert result is not None
        assert result.date_str == "2021-02-18"

    def test_german_month_name_januar(self):
        result = extract_date("Schreiben vom 5 Januar 2025")
        assert result is not None
        assert result.date_str == "2025-01-05"

    def test_german_month_name_dezember(self):
        result = extract_date("Datum: 31 Dezember 2024")
        assert result is not None
        assert result.date_str == "2024-12-31"

    def test_german_month_name_case_insensitive(self):
        result = extract_date("Datum: 1 JANUAR 2025")
        assert result is not None
        assert result.date_str == "2025-01-01"

    def test_single_digit_day(self):
        result = extract_date("Datum: 5.03.2025")
        assert result is not None
        assert result.date_str == "2025-03-05"

    def test_all_twelve_months(self):
        months = [
            ("Januar", 1), ("Februar", 2), ("März", 3), ("April", 4),
            ("Mai", 5), ("Juni", 6), ("Juli", 7), ("August", 8),
            ("September", 9), ("Oktober", 10), ("November", 11), ("Dezember", 12),
        ]
        for name, number in months:
            result = extract_date(f"Datum: 1 {name} 2024")
            assert result is not None, f"Failed for month: {name}"
            assert result.date_str == f"2024-{number:02d}-01"

    def test_year_boundary_valid(self):
        result = extract_date("Datum: 31.12.2099")
        assert result is not None

    def test_leap_year_feb29(self):
        result = extract_date("Datum: 29.02.2024")  # 2024 is a leap year
        assert result is not None
        assert result.date_str == "2024-02-29"

    def test_invalid_feb29_non_leap(self):
        result = extract_date("Datum: 29.02.2023")  # 2023 is not a leap year
        # Should either return None or some other valid date from the text
        # The important thing is that this invalid date is not returned
        if result is not None:
            assert result.date_str != "2023-02-29"


# ---------------------------------------------------------------------------
# Min-score threshold
# ---------------------------------------------------------------------------

class TestMinScore:

    def test_custom_min_score_zero_always_returns(self):
        result = extract_date("Datum: 18.02.2021", min_score=0)
        assert result is not None

    def test_min_score_higher_than_any_possible(self):
        result = extract_date("Rechnungsdatum: 18.02.2021", min_score=101)
        assert result is None
