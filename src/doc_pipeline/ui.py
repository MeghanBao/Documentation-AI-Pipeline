"""Streamlit web interface — drag-and-drop upload, live processing, archive browser."""
import logging
import os
from pathlib import Path

import streamlit as st

from .config import PipelineConfig
from .pipeline import process_document

logger = logging.getLogger(__name__)

_SUPPORTED_TYPES = ["pdf", "png", "jpg", "jpeg", "tif", "tiff"]


def _get_config() -> PipelineConfig:
    base_dir = Path(os.environ.get("PIPELINE_BASE_DIR", str(Path.home() / "_pipeline")))
    enable_rag = os.environ.get("PIPELINE_ENABLE_RAG", "").lower() in ("1", "true", "yes")
    config = PipelineConfig(base_dir=base_dir, enable_rag=enable_rag)
    config.ensure_dirs()
    return config


@st.cache_resource
def _get_rag_engine(persist_dir: str):
    """Load (and cache) the RAGEngine.  Called only when RAG is enabled."""
    from .rag import RAGEngine  # noqa: PLC0415

    return RAGEngine.from_dir(Path(persist_dir))


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
    for f in uploaded:
        dest = config.input_manual / f.name
        dest.write_bytes(f.getvalue())

        with st.spinner(f"Verarbeite **{f.name}** …"):
            result = process_document(dest, config)

        if result is None:
            st.error(f"✗  **{f.name}** — Fehler aufgetreten (siehe `input_error/`)")
        elif config.review in result.parents:
            st.warning(
                f"⚠  **{f.name}** → `review/`\n\n"
                f"Datum oder Typ konnte nicht sicher erkannt werden.\n\n"
                f"Neuer Dateiname: `{result.name}`"
            )
        else:
            st.success(
                f"✓  **{f.name}** → `archiv/{result.parent.name}/`\n\n"
                f"Neuer Dateiname: `{result.name}`"
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

    # Review folder — always highlighted if non-empty
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

    engine = _get_rag_engine(str(config.rag_db))

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

    with st.spinner("Suche läuft …"):
        results = engine.query(question, n_results=n_results)

    if not results:
        st.info("Keine passenden Abschnitte gefunden.")
        return

    st.divider()
    for i, hit in enumerate(results, 1):
        meta = hit["metadata"]
        score = 1.0 - hit["distance"]  # cosine distance → similarity
        header = (
            f"**#{i}** — `{meta.get('filename', '?')}`"
            f"  ·  Typ: {meta.get('doc_type', '?')}"
            f"  ·  Datum: {meta.get('date', '?')}"
            f"  ·  Relevanz: {score:.0%}"
        )
        with st.expander(header):
            st.text(hit["text"])


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

    st.markdown("**Ordnerstatus**")
    rows = [
        ("input_scanner/",  config.input_scanner),
        ("input_manual/",   config.input_manual),
        ("processing/",     config.processing),
        ("review/",         config.review),
        ("input_error/",    config.input_error),
        ("archiv/",         config.archive),
    ]
    for label, path in rows:
        icon = "✅" if path.exists() else "❌"
        st.text(f"  {icon}  {label:22s}  {path}")


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

    config = _get_config()

    tab_upload, tab_archive, tab_search, tab_settings = st.tabs([
        "📤  Hochladen & Verarbeiten",
        "📁  Archiv",
        "🔍  Intelligente Suche",
        "⚙️  Einstellungen",
    ])

    with tab_upload:
        _tab_upload(config)

    with tab_archive:
        _tab_archive(config)

    with tab_search:
        _tab_search(config)

    with tab_settings:
        _tab_settings(config)


if __name__ == "__main__":
    main()
