# ABOUTME: Photo file organizer that detects and moves photo files into Year/Month subfolders.
# ABOUTME: Extracts EXIF DateTimeOriginal for date-based organization; falls back to 'unsorted'.

import logging
import shutil
import struct
from pathlib import Path

from file_organizer.utils.config import Config

logger = logging.getLogger(__name__)


def _extract_exif_date(photo_path: Path) -> tuple[str, str] | None:
    """Extract year and month from JPEG EXIF DateTimeOriginal tag.

    Returns (year, month) as zero-padded strings, or None if not found.
    """
    try:
        with open(photo_path, "rb") as f:
            # Verify JPEG SOI marker
            if f.read(2) != b"\xff\xd8":
                return None

            # Scan for APP1 (EXIF) marker
            while True:
                marker = f.read(2)
                if len(marker) < 2:
                    return None
                if marker == b"\xff\xe1":
                    break
                if marker[0:1] != b"\xff":
                    return None
                # Skip non-EXIF segments
                seg_len_data = f.read(2)
                if len(seg_len_data) < 2:
                    return None
                seg_len = struct.unpack(">H", seg_len_data)[0]
                f.seek(seg_len - 2, 1)

            # Read APP1 segment
            app1_len_data = f.read(2)
            if len(app1_len_data) < 2:
                return None
            app1_len = struct.unpack(">H", app1_len_data)[0]
            app1_data = f.read(app1_len - 2)

            # Verify "Exif\x00\x00" header
            if not app1_data.startswith(b"Exif\x00\x00"):
                return None

            tiff_data = app1_data[6:]
            return _parse_tiff_for_date(tiff_data)
    except (OSError, struct.error):
        return None


def _parse_tiff_for_date(tiff_data: bytes) -> tuple[str, str] | None:
    """Parse TIFF structure to find DateTimeOriginal (tag 0x9003)."""
    if len(tiff_data) < 8:
        return None

    # Determine byte order
    byte_order = tiff_data[0:2]
    if byte_order == b"MM":
        endian = ">"
    elif byte_order == b"II":
        endian = "<"
    else:
        return None

    # Read IFD0 offset
    ifd_offset = struct.unpack_from(f"{endian}I", tiff_data, 4)[0]

    # Search IFD entries for DateTimeOriginal (0x9003) or DateTime (0x0132)
    return _search_ifd_for_date(tiff_data, ifd_offset, endian)


def _search_ifd_for_date(
    tiff_data: bytes, ifd_offset: int, endian: str
) -> tuple[str, str] | None:
    """Search an IFD for date tags."""
    if ifd_offset + 2 > len(tiff_data):
        return None

    entry_count = struct.unpack_from(f"{endian}H", tiff_data, ifd_offset)[0]
    target_tags = {0x9003, 0x0132}  # DateTimeOriginal, DateTime

    for i in range(entry_count):
        entry_offset = ifd_offset + 2 + (i * 12)
        if entry_offset + 12 > len(tiff_data):
            break

        tag = struct.unpack_from(f"{endian}H", tiff_data, entry_offset)[0]
        if tag in target_tags:
            value_count = struct.unpack_from(f"{endian}I", tiff_data, entry_offset + 4)[0]
            value_offset = struct.unpack_from(f"{endian}I", tiff_data, entry_offset + 8)[0]

            if value_offset + value_count <= len(tiff_data):
                date_str = tiff_data[value_offset:value_offset + value_count]
                date_str = date_str.rstrip(b"\x00").decode("ascii", errors="ignore")
                # EXIF date format: "YYYY:MM:DD HH:MM:SS"
                parts = date_str.split(":")
                if len(parts) >= 2 and len(parts[0]) == 4:
                    year = parts[0]
                    month = parts[1]
                    return (year, month)

    return None


class PhotoOrganizer:
    """Organizes photo files by detecting and moving them to Year/Month subfolders."""

    def __init__(self, config: Config):
        self.config = config
        self._extensions = set()
        cat_data = config.categories.get("photos", {})
        for ext in cat_data.get("extensions", []):
            self._extensions.add(ext.lower())

    def is_photo(self, path: Path) -> bool:
        """Check if a file is a recognized photo type."""
        return path.suffix.lower() in self._extensions

    def scan(self, source_dir: Path) -> list[Path]:
        """Scan a directory and return all photo files."""
        if not source_dir.is_dir():
            return []
        return [f for f in source_dir.iterdir() if f.is_file() and self.is_photo(f)]

    def _get_date_subfolder(self, photo: Path) -> str:
        """Determine the date-based subfolder for a photo.

        Returns 'YYYY/MM' if EXIF date is found, otherwise 'unsorted'.
        """
        result = _extract_exif_date(photo)
        if result:
            year, month = result
            return f"{year}/{month}"
        return "unsorted"

    def organize(
        self, source_dir: Path, target_dir: Path, dry_run: bool = False
    ) -> dict:
        """Move photo files from source to Year/Month subdirectories of target.

        Returns a dict with move statistics.
        """
        photos = self.scan(source_dir)
        moved = 0
        would_move = 0
        duplicates = 0

        entries = []

        for photo in photos:
            subfolder = self._get_date_subfolder(photo)
            dest_dir = target_dir / subfolder
            dest = dest_dir / photo.name

            if dry_run:
                would_move += 1
                logger.info("[DRY RUN] Would move: %s -> %s", photo, dest)
                continue

            dest_dir.mkdir(parents=True, exist_ok=True)

            # Handle duplicates by adding a counter suffix
            if dest.exists():
                duplicates += 1
                stem = photo.stem
                suffix = photo.suffix
                counter = 1
                while dest.exists():
                    dest = dest_dir / f"{stem}_{counter}{suffix}"
                    counter += 1

            shutil.move(str(photo), str(dest))
            entries.append({"source": photo, "destination": dest})
            moved += 1
            logger.info("Moved: %s -> %s", photo, dest)

        return {
            "moved": moved,
            "would_move": would_move,
            "duplicates": duplicates,
            "entries": entries,
        }
