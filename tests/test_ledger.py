"""Tests for the append-only provenance ledger (why / undo)."""
from pathlib import Path

from doc_pipeline import ledger
from doc_pipeline.classifier import Classification
from doc_pipeline.date_extractor import DateResult


def _archive_file(config, subdir: str, name: str) -> Path:
    dest = config.archive / subdir / name
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_bytes(b"%PDF dummy")
    return dest


def _record(config, dest: Path, *, confident=True, score=65, date_str="2025-02", reason=""):
    cls = Classification(doc_type="Lohnabrechnung", archive_subdir="Arbeit",
                         thema="Gehalt", confident=confident, matched_keyword="bruttogehalt")
    dr = DateResult(date_str=date_str, score=score, month_only=True) if date_str else None
    return ledger.record_archive(
        config, original_name="scan_001.pdf", original_src=config.input_manual / "scan_001.pdf",
        processing_path=config.processing / "scan_001_ab12.pdf", dest=dest,
        classification=cls, date_result=dr, review_reason=reason,
    )


class TestRecord:
    def test_record_appends_one_event(self, tmp_config):
        dest = _archive_file(tmp_config, "Arbeit", "2025-02_Lohnabrechnung_Gehalt.pdf")
        eid = _record(tmp_config, dest)
        events = ledger.load_events(tmp_config.base_dir)
        assert len(events) == 1
        assert events[0]["type"] == "archive"
        assert events[0]["id"] == eid
        assert events[0]["doc_type"] == "Lohnabrechnung"
        assert events[0]["date_score"] == 65

    def test_journal_is_jsonl_under_base_dir(self, tmp_config):
        dest = _archive_file(tmp_config, "Arbeit", "a.pdf")
        _record(tmp_config, dest)
        assert ledger.journal_path(tmp_config.base_dir).exists()


class TestWhy:
    def test_explain_shows_decision_chain(self, tmp_config):
        dest = _archive_file(tmp_config, "Arbeit", "2025-02_Lohnabrechnung_Gehalt.pdf")
        _record(tmp_config, dest)
        out = ledger.explain(tmp_config, str(dest))
        assert out is not None
        assert "Lohnabrechnung" in out
        assert "Stage 2" in out          # score 65 → Stage 2
        assert "Abrechnungsmonat" in out  # score 65 → this labeled field
        assert "score 65" in out

    def test_explain_by_basename(self, tmp_config):
        dest = _archive_file(tmp_config, "Arbeit", "x.pdf")
        _record(tmp_config, dest)
        assert ledger.explain(tmp_config, "x.pdf") is not None

    def test_explain_unknown_file_returns_none(self, tmp_config):
        assert ledger.explain(tmp_config, "ghost.pdf") is None


class TestUndo:
    def test_undo_moves_file_back_and_restores_name(self, tmp_config):
        dest = _archive_file(tmp_config, "Arbeit", "2025-02_Lohnabrechnung_Gehalt.pdf")
        _record(tmp_config, dest)
        result = ledger.undo(tmp_config)
        assert result is not None and result["moved"]
        assert not dest.exists()
        restored = tmp_config.base_dir / "undone" / "scan_001.pdf"
        assert restored.exists()

    def test_undo_removes_review_sidecar(self, tmp_config):
        dest = _archive_file(tmp_config, "review", "UNSICHER_Rechnung_scan.pdf")
        dest.with_suffix(".reason.txt").write_text("Grund: kein Datum", encoding="utf-8")
        _record(tmp_config, dest, confident=False, score=40, date_str=None, reason="kein Datum")
        ledger.undo(tmp_config)
        assert not dest.with_suffix(".reason.txt").exists()

    def test_undo_is_append_only_not_a_deletion(self, tmp_config):
        dest = _archive_file(tmp_config, "Arbeit", "a.pdf")
        _record(tmp_config, dest)
        ledger.undo(tmp_config)
        events = ledger.load_events(tmp_config.base_dir)
        # archive event still present; an undo event was appended referencing it
        types = [e["type"] for e in events]
        assert types == ["archive", "undo"]
        assert events[1]["ref"] == events[0]["id"]

    def test_undone_archive_drops_out_of_active_set(self, tmp_config):
        dest = _archive_file(tmp_config, "Arbeit", "a.pdf")
        _record(tmp_config, dest)
        ledger.undo(tmp_config)
        assert ledger.active_archives(ledger.load_events(tmp_config.base_dir)) == []

    def test_undo_marks_explain_as_undone(self, tmp_config):
        dest = _archive_file(tmp_config, "Arbeit", "a.pdf")
        _record(tmp_config, dest)
        ledger.undo(tmp_config)
        assert "UNDONE" in ledger.explain(tmp_config, "a.pdf")

    def test_nothing_to_undo_returns_none(self, tmp_config):
        assert ledger.undo(tmp_config) is None

    def test_undo_targets_specific_file(self, tmp_config):
        a = _archive_file(tmp_config, "Arbeit", "a.pdf")
        b = _archive_file(tmp_config, "Arbeit", "b.pdf")
        _record(tmp_config, a)
        _record(tmp_config, b)
        ledger.undo(tmp_config, "a.pdf")
        assert not a.exists() and b.exists()  # only the targeted one moved


class TestHistory:
    def test_history_newest_first(self, tmp_config):
        d1 = _archive_file(tmp_config, "Arbeit", "a.pdf")
        d2 = _archive_file(tmp_config, "Arbeit", "b.pdf")
        _record(tmp_config, d1)
        _record(tmp_config, d2)
        rows = ledger.history(tmp_config)
        assert Path(rows[0]["dest"]).name == "b.pdf"
