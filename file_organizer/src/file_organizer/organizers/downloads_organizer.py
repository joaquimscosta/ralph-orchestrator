# ABOUTME: Downloads file organizer that groups files by type into subfolders.
# ABOUTME: Categorizes downloads into installers, archives, and disk_images.

import logging
import shutil
from pathlib import Path

from file_organizer.utils.config import Config

logger = logging.getLogger(__name__)

# Mapping of file extensions to download type subfolders
DOWNLOAD_TYPE_MAP = {
    # Installers
    ".dmg": "installers",
    ".exe": "installers",
    ".msi": "installers",
    ".pkg": "installers",
    ".deb": "installers",
    ".rpm": "installers",
    ".appimage": "installers",
    # Archives
    ".zip": "archives",
    ".tar": "archives",
    ".gz": "archives",
    ".bz2": "archives",
    ".xz": "archives",
    ".7z": "archives",
    ".rar": "archives",
    # Disk images
    ".iso": "disk_images",
    ".img": "disk_images",
}


class DownloadsOrganizer:
    """Organizes download files into type-based subfolders (installers/, archives/, disk_images/)."""

    def __init__(self, config: Config):
        self.config = config
        self._extensions = set()
        cat_data = config.categories.get("downloads", {})
        for ext in cat_data.get("extensions", []):
            self._extensions.add(ext.lower())

    def is_download(self, path: Path) -> bool:
        """Check if a file is a recognized download type."""
        return path.suffix.lower() in self._extensions

    def scan(self, source_dir: Path) -> list[Path]:
        """Scan a directory and return all download files."""
        if not source_dir.is_dir():
            return []
        return [f for f in source_dir.iterdir() if f.is_file() and self.is_download(f)]

    def _get_type_subfolder(self, download: Path) -> str:
        """Return the type-based subfolder name for a download file."""
        return DOWNLOAD_TYPE_MAP.get(download.suffix.lower(), "other")

    def organize(
        self, source_dir: Path, target_dir: Path, dry_run: bool = False
    ) -> dict:
        """Move download files from source to type-based subfolders of target.

        Returns a dict with move statistics.
        """
        downloads = self.scan(source_dir)
        moved = 0
        would_move = 0
        duplicates = 0

        entries = []

        for dl in downloads:
            subfolder = self._get_type_subfolder(dl)
            dest_dir = target_dir / subfolder
            dest = dest_dir / dl.name

            if dry_run:
                would_move += 1
                logger.info("[DRY RUN] Would move: %s -> %s", dl, dest)
                continue

            dest_dir.mkdir(parents=True, exist_ok=True)

            if dest.exists():
                duplicates += 1
                stem = dl.stem
                suffix = dl.suffix
                counter = 1
                while dest.exists():
                    dest = dest_dir / f"{stem}_{counter}{suffix}"
                    counter += 1

            shutil.move(str(dl), str(dest))
            entries.append({"source": dl, "destination": dest})
            moved += 1
            logger.info("Moved: %s -> %s", dl, dest)

        return {
            "moved": moved,
            "would_move": would_move,
            "duplicates": duplicates,
            "entries": entries,
        }
