# ABOUTME: Document file organizer that sorts documents into extension-based subfolders.
# ABOUTME: Groups documents by type (pdf/, docx/, txt/) within the target directory.

import logging
import shutil
from pathlib import Path

from file_organizer.utils.config import Config

logger = logging.getLogger(__name__)


class DocumentOrganizer:
    """Organizes document files into extension-based subfolders (pdf/, docx/, txt/)."""

    def __init__(self, config: Config):
        self.config = config
        self._extensions = set()
        cat_data = config.categories.get("documents", {})
        for ext in cat_data.get("extensions", []):
            self._extensions.add(ext.lower())

    def is_document(self, path: Path) -> bool:
        """Check if a file is a recognized document type."""
        return path.suffix.lower() in self._extensions

    def scan(self, source_dir: Path) -> list[Path]:
        """Scan a directory and return all document files."""
        if not source_dir.is_dir():
            return []
        return [f for f in source_dir.iterdir() if f.is_file() and self.is_document(f)]

    def _get_extension_subfolder(self, doc: Path) -> str:
        """Return the extension-based subfolder name (without the leading dot)."""
        return doc.suffix.lstrip(".").lower()

    def organize(
        self, source_dir: Path, target_dir: Path, dry_run: bool = False
    ) -> dict:
        """Move document files from source to extension-based subfolders of target.

        Returns a dict with move statistics.
        """
        docs = self.scan(source_dir)
        moved = 0
        would_move = 0
        duplicates = 0

        entries = []

        for doc in docs:
            subfolder = self._get_extension_subfolder(doc)
            dest_dir = target_dir / subfolder
            dest = dest_dir / doc.name

            if dry_run:
                would_move += 1
                logger.info("[DRY RUN] Would move: %s -> %s", doc, dest)
                continue

            dest_dir.mkdir(parents=True, exist_ok=True)

            if dest.exists():
                duplicates += 1
                stem = doc.stem
                suffix = doc.suffix
                counter = 1
                while dest.exists():
                    dest = dest_dir / f"{stem}_{counter}{suffix}"
                    counter += 1

            shutil.move(str(doc), str(dest))
            entries.append({"source": doc, "destination": dest})
            moved += 1
            logger.info("Moved: %s -> %s", doc, dest)

        return {
            "moved": moved,
            "would_move": would_move,
            "duplicates": duplicates,
            "entries": entries,
        }
