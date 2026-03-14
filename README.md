# Dokumenten-KI Pipeline

> **English** | [Deutsch](#deutsch)

---

## English

### Overview

A fully local, privacy-friendly automated document pipeline for home networks.
It watches NAS input folders, extracts text via OCR, classifies documents by type, detects the document date using a 4-stage scoring system, generates standardised filenames, and moves each file into the correct archive folder — with zero cloud dependency.

```
Scanner / File drop
        │
        ▼
  NAS Input Folder
        │
        ▼
   Workbot (OCR)
   ┌────┴─────────────────────────────┐
   │  1. Text extraction (PyMuPDF)    │
   │  2. OCR fallback (Tesseract)     │
   │  3. Document type classification │
   │  4. Date extraction & scoring    │
   │  5. Filename generation          │
   └────┬──────────┬──────────────────┘
        │          │
        ▼          ▼
   archiv/      review/   input_error/
```

### Architecture

```
src/doc_pipeline/
├── config.py          PipelineConfig — folder paths, OCR thresholds
├── ocr.py             PyMuPDF native text + per-page Tesseract fallback
├── classifier.py      Keyword-rule doc-type + thema detection
├── date_extractor.py  4-stage scoring date extraction
├── archiver.py        Filename builder + file routing
├── pipeline.py        Orchestrator for a single document
├── watcher.py         watchdog observer (input_scanner/ + input_manual/)
└── main.py            CLI entry point
```

### Module Details

| Module | Responsibility |
|---|---|
| `config.py` | Central `PipelineConfig` dataclass. Set `base_dir` to your NAS path; all sub-folders are derived automatically. `ensure_dirs()` creates the full folder tree. |
| `ocr.py` | Opens PDFs with PyMuPDF. Pages with fewer than `ocr_min_chars_per_page` characters (default: 50) are rendered at 2× resolution and passed to Tesseract. Image files (PNG/JPG/TIFF) go directly to Tesseract. |
| `classifier.py` | Scans lowercase full text against `_TYPE_RULES` (ordered, most-specific first). Returns `doc_type`, `archive_subdir`, `thema`, and a `confident` flag. `confident=False` → document is routed to `review/`. |
| `date_extractor.py` | 4-stage scoring (see below). Returns the highest-scoring `DateResult` or `None`. |
| `archiver.py` | Builds the final filename and moves the file. Appends an incrementing counter on name collisions. |
| `pipeline.py` | Moves file to `processing/`, calls each module in sequence, handles errors per step. |
| `watcher.py` | Watchdog-based observer. Polls file size until stable before triggering `process_document()`. |
| `main.py` | CLI with `--process FILE` (single-file mode) and default watch mode. |
| `ui.py` | Streamlit web UI: drag-and-drop upload, archive browser, settings view. |

### Date Extraction — 4-Stage Scoring

| Stage | Method | Example field | Score |
|---|---|---|---|
| 1 | Explicit labeled date fields | `Rechnungsdatum` | 100 |
| 1 | | `Ausstellungsdatum`, `Bescheiddatum` | 90 |
| 1 | | `Vertragsdatum` | 85 |
| 1 | | `Schreiben vom` | 80 |
| 2 | Doc-type-specific fields | `Abrechnungsmonat` (payslips) | 65 |
| 3 | All dates in full text | any detected date | 40 |
| 4 | Nothing found / score < threshold | → `review/` | — |

Supported formats: `DD.MM.YYYY` · `DD-MM-YYYY` · `YYYY-MM-DD` · `DD/MM/YYYY` · `DD Month YYYY`

### Filename Schema

```
YYYY-MM-DD_Typ_Thema.pdf          # full date known
YYYY-MM_Typ_Thema.pdf             # month only (e.g. payslips)
UNSICHER_Typ_original-stem.pdf    # uncertain → review/
```

**Examples**

```
2025-02-18_Rechnung_Strom.pdf
2024-11-03_Versicherung_Haftpflicht.pdf
2025-01_Lohnabrechnung_Firma.pdf
UNSICHER_Dokument_scan_001.pdf
```

### Folder Structure (NAS)

```
N:\_pipeline\
├── input_scanner\      ← automatic scans from network scanner
├── input_manual\       ← manually dropped files
├── processing\         ← temporary working directory
├── review\             ← uncertain type or date → manual check
├── input_error\        ← OCR failure / corrupt file
└── archiv\
    ├── Rechnungen\
    ├── Versicherung\
    ├── Steuer\
    ├── Arbeit\
    ├── Verträge\
    └── Sonstiges\
```

### Screenshots

> 📸 *Screenshots will be added after first deployment. See placeholder locations below.*

<!-- TODO: replace the placeholder paths with real screenshots after running the UI -->

**Upload & Process tab**
![Upload tab](docs/screenshots/ui_upload.png)
<!-- Screenshot: drag-and-drop file upload with result summary card -->

**Archive browser tab**
![Archive tab](docs/screenshots/ui_archive.png)
<!-- Screenshot: archive browser showing documents grouped by category -->

**Processing History tab**
![History tab](docs/screenshots/ui_history.png)
<!-- Screenshot: filterable table of recently processed documents -->

**System Status tab**
![Status tab](docs/screenshots/ui_status.png)
<!-- Screenshot: Tesseract check, folder status, disk usage metrics -->

---

### Quick Start (Docker — recommended)

The easiest way to run the pipeline. No Python or Tesseract installation needed.

**Prerequisites:** [Docker Desktop](https://www.docker.com/products/docker-desktop/)

**Windows — first-time installation (auto-detects Docker):**

```
install.bat
```

**Windows — daily use (Docker already installed):**

```
start.bat
```

**All platforms:**

```bash
git clone https://github.com/MeghanBao/Documentation-AI-Pipeline.git
cd Documentation-AI-Pipeline

docker compose up --build -d
# open http://localhost:8501
```

On first run Docker builds the image (≈ 2–5 min). Subsequent starts take a few seconds.
Pipeline data is stored in `./data/_pipeline/` on the host.

### Web UI

The Streamlit interface is available at **http://localhost:8501** after starting with Docker.

| Tab | Function |
|---|---|
| 📤 Hochladen & Verarbeiten | Drag-and-drop upload; structured result card per file; batch summary table |
| 📁 Archiv | Browse archived documents by category; refresh button |
| 🕐 Verlauf | Filterable history of all processed documents (persisted to disk) |
| 🔍 Intelligente Suche | Natural-language search over the archive via local RAG (opt-in) |
| 🖥️ Systemstatus | Tesseract version, folder existence, disk usage with low-space alerts |
| ⚙️ Einstellungen | Full configuration dump (JSON); environment variable reference |

To run the UI without Docker:

```bash
pip install -e .
streamlit run src/doc_pipeline/ui.py
```

### Installation (manual / without Docker)

**Prerequisites**

- Python ≥ 3.10
- [Tesseract OCR](https://github.com/tesseract-ocr/tesseract) with the German language pack (`deu`)

```bash
# Ubuntu / Debian
sudo apt install tesseract-ocr tesseract-ocr-deu

# macOS
brew install tesseract tesseract-lang

# Windows — download installer from:
# https://github.com/UB-Mannheim/tesseract/wiki
# then add Tesseract to PATH and install deu.traineddata
```

**Install the package**

```bash
git clone https://github.com/MeghanBao/Documentation-AI-Pipeline.git
cd Documentation-AI-Pipeline

pip install -e .
```

### Usage (CLI)

```bash
# Continuous watch mode (default)
doc-pipeline --base-dir N:/_pipeline

# Process a single file and exit
doc-pipeline --process /path/to/scan.pdf --base-dir N:/_pipeline

# Verbose / debug output
doc-pipeline --base-dir N:/_pipeline --log-level DEBUG

# Run as a Python module
python -m doc_pipeline --base-dir N:/_pipeline
```

### Hardware (Reference Setup)

| Component | Spec |
|---|---|
| Workbot | Dell Precision T3610 |
| RAM | 32 GB |
| CPU | Intel Xeon |
| Storage | SSD |
| OCR speed | ~0.3–0.8 s / page |
| 100-page PDF | ~40–60 s total |

### Roadmap

- [x] **Core pipeline** — OCR → classify → date → archive
- [x] **Streamlit Web UI** — upload, archive browser, history, system status
- [x] **RAG system** — sentence-transformers + ChromaDB, fully offline
- [x] **Docker Compose** — one-click install & start on Windows
- [x] **PaddleOCR** — higher accuracy for complex layouts
- [ ] **Automatic tags** — tag documents beyond the primary type
- [ ] **LLM-powered classification** — replace keyword rules with a local model

```
Document
   │
   ▼
  OCR  ──────────────────────── Archive
   │                               │
   ▼                               ▼
Classifier                    Embeddings (sentence-transformers)
   │                               │
   ▼                               ▼
Date extractor             Vector DB (ChromaDB)
   │                               │
   ▼                               ▼
Archiver             "Which insurance policies do I have?"
                     "When was my internet contract signed?"
```

---

## Deutsch

### Überblick

Eine vollständig lokale, datenschutzfreundliche Dokumenten-Pipeline für Heimnetzwerke.
Das System überwacht NAS-Eingabeordner, extrahiert Text per OCR, klassifiziert Dokumente nach Typ, erkennt das Dokumentdatum mit einem 4-stufigen Score-System, generiert einheitliche Dateinamen und verschiebt jede Datei in den richtigen Archivordner — ohne Cloud-Abhängigkeit.

```
Scanner / Dateiablage
        │
        ▼
  NAS Eingabeordner
        │
        ▼
   Workbot (OCR)
   ┌────┴─────────────────────────────────┐
   │  1. Textextraktion (PyMuPDF)         │
   │  2. OCR-Fallback (Tesseract)         │
   │  3. Dokumenttyp-Klassifizierung      │
   │  4. Datumserkennung & Bewertung      │
   │  5. Dateiname generieren             │
   └────┬──────────┬───────────────────────┘
        │          │
        ▼          ▼
   archiv/      review/   input_error/
```

### Architektur

```
src/doc_pipeline/
├── config.py          PipelineConfig — Ordnerpfade, OCR-Schwellwerte
├── ocr.py             PyMuPDF nativer Text + seitenweiser Tesseract-Fallback
├── classifier.py      Schlüsselwort-Klassifizierung: Dokumenttyp + Thema
├── date_extractor.py  4-stufige Datumserkennung mit Score-System
├── archiver.py        Dateiname-Generator + Datei-Routing
├── pipeline.py        Orchestrierung eines einzelnen Dokuments
├── watcher.py         watchdog-Observer (input_scanner/ + input_manual/)
└── main.py            CLI-Einstiegspunkt
```

### Modulbeschreibung

| Modul | Aufgabe |
|---|---|
| `config.py` | Zentraler `PipelineConfig`-Dataclass. `base_dir` auf NAS-Pfad setzen; alle Unterordner werden automatisch abgeleitet. `ensure_dirs()` legt die vollständige Ordnerstruktur an. |
| `ocr.py` | Öffnet PDFs mit PyMuPDF. Seiten mit weniger als `ocr_min_chars_per_page` Zeichen (Standard: 50) werden mit 2-facher Auflösung gerendert und an Tesseract übergeben. Bilddateien (PNG/JPG/TIFF) gehen direkt an Tesseract. |
| `classifier.py` | Durchsucht den Volltext (Kleinbuchstaben) nach `_TYPE_RULES` (geordnet, spezifischste zuerst). Gibt `doc_type`, `archive_subdir`, `thema` und ein `confident`-Flag zurück. `confident=False` → Dokument wird nach `review/` verschoben. |
| `date_extractor.py` | 4-stufige Bewertung (siehe unten). Gibt das `DateResult` mit dem höchsten Score zurück oder `None`. |
| `archiver.py` | Baut den endgültigen Dateinamen und verschiebt die Datei. Bei Namenskonflikten wird ein Zähler angehängt. |
| `pipeline.py` | Verschiebt Datei nach `processing/`, ruft alle Module nacheinander auf, behandelt Fehler je Schritt. |
| `watcher.py` | watchdog-basierter Observer. Prüft Dateigröße auf Stabilität, bevor `process_document()` ausgelöst wird. |
| `main.py` | CLI mit `--process FILE` (Einzeldatei-Modus) und Standard-Watch-Modus. |
| `ui.py` | Streamlit-Web-Oberfläche: Drag-and-Drop-Upload, Archiv-Browser, Einstellungen. |

### Datumserkennung — 4-stufiges Score-System

| Stufe | Methode | Beispielfeld | Score |
|---|---|---|---|
| 1 | Explizite benannte Datumsfelder | `Rechnungsdatum` | 100 |
| 1 | | `Ausstellungsdatum`, `Bescheiddatum` | 90 |
| 1 | | `Vertragsdatum` | 85 |
| 1 | | `Schreiben vom` | 80 |
| 2 | Dokumenttyp-spezifische Felder | `Abrechnungsmonat` (Lohnabrechnung) | 65 |
| 3 | Alle Datumsangaben im Volltext | jedes erkannte Datum | 40 |
| 4 | Kein Datum / Score < Schwellwert | → `review/` | — |

Unterstützte Formate: `DD.MM.YYYY` · `DD-MM-YYYY` · `YYYY-MM-DD` · `DD/MM/YYYY` · `DD. Monat YYYY`

### Dateinamenschema

```
YYYY-MM-DD_Typ_Thema.pdf          # vollständiges Datum bekannt
YYYY-MM_Typ_Thema.pdf             # nur Monat (z. B. Lohnabrechnung)
UNSICHER_Typ_Originaldatei.pdf    # unsicher → review/
```

**Beispiele**

```
2025-02-18_Rechnung_Strom.pdf
2024-11-03_Versicherung_Haftpflicht.pdf
2025-01_Lohnabrechnung_Firma.pdf
UNSICHER_Dokument_scan_001.pdf
```

### Ordnerstruktur (NAS)

```
N:\_pipeline\
├── input_scanner\      ← automatische Scans vom Netzwerkscanner
├── input_manual\       ← manuell abgelegte Dateien
├── processing\         ← temporäres Arbeitsverzeichnis
├── review\             ← unsicherer Typ oder kein Datum → manuelle Prüfung
├── input_error\        ← OCR-Fehler / beschädigte Datei
└── archiv\
    ├── Rechnungen\
    ├── Versicherung\
    ├── Steuer\
    ├── Arbeit\
    ├── Verträge\
    └── Sonstiges\
```

### Screenshots

> 📸 *Screenshots werden nach dem ersten Deployment eingefügt — Platzhalter siehe unten.*

<!-- TODO: echte Screenshots nach dem ersten Start hinzufügen -->

**Tab: Hochladen & Verarbeiten**
![Upload-Tab](docs/screenshots/ui_upload.png)

**Tab: Archiv-Browser**
![Archiv-Tab](docs/screenshots/ui_archive.png)

**Tab: Verarbeitungsverlauf**
![Verlauf-Tab](docs/screenshots/ui_history.png)

**Tab: Systemstatus**
![Status-Tab](docs/screenshots/ui_status.png)

---

### Schnellstart (Docker — empfohlen)

Die einfachste Variante. Kein Python, keine Tesseract-Installation notwendig.

**Voraussetzung:** [Docker Desktop](https://www.docker.com/products/docker-desktop/)

**Windows — Ersteinrichtung (prüft Docker automatisch):**

```
install.bat
```

**Windows — täglicher Betrieb (Docker bereits installiert):**

```
start.bat
```

**Alle Plattformen:**

```bash
git clone https://github.com/MeghanBao/Documentation-AI-Pipeline.git
cd Documentation-AI-Pipeline

docker compose up --build -d
# Browser öffnen: http://localhost:8501
```

Beim ersten Start wird das Image gebaut (≈ 2–5 Min.). Danach startet die Pipeline in Sekunden.
Die Dokumentendaten liegen in `./data/_pipeline/` auf dem Host-Rechner.

### Web-Oberfläche

Die Streamlit-Oberfläche ist nach dem Docker-Start erreichbar unter **http://localhost:8501**.

| Tab | Funktion |
|---|---|
| 📤 Hochladen & Verarbeiten | Drag-and-Drop-Upload; strukturierte Ergebniskarte pro Datei; Sammelübersicht |
| 📁 Archiv | Archivierte Dokumente nach Kategorie; Aktualisieren-Schaltfläche |
| 🕐 Verlauf | Filterbare Verarbeitungshistorie aller Dokumente (dauerhaft gespeichert) |
| 🔍 Intelligente Suche | Natürlichsprachliche Suche im Archiv per lokalem RAG (opt-in) |
| 🖥️ Systemstatus | Tesseract-Version, Ordnercheck, Speicherplatz-Anzeige |
| ⚙️ Einstellungen | Vollständige Konfigurationsübersicht (JSON); Umgebungsvariablen |

Ohne Docker:

```bash
pip install -e .
streamlit run src/doc_pipeline/ui.py
```

> **Ausführliche Bedienungsanleitung für Nicht-Techniker:** siehe [`USAGE.md`](USAGE.md)

### Installation (manuell / ohne Docker)

**Voraussetzungen**

- Python ≥ 3.10
- [Tesseract OCR](https://github.com/tesseract-ocr/tesseract) mit deutschem Sprachpaket (`deu`)

```bash
# Ubuntu / Debian
sudo apt install tesseract-ocr tesseract-ocr-deu

# macOS
brew install tesseract tesseract-lang

# Windows — Installer herunterladen:
# https://github.com/UB-Mannheim/tesseract/wiki
# Tesseract zum PATH hinzufügen und deu.traineddata installieren
```

**Paket installieren**

```bash
git clone https://github.com/MeghanBao/Documentation-AI-Pipeline.git
cd Documentation-AI-Pipeline

pip install -e .
```

### Verwendung (CLI)

```bash
# Kontinuierlicher Watch-Modus (Standard)
doc-pipeline --base-dir N:/_pipeline

# Einzelne Datei verarbeiten und beenden
doc-pipeline --process /pfad/zur/datei.pdf --base-dir N:/_pipeline

# Ausführliche Ausgabe / Debug
doc-pipeline --base-dir N:/_pipeline --log-level DEBUG

# Als Python-Modul ausführen
python -m doc_pipeline --base-dir N:/_pipeline
```

### Hardware (Referenz-Setup)

| Komponente | Spezifikation |
|---|---|
| Workbot | Dell Precision T3610 |
| RAM | 32 GB |
| CPU | Intel Xeon |
| Speicher | SSD |
| OCR-Geschwindigkeit | ~0,3–0,8 s / Seite |
| 100-seitiges PDF | ~40–60 s gesamt |

### Geplante Erweiterungen

- [x] **Kern-Pipeline** — OCR → Klassifizierung → Datum → Archiv
- [x] **Streamlit-Web-UI** — Upload, Archiv, Verlauf, Systemstatus
- [x] **RAG-System** — sentence-transformers + ChromaDB, vollständig offline
- [x] **Docker Compose** — Ein-Klick-Installation und -Start unter Windows
- [ ] **PaddleOCR** — höhere Erkennungsgenauigkeit bei komplexen Layouts
- [ ] **Automatische Tags** — Dokumenten über den Primärtyp hinaus verschlagworten
- [ ] **LLM-gestützte Klassifizierung** — Keyword-Regeln durch lokales Modell ersetzen

```
Dokument
   │
   ▼
  OCR  ──────────────────────── Archiv
   │                               │
   ▼                               ▼
Klassifizierung          Embeddings (sentence-transformers)
   │                               │
   ▼                               ▼
Datumserkennung             Vektor-DB (ChromaDB)
   │                               │
   ▼                               ▼
Archivierung          "Welche Versicherungen habe ich?"
                      "Wann wurde mein Vertrag abgeschlossen?"
```
