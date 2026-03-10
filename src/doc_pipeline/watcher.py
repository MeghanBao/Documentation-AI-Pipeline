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
