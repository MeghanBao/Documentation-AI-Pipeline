"""Streamlit web interface — drag-and-drop upload, live processing, archive browser."""
import json
import logging
import os
import shutil
import subprocess
from datetime import datetime
from pathlib import Path
from typing import Optional

import streamlit as st

from .config import PipelineConfig
from .pipeline import process_document

logger = logging.getLogger(__name__)

_SUPPORTED_TYPES = ["pdf", "png", "jpg", "jpeg", "tif", "tiff"]
_HISTORY_MAX = 100  # keep last N entries in history log


# ---------------------------------------------------------------------------
# Config + helpers
# ---------------------------------------------------------------------------

def _get_config() -> PipelineConfig:
    base_dir = Path(os.environ.get("PIPELINE_BASE_DIR", str(Path.home() / "_pipeline")))
    enable_rag = os.environ.get("PIPELINE_ENABLE_RAG", "").lower() in ("1", "true", "yes")
    config = PipelineConfig(base_dir=base_dir, enable_rag=enable_rag)
    config.ensure_dirs()
    return config


@st.cache_resource
def _get_rag_engine(persist_dir: str):
    """Load (and cache) the RAGEngine. Called only when RAG is enabled."""
    from .rag import RAGEngine  # noqa: PLC0415

    return RAGEngine.from_dir(Path(persist_dir))


def _history_file(config: PipelineConfig) -> Path:
    return config.base_dir / "processing_history.json"


def _read_history(config: PipelineConfig) -> list[dict]:
    hf = _history_file(config)
    try:
        if hf.exists():
            return json.loads(hf.read_text(encoding="utf-8"))
    except Exception:
        pass
    return []


def _append_history(
    config: PipelineConfig,
    original: str,
    result: Optional[Path],
    status: str,
) -> None:
    """Append one entry to the on-disk history log (newest first, capped at _HISTORY_MAX)."""
    hf = _history_file(config)
    try:
        history = _read_history(config)
        entry = {
            "timestamp": datetime.now().isoformat(timespec="seconds"),
            "original": original,
            "result": result.name if result else None,
            "category": result.parent.name if result else None,
            "status": status,
        }
        history.insert(0, entry)
        history = history[:_HISTORY_MAX]
        hf.write_text(json.dumps(history, ensure_ascii=False, indent=2), encoding="utf-8")
    except Exception as exc:
        logger.warning("Could not write processing history: %s", exc)


# ---------------------------------------------------------------------------
# Tab: Upload & Process
# ---------------------------------------------------------------------------

def _tab_upload(config: PipelineConfig) -> None:
    st.subheader("Dokument hochladen und verarbeiten")
    st.caption("PDF, PNG, JPG oder TIFF – in das Feld ziehen oder per Klick auswählen.")

    uploaded = st.file_uploader(
        "Dateien auswählen",
        type=_SUPPORTED_TYPES,
        accept_multiple_files=True,
        label_visibility="collapsed",
    )

    if not uploaded:
        st.info("Noch keine Datei ausgewählt.")
        return

    st.write(f"**{len(uploaded)} Datei(en) ausgewählt:**")
    for f in uploaded:
        st.text(f"  • {f.name}")

    if not st.button("▶  Verarbeiten", type="primary", use_container_width=True):
        return

    st.divider()
    summary_rows: list[dict] = []

    for f in uploaded:
        try:
            dest = config.input_manual / f.name
            dest.write_bytes(f.getvalue())
        except Exception as exc:
            logger.error("Could not save uploaded file %s: %s", f.name, exc)
            st.error(
                f"❌ **{f.name}** konnte nicht gespeichert werden.\n\n"
                "Bitte stellen Sie sicher, dass ausreichend Speicherplatz verfügbar ist."
            )
            _append_history(config, f.name, None, "fehler")
            summary_rows.append({"Datei": f.name, "Status": "❌ Fehler beim Speichern",
                                  "Neuer Name": "—", "Kategorie": "—"})
            continue

        try:
            with st.spinner(f"Verarbeite **{f.name}** …"):
                result = process_document(dest, config)
        except Exception as exc:
            logger.error("Unexpected pipeline error for %s: %s", f.name, exc)
            st.error(
                f"❌ **{f.name}** — Unerwarteter Fehler bei der Verarbeitung.\n\n"
                "Die Datei wurde in `input_error/` verschoben. "
                "Bitte prüfen Sie die Datei auf Beschädigungen."
            )
            _append_history(config, f.name, None, "fehler")
            summary_rows.append({"Datei": f.name, "Status": "❌ Verarbeitungsfehler",
                                  "Neuer Name": "—", "Kategorie": "—"})
            continue

        if result is None:
            st.error(
                f"❌ **{f.name}** — Die Datei konnte nicht verarbeitet werden.\n\n"
                "Mögliche Ursachen: beschädigte Datei, OCR-Fehler oder ungültiges Format.\n"
                "Die Datei wurde in `input_error/` verschoben."
            )
            _append_history(config, f.name, None, "fehler")
            summary_rows.append({"Datei": f.name, "Status": "❌ Fehler (input_error/)",
                                  "Neuer Name": "—", "Kategorie": "—"})

        elif config.review in result.parents:
            st.warning(
                f"⚠️ **{f.name}** → `review/`\n\n"
                "Datum oder Dokumenttyp konnte nicht eindeutig erkannt werden. "
                "Bitte manuell überprüfen.\n\n"
                f"Neuer Dateiname: `{result.name}`"
            )
            _append_history(config, f.name, result, "überprüfen")
            summary_rows.append({"Datei": f.name, "Status": "⚠️ Manuelle Prüfung nötig",
                                  "Neuer Name": result.name, "Kategorie": "review/"})

        else:
            # Parse metadata from filename for the result card
            parts = result.stem.split("_", 2)
            date_str = parts[0] if parts else "—"
            doc_type = parts[1] if len(parts) > 1 else "—"
            thema = parts[2] if len(parts) > 2 else "—"

            st.success(
                f"✅ **{f.name}** erfolgreich archiviert\n\n"
                f"| Feld | Wert |\n"
                f"|---|---|\n"
                f"| Neuer Dateiname | `{result.name}` |\n"
                f"| Dokumenttyp | {doc_type} |\n"
                f"| Thema | {thema} |\n"
                f"| Datum | {date_str} |\n"
                f"| Archivordner | `archiv/{result.parent.name}/` |"
            )
            _append_history(config, f.name, result, "archiviert")
            summary_rows.append({
                "Datei": f.name,
                "Status": "✅ Archiviert",
                "Neuer Name": result.name,
                "Kategorie": result.parent.name,
            })

    # Summary table
    if len(summary_rows) > 1:
        st.divider()
        st.subheader("Zusammenfassung")
        st.dataframe(
            summary_rows,
            use_container_width=True,
            hide_index=True,
        )


# ---------------------------------------------------------------------------
# Tab: Archive
# ---------------------------------------------------------------------------

def _tab_archive(config: PipelineConfig) -> None:
    st.subheader("Archiv-Übersicht")

    cols = st.columns([5, 1])
    cols[0].caption("Alle archivierten Dokumente, nach Kategorie geordnet.")
    if cols[1].button("↻ Neu laden"):
        st.rerun()

    total = 0
    subdirs = ["Rechnungen", "Versicherung", "Steuer", "Arbeit", "Verträge", "Sonstiges"]

    for subdir in subdirs:
        folder = config.archive / subdir
        files = sorted(folder.glob("*"), reverse=True) if folder.exists() else []
        total += len(files)
        label = f"📁  {subdir}  —  {len(files)} Datei(en)"
        with st.expander(label, expanded=len(files) > 0):
            if files:
                for f in files:
                    st.text(f.name)
            else:
                st.caption("Noch keine Dateien in dieser Kategorie.")

    review_files = sorted(config.review.glob("*"), reverse=True) if config.review.exists() else []
    if review_files:
        with st.expander(
            f"⚠️  review/  —  {len(review_files)} Datei(en) warten auf manuelle Prüfung",
            expanded=True,
        ):
            st.caption(
                "Diese Dokumente konnten nicht eindeutig klassifiziert werden. "
                "Bitte manuell überprüfen und in den richtigen Archivordner verschieben."
            )
            for f in review_files:
                st.text(f.name)

    error_files = list(config.input_error.glob("*")) if config.input_error.exists() else []
    if error_files:
        with st.expander(f"🔴  input_error/  —  {len(error_files)} Datei(en) mit Fehler"):
            st.caption("OCR fehlgeschlagen oder Datei beschädigt.")
            for f in error_files:
                st.text(f.name)

    st.divider()
    st.caption(f"Gesamt im Archiv: **{total}** Dokument(e)")


# ---------------------------------------------------------------------------
# Tab: Processing History
# ---------------------------------------------------------------------------

def _tab_history(config: PipelineConfig) -> None:
    st.subheader("Verarbeitungsverlauf")

    cols = st.columns([5, 1])
    cols[0].caption("Die zuletzt verarbeiteten Dokumente (neueste zuerst).")
    if cols[1].button("↻ Neu laden", key="history_reload"):
        st.rerun()

    history = _read_history(config)

    if not history:
        st.info("Noch keine Dokumente verarbeitet. Laden Sie Dateien im Tab **Hochladen & Verarbeiten** hoch.")
        return

    # Status filter
    status_options = ["Alle", "✅ Archiviert", "⚠️ Manuelle Prüfung nötig", "❌ Fehler"]
    status_filter = st.selectbox("Filter nach Status", status_options, index=0)

    _STATUS_MAP = {
        "archiviert":      "✅ Archiviert",
        "überprüfen":      "⚠️ Manuelle Prüfung nötig",
        "fehler":          "❌ Fehler",
    }

    rows = []
    for entry in history:
        display_status = _STATUS_MAP.get(entry.get("status", ""), entry.get("status", "—"))
        if status_filter != "Alle" and display_status != status_filter:
            continue
        rows.append({
            "Zeitstempel":  entry.get("timestamp", "—"),
            "Originaldatei": entry.get("original", "—"),
            "Neuer Name":   entry.get("result") or "—",
            "Kategorie":    entry.get("category") or "—",
            "Status":       display_status,
        })

    if not rows:
        st.info("Keine Einträge für den gewählten Filter.")
        return

    st.dataframe(rows, use_container_width=True, hide_index=True)
    st.caption(f"{len(rows)} Einträge angezeigt (von {len(history)} gesamt)")


# ---------------------------------------------------------------------------
# Tab: Smart Search (RAG)
# ---------------------------------------------------------------------------

def _tab_search(config: PipelineConfig) -> None:
    st.subheader("Intelligente Suche")

    if not config.enable_rag:
        st.info(
            "Die intelligente Suche ist deaktiviert.\n\n"
            "Zum Aktivieren die Umgebungsvariable `PIPELINE_ENABLE_RAG=true` setzen "
            "und den Container neu starten."
        )
        return

    try:
        engine = _get_rag_engine(str(config.rag_db))
    except Exception as exc:
        logger.error("Could not load RAG engine: %s", exc)
        st.error(
            "❌ Die Suchmaschine konnte nicht geladen werden.\n\n"
            "Bitte stellen Sie sicher, dass alle Abhängigkeiten installiert sind "
            "(`sentence-transformers`, `chromadb`)."
        )
        return

    st.caption(
        f"Durchsuche **{engine.chunk_count}** Textabschnitte aus dem Archiv "
        "mit natürlichsprachlichen Fragen."
    )

    if engine.chunk_count == 0:
        st.warning(
            "Das Suchindex ist noch leer. "
            "Lade Dokumente über den Tab **Hochladen & Verarbeiten** hoch — "
            "sie werden automatisch indexiert."
        )
        return

    question = st.text_input(
        "Frage eingeben",
        placeholder='z. B. "Welche Stromrechnung hatte den höchsten Betrag?"',
    )

    n_results = st.slider("Anzahl Ergebnisse", min_value=1, max_value=10, value=5)

    if not question:
        return

    try:
        with st.spinner("Suche läuft …"):
            results = engine.query(question, n_results=n_results)
    except Exception as exc:
        logger.error("RAG query error: %s", exc)
        st.error("❌ Fehler bei der Suche. Bitte versuchen Sie es erneut.")
        return

    if not results:
        st.info("Keine passenden Abschnitte gefunden.")
        return

    st.divider()
    for i, hit in enumerate(results, 1):
        meta = hit["metadata"]
        score = 1.0 - hit["distance"]
        header = (
            f"**#{i}** — `{meta.get('filename', '?')}`"
            f"  ·  Typ: {meta.get('doc_type', '?')}"
            f"  ·  Datum: {meta.get('date', '?')}"
            f"  ·  Relevanz: {score:.0%}"
        )
        with st.expander(header):
            st.text(hit["text"])


# ---------------------------------------------------------------------------
# Tab: System Status
# ---------------------------------------------------------------------------

def _check_tesseract() -> tuple[bool, str]:
    """Return (ok, version_or_error_message)."""
    try:
        import pytesseract  # noqa: PLC0415
        version = pytesseract.get_tesseract_version()
        return True, str(version)
    except Exception as exc:
        return False, str(exc)


def _tab_status(config: PipelineConfig) -> None:
    st.subheader("Systemstatus")
    st.caption("Überprüfung der wichtigsten Systemkomponenten.")

    if st.button("↻ Status aktualisieren"):
        st.rerun()

    st.markdown("#### OCR-Engine")
    tess_ok, tess_msg = _check_tesseract()
    if tess_ok:
        st.success(f"✅ Tesseract verfügbar — Version {tess_msg}")
    else:
        st.error(
            f"❌ Tesseract nicht gefunden.\n\n"
            "Installation: `sudo apt-get install tesseract-ocr tesseract-ocr-deu` "
            "(Linux) oder Tesseract für Windows herunterladen.\n\n"
            f"Fehlerdetails: `{tess_msg}`"
        )

    st.markdown("#### Ordnerstruktur")
    folder_rows = [
        ("input_scanner/", config.input_scanner),
        ("input_manual/",  config.input_manual),
        ("processing/",    config.processing),
        ("review/",        config.review),
        ("input_error/",   config.input_error),
        ("archiv/",        config.archive),
    ]
    all_ok = True
    for label, path in folder_rows:
        exists = path.exists()
        all_ok = all_ok and exists
        icon = "✅" if exists else "❌"
        st.text(f"  {icon}  {label:22s}  {path}")

    if not all_ok:
        st.warning(
            "Einige Ordner fehlen. Sie werden beim nächsten Start automatisch angelegt. "
            "Sie können auch `config.ensure_dirs()` manuell aufrufen."
        )

    st.markdown("#### Speicherplatz")
    try:
        usage = shutil.disk_usage(config.base_dir if config.base_dir.exists() else Path.home())
        total_gb = usage.total / 1024 ** 3
        used_gb  = usage.used  / 1024 ** 3
        free_gb  = usage.free  / 1024 ** 3
        pct_used = usage.used / usage.total * 100

        col1, col2, col3 = st.columns(3)
        col1.metric("Gesamt", f"{total_gb:.1f} GB")
        col2.metric("Belegt", f"{used_gb:.1f} GB", f"{pct_used:.0f}%")
        col3.metric("Frei", f"{free_gb:.1f} GB")

        if free_gb < 1.0:
            st.error("⚠️ Weniger als 1 GB frei — bitte Speicherplatz freigeben!")
        elif free_gb < 5.0:
            st.warning("⚠️ Wenig freier Speicherplatz (< 5 GB).")
        else:
            st.success(f"✅ Ausreichend Speicherplatz verfügbar ({free_gb:.1f} GB frei).")
    except Exception as exc:
        st.warning(f"Speicherplatz konnte nicht ermittelt werden: {exc}")

    st.markdown("#### RAG / Intelligente Suche")
    if config.enable_rag:
        st.success("✅ Intelligente Suche aktiviert")
        st.text(f"  Datenbankpfad: {config.rag_db}")
    else:
        st.info("ℹ️ Intelligente Suche deaktiviert (`PIPELINE_ENABLE_RAG=false`)")


# ---------------------------------------------------------------------------
# Tab: Settings
# ---------------------------------------------------------------------------

def _tab_settings(config: PipelineConfig) -> None:
    st.subheader("Einstellungen")
    st.info(
        f"**Basis-Verzeichnis:** `{config.base_dir}`\n\n"
        "Zum Ändern die Umgebungsvariable `PIPELINE_BASE_DIR` setzen "
        "(in `docker-compose.yml` oder `.env`)."
    )

    st.markdown("**Konfigurationsübersicht**")
    st.json({
        "base_dir":             str(config.base_dir),
        "ocr_lang":             config.ocr_lang,
        "ocr_min_chars_per_page": config.ocr_min_chars_per_page,
        "date_min_score":       config.date_min_score,
        "enable_rag":           config.enable_rag,
        "rag_db":               str(config.rag_db),
    })


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main() -> None:
    st.set_page_config(
        page_title="Dokumenten-KI Pipeline",
        page_icon="📄",
        layout="wide",
        menu_items={"About": "Lokale Dokumenten-KI Pipeline — vollständig offline"},
    )

    st.title("📄 Dokumenten-KI Pipeline")
    st.caption("Automatische OCR · Klassifizierung · Archivierung — vollständig lokal")

    try:
        config = _get_config()
    except Exception as exc:
        logger.error("Failed to initialise pipeline config: %s", exc)
        st.error(
            "❌ **Konfigurationsfehler**\n\n"
            "Die Pipeline konnte nicht initialisiert werden. "
            "Bitte überprüfen Sie die Umgebungsvariable `PIPELINE_BASE_DIR` "
            "und stellen Sie sicher, dass das Verzeichnis erreichbar ist.\n\n"
            f"Fehlerdetails: `{exc}`"
        )
        return

    tab_upload, tab_archive, tab_history, tab_search, tab_status, tab_settings = st.tabs([
        "📤  Hochladen & Verarbeiten",
        "📁  Archiv",
        "🕐  Verlauf",
        "🔍  Intelligente Suche",
        "🖥️  Systemstatus",
        "⚙️  Einstellungen",
    ])

    with tab_upload:
        _tab_upload(config)

    with tab_archive:
        _tab_archive(config)

    with tab_history:
        _tab_history(config)

    with tab_search:
        _tab_search(config)

    with tab_status:
        _tab_status(config)

    with tab_settings:
        _tab_settings(config)


if __name__ == "__main__":
    main()
