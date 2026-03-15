"""Watchdog-based file system monitor for input_scanner and input_manual."""
import logging
import time
from pathlib import Path

from watchdog.events import FileCreatedEvent, FileSystemEventHandler
from watchdog.observers import Observer

from .config import PipelineConfig
from .pipeline import process_document

logger = logging.getLogger(__name__)

_SUPPORTED_EXTENSIONS = {".pdf", ".png", ".jpg", ".jpeg", ".tif", ".tiff"}

# Retry settings for locked files (scanner apps often keep files open briefly)
_LOCK_RETRIES = 15
_LOCK_DELAY = 2.0  # seconds between retries


class _DocumentHandler(FileSystemEventHandler):
    def __init__(self, config: PipelineConfig) -> None:
        self._config = config

    def on_created(self, event: FileCreatedEvent) -> None:  # type: ignore[override]
        if event.is_directory:
            return
        path = Path(event.src_path)
        if path.suffix.lower() not in _SUPPORTED_EXTENSIONS:
            return
        logger.info("New file detected: %s", path.name)
        _wait_for_stable_size(path)
        if not _wait_until_unlocked(path):
            logger.error(
                "File still locked after %d retries — skipping: %s",
                _LOCK_RETRIES,
                path.name,
            )
            return
        process_document(path, self._config)


def start_watcher(config: PipelineConfig) -> None:
    """
    Watch input_scanner/ and input_manual/ and process new files automatically.
    Blocks until a KeyboardInterrupt (Ctrl-C).
    """
    config.ensure_dirs()

    handler = _DocumentHandler(config)
    observer = Observer()

    for watch_dir in (config.input_scanner, config.input_manual):
        observer.schedule(handler, str(watch_dir), recursive=False)
        logger.info("Watching: %s", watch_dir)

    observer.start()
    logger.info("Pipeline watcher started. Press Ctrl-C to stop.")
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        logger.info("Stopping watcher…")
    finally:
        observer.stop()
        observer.join()


def _wait_for_stable_size(
    path: Path,
    poll_interval: float = 0.5,
    max_polls: int = 20,
) -> None:
    """Poll until the file size stops changing (i.e. the write is complete)."""
    prev_size = -1
    for _ in range(max_polls):
        try:
            size = path.stat().st_size
        except FileNotFoundError:
            return
        if size == prev_size:
            return
        prev_size = size
        time.sleep(poll_interval)


def _wait_until_unlocked(
    path: Path,
    retries: int = _LOCK_RETRIES,
    delay: float = _LOCK_DELAY,
) -> bool:
    """Return True once the file can be opened exclusively (not held by another process).

    On Windows, scanner apps often keep files open after writing completes.
    Opening with 'r+b' mode requires an exclusive handle and reliably detects this.
    """
    for attempt in range(retries):
        try:
            with path.open("r+b"):
                return True
        except PermissionError:
            logger.debug(
                "File locked, waiting (%d/%d): %s", attempt + 1, retries, path.name
            )
            time.sleep(delay)
        except FileNotFoundError:
            return False
    return False
