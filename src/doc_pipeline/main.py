"""CLI entry point: python -m doc_pipeline  or  doc-pipeline (installed script)."""
import argparse
import logging
from pathlib import Path

from .config import PipelineConfig
from .pipeline import process_document
from .watcher import start_watcher


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
    else:
        start_watcher(config)


if __name__ == "__main__":
    main()
