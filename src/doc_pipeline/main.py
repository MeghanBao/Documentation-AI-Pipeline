"""CLI entry point: python -m doc_pipeline  or  doc-pipeline (installed script)."""
import argparse
import logging
from pathlib import Path

from .config import PipelineConfig
from .pipeline import process_document
from .watcher import _SUPPORTED_EXTENSIONS, start_watcher

_SUPPORTED_GLOB = ", ".join(sorted(_SUPPORTED_EXTENSIONS))


def main() -> None:
    parser = argparse.ArgumentParser(
        prog="doc-pipeline",
        description="Dokumenten-KI Pipeline – OCR, Klassifizierung, Archivierung",
    )
    parser.add_argument(
        "--base-dir",
        type=Path,
        metavar="PATH",
        help="Pipeline base directory (default: N:/_pipeline)",
    )
    parser.add_argument(
        "--process",
        type=Path,
        metavar="FILE",
        help="Process a single file and exit",
    )
    parser.add_argument(
        "--process-dir",
        type=Path,
        metavar="DIR",
        help=f"Process all supported files in a directory and exit ({_SUPPORTED_GLOB})",
    )
    parser.add_argument(
        "--log-level",
        default="INFO",
        choices=["DEBUG", "INFO", "WARNING", "ERROR"],
    )
    args = parser.parse_args()

    logging.basicConfig(
        level=getattr(logging, args.log_level),
        format="%(asctime)s  %(levelname)-8s  %(name)s  %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    config = PipelineConfig()
    if args.base_dir:
        config.base_dir = args.base_dir

    if args.process:
        config.ensure_dirs()
        process_document(args.process, config)
    elif args.process_dir:
        _process_directory(args.process_dir, config)
    else:
        start_watcher(config)


def _process_directory(directory: Path, config: PipelineConfig) -> None:
    """Process all supported files in *directory* sequentially."""
    if not directory.is_dir():
        logging.getLogger(__name__).error("Not a directory: %s", directory)
        return

    files = sorted(
        f for f in directory.iterdir()
        if f.is_file() and f.suffix.lower() in _SUPPORTED_EXTENSIONS
    )

    if not files:
        logging.getLogger(__name__).warning(
            "No supported files found in %s (supported: %s)", directory, _SUPPORTED_GLOB
        )
        return

    config.ensure_dirs()
    logger = logging.getLogger(__name__)
    logger.info("Batch processing %d file(s) from: %s", len(files), directory)

    ok = failed = 0
    for f in files:
        result = process_document(f, config)
        if result is None:
            failed += 1
        else:
            ok += 1

    logger.info("Batch done — %d succeeded, %d failed", ok, failed)


if __name__ == "__main__":
    main()
