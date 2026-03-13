#!/usr/bin/env python3
"""
Generate the three test-fixture PDFs used by test_integration.py.

Run once (or whenever fixtures need regenerating):
    python tests/fixtures/generate_fixtures.py
"""
from pathlib import Path

from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas

OUT = Path(__file__).parent


def make_pdf(filename: str, lines: list[str]) -> None:
    path = OUT / filename
    c = canvas.Canvas(str(path), pagesize=A4)
    c.setFont("Helvetica", 11)
    y = 760
    for line in lines:
        c.drawString(72, y, line)
        y -= 18
    c.save()
    print(f"  created: {path.name}")


# ------------------------------------------------------------------
# 1. Rechnung Strom  —  Rechnungsdatum: 15.03.2025
# ------------------------------------------------------------------
make_pdf("rechnung_strom.pdf", [
    "Stadtwerke Musterstadt GmbH",
    "Kundennummer: 4711-0815",
    "",
    "Rechnungsdatum: 15.03.2025",
    "",
    "Ihre Stromrechnung fuer den Monat Maerz 2025.",
    "",
    "Verbrauch:         350 kWh Strom",
    "Nettobetrag:        71,76 EUR",
    "MwSt. 19%:          13,64 EUR",
    "Rechnungsbetrag:    85,40 EUR",
    "",
    "Bitte begleichen Sie diesen Rechnungsbetrag bis zum 05.04.2025.",
    "IBAN: DE89 3704 0044 0532 0130 00",
])

# ------------------------------------------------------------------
# 2. Versicherung Haftpflicht  —  Schreiben vom 20.01.2025
# ------------------------------------------------------------------
make_pdf("versicherung_haftpflicht.pdf", [
    "Muster Versicherung AG",
    "Police Nr. 98765432",
    "",
    "Schreiben vom 20.01.2025",
    "",
    "Sehr geehrte Damen und Herren,",
    "",
    "hiermit bestaetigen wir Ihre Haftpflichtversicherung.",
    "Versicherungsbeitrag: 89,00 EUR jaehrlich.",
    "Versicherungsnehmer: Max Mustermann",
    "",
    "Naechste Beitragsrate faellig: 01.02.2025",
    "Vertragslaufzeit: 12 Monate",
])

# ------------------------------------------------------------------
# 3. Lohnabrechnung  —  Abrechnungsmonat: Februar 2025
# ------------------------------------------------------------------
make_pdf("lohnabrechnung_feb_2025.pdf", [
    "Musterfirma GmbH",
    "Lohnabrechnung",
    "",
    "Abrechnungsmonat: Februar 2025",
    "Arbeitnehmer: Max Mustermann",
    "Personalnummer: 1234",
    "",
    "Bruttogehalt:      3.500,00 EUR",
    "Nettogehalt:       2.280,00 EUR",
    "",
    "Steuerklasse: I",
    "Sozialversicherung: 819,30 EUR",
    "Lohnsteuer: 400,70 EUR",
])

print("Done.")
