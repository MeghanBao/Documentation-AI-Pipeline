"""
Reversible ledger for the document pipeline.

An append-only journal records *why* every document was named and routed the way
it was (classification + date-scoring decisions + the file move), so you can later
ask ``why`` a file ended up where it did, and ``undo`` a wrong archive move.

Design (borrowed from event-sourced systems): the journal is **append-only**.
An archive is "undone" not by editing its record but by appending an ``undo``
event that references it — so history is never rewritten and every action stays
auditable.

Storage: ``<base_dir>/.pipeline_journal/events.jsonl`` (one JSON object per line).

CLI::

    python -m doc_pipeline.ledger why   archiv/Arbeit/2025-02_Lohnabrechnung_Gehalt.pdf
    python -m doc_pipeline.ledger undo   [FILE]
    python -m doc_pipeline.ledger history [-n N]

The base directory comes from ``$PIPELINE_BASE_DIR`` (else the PipelineConfig default).
"""
from __future__ import annotations

import argparse
import json
import logging
import os
import shutil
import uuid
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from .config import PipelineConfig

logger = logging.getLogger(__name__)

JOURNAL_DIRNAME = ".pipeline_journal"
JOURNAL_FILENAME = "events.jsonl"

# Map a date-extractor score back to its 4-stage meaning (see date_extractor.py).
_SCORE_FIELD: dict[int, str] = {
    100: "Rechnungsdatum",
    90: "Ausstellungs-/Bescheiddatum",
    85: "Vertragsdatum",
    80: "Schreiben vom",
    70: "Datum",
    65: "Abrechnungsmonat",
    40: "generic date in text",
    30: "Fälligkeitsdatum",
    10: "Geburtsdatum",
}


def _now() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds")


def journal_path(base_dir: Path) -> Path:
    return base_dir / JOURNAL_DIRNAME / JOURNAL_FILENAME


def _append(base_dir: Path, event: dict[str, Any]) -> None:
    jp = journal_path(base_dir)
    jp.parent.mkdir(parents=True, exist_ok=True)
    with jp.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(event, ensure_ascii=False) + "\n")


def load_events(base_dir: Path) -> list[dict[str, Any]]:
    jp = journal_path(base_dir)
    if not jp.exists():
        return []
    events: list[dict[str, Any]] = []
    for line in jp.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            events.append(json.loads(line))
        except json.JSONDecodeError:
            logger.warning("Skipping malformed journal line")
    return events


# ---------------------------------------------------------------------------
# Recording (called by the pipeline; best-effort, never raises into it)
# ---------------------------------------------------------------------------

def record_archive(
    config: PipelineConfig,
    *,
    original_name: str,
    original_src: Path,
    processing_path: Path,
    dest: Path,
    classification: Any,
    date_result: Any,
    review_reason: str = "",
) -> str | None:
    """Append one ``archive`` event. Returns its id, or None on failure.

    Best-effort: journaling must never break the pipeline, so all errors are
    swallowed (mirrors the non-fatal RAG indexing step).
    """
    try:
        event = {
            "id": uuid.uuid4().hex,
            "ts": _now(),
            "type": "archive",
            "original_name": original_name,
            "original_src": str(original_src),
            "processing": str(processing_path),
            "dest": str(dest),
            "doc_type": getattr(classification, "doc_type", ""),
            "archive_subdir": getattr(classification, "archive_subdir", ""),
            "thema": getattr(classification, "thema", ""),
            "confident": bool(getattr(classification, "confident", False)),
            "matched_keyword": getattr(classification, "matched_keyword", ""),
            "date_str": getattr(date_result, "date_str", None) if date_result else None,
            "date_score": getattr(date_result, "score", None) if date_result else None,
            "month_only": bool(getattr(date_result, "month_only", False)) if date_result else False,
            "review_reason": review_reason or "",
        }
        _append(config.base_dir, event)
        return event["id"]
    except OSError as exc:
        logger.warning("Journal write failed: %s", exc)
        return None


# ---------------------------------------------------------------------------
# Queries
# ---------------------------------------------------------------------------

def _undone_ids(events: list[dict[str, Any]]) -> set[str]:
    return {e["ref"] for e in events if e.get("type") == "undo" and "ref" in e}


def active_archives(events: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Archive events that have not been undone, in chronological order."""
    undone = _undone_ids(events)
    return [e for e in events if e.get("type") == "archive" and e.get("id") not in undone]


def _match(event: dict[str, Any], target: str) -> bool:
    dest = event.get("dest", "")
    return dest == target or Path(dest).name == Path(target).name


def find_archive(
    events: list[dict[str, Any]], target: str, *, active_only: bool = False
) -> dict[str, Any] | None:
    """Latest archive event whose dest matches ``target`` (exact path or basename)."""
    pool = active_archives(events) if active_only else [e for e in events if e.get("type") == "archive"]
    matches = [e for e in pool if _match(e, target)]
    return matches[-1] if matches else None


# ---------------------------------------------------------------------------
# why
# ---------------------------------------------------------------------------

def _date_line(event: dict[str, Any]) -> str:
    score = event.get("date_score")
    date_str = event.get("date_str")
    if score is None or date_str is None:
        return "date:  none found → routed to review (Stage 4)"
    stage = 4 if score is None else 3 if score == 40 else 2 if score == 65 else 1
    field = _SCORE_FIELD.get(score, f"score {score}")
    return f"date:  {date_str} · Stage {stage} · {field} · score {score}"


def format_chain(event: dict[str, Any], *, undone: bool = False, restored_to: str = "") -> str:
    dest = Path(event.get("dest", "?"))
    confident = "confident" if event.get("confident") else "UNSURE → review"
    route = event.get("archive_subdir") or "review"
    mk = event.get("matched_keyword")
    matched = f' · matched "{mk}"' if mk else ""
    lines = [
        f"📄 backstory · {dest.name}",
        f"  archived: {event.get('dest')}   ({event.get('ts')})",
        f"  from:     {event.get('original_name')}",
        "  ── why " + "─" * 34,
        f"  type:  {event.get('doc_type')}{matched}  (thema: {event.get('thema')})  [{confident}]",
        f"  {_date_line(event)}",
        f"  route: {route}",
    ]
    if event.get("review_reason"):
        lines.append(f"  reason: {event['review_reason']}")
    if undone:
        tail = f" → restored to {restored_to}" if restored_to else ""
        lines.append(f"  ⟲ UNDONE{tail}")
    return "\n".join(lines)


def explain(config: PipelineConfig, target: str) -> str | None:
    events = load_events(config.base_dir)
    event = find_archive(events, target)
    if event is None:
        return None
    undone_ids = _undone_ids(events)
    restored = ""
    if event["id"] in undone_ids:
        for e in events:
            if e.get("type") == "undo" and e.get("ref") == event["id"]:
                restored = e.get("restored_to", "")
    return format_chain(event, undone=event["id"] in undone_ids, restored_to=restored)


# ---------------------------------------------------------------------------
# undo (reversible move)
# ---------------------------------------------------------------------------

def _unique(path: Path) -> Path:
    if not path.exists():
        return path
    stem, suffix, n = path.stem, path.suffix, 1
    while (cand := path.parent / f"{stem}_{n}{suffix}").exists():
        n += 1
    return cand


def undo(config: PipelineConfig, target: str | None = None) -> dict[str, Any] | None:
    """Reverse an archive move: put the file back under ``<base_dir>/undone/`` with
    its original name, drop the review sidecar, and append an ``undo`` event.

    With no ``target``, undoes the most recent not-yet-undone archive.
    Returns a summary dict, or None if there is nothing to undo.
    """
    events = load_events(config.base_dir)
    candidates = active_archives(events)
    if not candidates:
        return None

    event = find_archive(events, target, active_only=True) if target else candidates[-1]
    if event is None:
        return None

    dest = Path(event["dest"])
    undone_dir = config.base_dir / "undone"
    undone_dir.mkdir(parents=True, exist_ok=True)
    restore_to = _unique(undone_dir / (event.get("original_name") or dest.name))

    moved = False
    if dest.exists():
        shutil.move(str(dest), str(restore_to))
        moved = True
        sidecar = dest.with_suffix(".reason.txt")
        if sidecar.exists():
            try:
                sidecar.unlink()
            except OSError as exc:
                logger.warning("Could not remove sidecar %s: %s", sidecar.name, exc)

    _append(
        config.base_dir,
        {
            "id": uuid.uuid4().hex,
            "ts": _now(),
            "type": "undo",
            "ref": event["id"],
            "restored_to": str(restore_to) if moved else "",
            "file_present": moved,
        },
    )
    return {"archive": event, "restored_to": restore_to if moved else None, "moved": moved}


def history(config: PipelineConfig, limit: int = 20) -> list[dict[str, Any]]:
    return load_events(config.base_dir)[-limit:][::-1]


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def _load_config() -> PipelineConfig:
    base = os.environ.get("PIPELINE_BASE_DIR")
    return PipelineConfig(base_dir=Path(base)) if base else PipelineConfig()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="doc-pipeline-ledger",
        description="Provenance (why) and reversible undo for the document pipeline.",
    )
    sub = parser.add_subparsers(dest="cmd", required=True)
    p_why = sub.add_parser("why", help="explain why a file was named/routed as it was")
    p_why.add_argument("file")
    p_undo = sub.add_parser("undo", help="reverse an archive move (default: most recent)")
    p_undo.add_argument("file", nargs="?")
    p_hist = sub.add_parser("history", help="show recent journal events")
    p_hist.add_argument("-n", type=int, default=20)

    args = parser.parse_args(argv)
    config = _load_config()

    if args.cmd == "why":
        out = explain(config, args.file)
        if out is None:
            print(f"No journal record found for: {args.file}")
            return 1
        print(out)
        return 0

    if args.cmd == "undo":
        result = undo(config, args.file)
        if result is None:
            print("Nothing to undo." if not args.file else f"No active archive matches: {args.file}")
            return 1
        if result["moved"]:
            print(f"⟲ Restored {result['archive']['original_name']} → {result['restored_to']}")
        else:
            print("Marked as undone (archived file was already missing on disk).")
        return 0

    if args.cmd == "history":
        rows = history(config, args.n)
        if not rows:
            print("Journal is empty.")
            return 0
        for e in rows:
            if e.get("type") == "archive":
                print(f"{e['ts']}  ARCHIVE  {Path(e['dest']).name}")
            elif e.get("type") == "undo":
                print(f"{e['ts']}  UNDO     ref={e['ref'][:8]}")
        return 0

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
