# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Automated document processing pipeline running **fully locally** on a home network. Watches NAS input folders, performs OCR on scanned documents, classifies by type, extracts dates, generates standardized filenames, and archives them. The German-language spec is at `docs/dokumenten_pipeline_konzept.txt`.

## Commands

```bash
# Install (editable)
pip install -e .

# Watch input folders (continuous mode)
doc-pipeline --base-dir N:/_pipeline

# Process a single file and exit
doc-pipeline --process /path/to/scan.pdf --base-dir N:/_pipeline

# Verbose debug output
doc-pipeline --log-level DEBUG
```

## Tech Stack

- **Language:** Python ≥ 3.10
- **OCR:** PyMuPDF (native PDF text) + Tesseract (fallback for scanned pages)
- **File watching:** watchdog
- **Future:** PaddleOCR, embeddings, vector DB, RAG

## Module Layout

```
src/doc_pipeline/
├── config.py          PipelineConfig dataclass — all folder paths + thresholds
├── ocr.py             Text extraction: PyMuPDF native → Tesseract fallback per page
├── classifier.py      Keyword-based type detection + thema extraction
├── date_extractor.py  4-stage scoring date extraction
├── archiver.py        Filename generation + file move
├── pipeline.py        Orchestrator: wires all modules for one document
├── watcher.py         watchdog observer for input_scanner/ and input_manual/
└── main.py            CLI entry point (argparse)
```

### Processing flow per document

```
input_scanner/ or input_manual/  →  processing/  →  archiv/{subdir}/
                                                ↘  review/       (uncertain type or date)
                                                ↘  input_error/  (OCR failure / corrupt file)
```

1. Move file to `processing/` to prevent double-processing
2. `ocr.py` — PyMuPDF extracts native text; pages below `ocr_min_chars_per_page` (default 50) are re-OCR'd with Tesseract at 2× resolution
3. `classifier.py` — keyword scan sets `doc_type`, `archive_subdir`, `thema`, and `confident`
4. `date_extractor.py` — 4-stage scoring returns best `DateResult` or `None`
5. `archiver.py` — builds filename, moves to destination

## Filename Schema

```
YYYY-MM-DD_TYP_THEMA.pdf        # full date known
YYYY-MM_TYP_THEMA.pdf           # only month known
UNSICHER_TYP_originalname.pdf   # classification uncertain → goes to review/
```

Document types map to archive subdirectories: `Rechnungen`, `Versicherung`, `Steuer`, `Arbeit`, `Verträge`, `Sonstiges`.

## Date Extraction Logic (4-stage scoring)

1. **Stage 1:** Explicit date fields (`Rechnungsdatum`, `Ausstellungsdatum`, `Bescheiddatum`, etc.)
2. **Stage 2:** Document-type-specific fields (e.g. `Abrechnungsmonat` for payslips)
3. **Stage 3:** All dates in document — highest-scoring wins (100pts: Rechnungsdatum, 90pts: Ausstellungsdatum, 70pts: letterhead date, 30pts: due date, 10pts: birthdate)
4. **Stage 4:** No plausible date found → move to `review/`

Supported date formats: `DD.MM.YYYY`, `DD-MM-YYYY`, `YYYY-MM-DD`, `DD/MM/YYYY`, `DD Month YYYY`

## NAS Folder Structure

```
N:\_pipeline/
├── input_scanner/   # auto-scans from scanner
├── input_manual/    # manually dropped files
├── processing/      # temp working directory
├── review/          # uncertain date or type
├── input_error/     # unreadable / OCR failed
└── archiv/
    ├── Rechnungen
    ├── Versicherung
    ├── Steuer
    ├── Arbeit
    ├── Verträge
    └── Sonstiges
```
