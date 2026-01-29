# ABOUTME: CLI entry point for the file organizer tool using argparse.
# ABOUTME: Provides commands for organizing photos, documents, downloads, custom categories, and undo.

import argparse
import logging
import sys
from pathlib import Path

from file_organizer.file_organizer import FileOrganizer
from file_organizer.utils.config import Config, load_config

logger = logging.getLogger("file_organizer")


def build_parser() -> argparse.ArgumentParser:
    """Build the argparse parser with all subcommands."""
    # Common arguments shared across all subcommands
    common_parser = argparse.ArgumentParser(add_help=False)
    common_parser.add_argument(
        "--verbose", "-v",
        action="store_true",
        help="Enable verbose logging output.",
    )
    common_parser.add_argument(
        "--config", "-c",
        type=str,
        default=None,
        help="Path to config file (default: ~/.file_organizer.yml).",
    )
    common_parser.add_argument(
        "--log-file",
        type=str,
        default=None,
        help="Path to log file for persistent logging output.",
    )

    parser = argparse.ArgumentParser(
        prog="file-organizer",
        description="Organize files into structured directories by type.",
        parents=[common_parser],
    )

    subparsers = parser.add_subparsers(dest="command", help="Available commands")

    # Shared arguments for organize commands
    def add_organize_args(sub):
        sub.add_argument("source", help="Source directory to organize.")
        sub.add_argument(
            "--target", "-t",
            type=str,
            default=None,
            help="Target base directory for organized files.",
        )
        sub.add_argument(
            "--dry-run",
            action="store_true",
            help="Show what would be done without moving files.",
        )

    # photos
    photos_parser = subparsers.add_parser(
        "photos", help="Organize photo files.", parents=[common_parser],
    )
    add_organize_args(photos_parser)

    # documents
    docs_parser = subparsers.add_parser(
        "documents", help="Organize document files.", parents=[common_parser],
    )
    add_organize_args(docs_parser)

    # downloads
    dl_parser = subparsers.add_parser(
        "downloads", help="Organize download files.", parents=[common_parser],
    )
    add_organize_args(dl_parser)

    # custom
    custom_parser = subparsers.add_parser(
        "custom", help="Organize files using a custom category from config.",
        parents=[common_parser],
    )
    add_organize_args(custom_parser)
    custom_parser.add_argument(
        "--category",
        required=True,
        help="Name of the custom category to use from config.",
    )

    # undo
    undo_parser = subparsers.add_parser(
        "undo", help="Undo a previous organize operation.", parents=[common_parser],
    )
    undo_parser.add_argument(
        "manifest",
        help="Path to the backup manifest JSON file.",
    )

    return parser


def main() -> int:
    """Main CLI entry point. Returns exit code."""
    parser = build_parser()
    args = parser.parse_args()

    # Set up logging
    level = logging.DEBUG if getattr(args, "verbose", False) else logging.INFO
    logging.basicConfig(
        level=level,
        format="%(levelname)s: %(message)s",
    )

    # Add file logging if requested
    log_file = getattr(args, "log_file", None)
    if log_file:
        file_handler = logging.FileHandler(log_file)
        file_handler.setLevel(level)
        file_handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s: %(message)s"))
        logging.getLogger().addHandler(file_handler)

    if not args.command:
        parser.print_help()
        return 1

    # Load config
    config_path = Path(args.config) if args.config else Path.home() / ".file_organizer.yml"
    config = load_config(config_path)

    # Handle undo
    if args.command == "undo":
        manifest_path = Path(args.manifest)
        if not manifest_path.exists():
            logger.error("Manifest file not found: %s", manifest_path)
            return 1
        organizer = FileOrganizer(config=config, base_target=manifest_path.parent)
        results = organizer.undo(manifest_path)
        logger.info(
            "Undo complete: %d restored, %d failed",
            results["restored"],
            results["failed"],
        )
        return 0 if results["failed"] == 0 else 1

    # Handle organize commands
    source_dir = Path(args.source)
    if not source_dir.is_dir():
        logger.error("Source directory not found: %s", source_dir)
        return 1

    # Determine target directory
    if args.target:
        base_target = Path(args.target)
    else:
        base_target = source_dir / "organized"

    # Determine categories
    category_map = {
        "photos": ["photos"],
        "documents": ["documents"],
        "downloads": ["downloads"],
        "custom": [args.category] if hasattr(args, "category") and args.category else None,
    }
    categories = category_map.get(args.command)

    organizer = FileOrganizer(config=config, base_target=base_target)
    results = organizer.organize(source_dir, dry_run=args.dry_run, categories=categories)

    if args.dry_run:
        logger.info("Dry run complete: %d files would be moved", results["total_would_move"])
    else:
        logger.info("Organization complete: %d files moved", results["total_moved"])

    return 0


if __name__ == "__main__":
    sys.exit(main())
