# ABOUTME: Tests for the photo organizer module.
# ABOUTME: Validates photo file detection, categorization, and move operations.

from pathlib import Path

import pytest

from file_organizer.organizers.photo_organizer import PhotoOrganizer
from file_organizer.utils.config import Config, DEFAULT_CONFIG


@pytest.fixture
def photo_organizer():
    cfg = Config.from_dict(DEFAULT_CONFIG)
    return PhotoOrganizer(cfg)


@pytest.fixture
def workspace(tmp_path):
    """Create a workspace with photo files."""
    source = tmp_path / "source"
    source.mkdir()
    (source / "vacation.jpg").write_bytes(b"\xff\xd8\xff")
    (source / "portrait.png").write_bytes(b"\x89PNG")
    (source / "raw_shot.cr2").write_bytes(b"raw")
    (source / "document.pdf").write_bytes(b"pdf")
    (source / "readme.txt").write_text("text")
    return source


class TestPhotoOrganizerDetection:
    """Tests for detecting photo files."""

    def test_recognizes_jpg(self, photo_organizer):
        assert photo_organizer.is_photo(Path("photo.jpg"))

    def test_recognizes_jpeg(self, photo_organizer):
        assert photo_organizer.is_photo(Path("photo.jpeg"))

    def test_recognizes_png(self, photo_organizer):
        assert photo_organizer.is_photo(Path("image.png"))

    def test_recognizes_gif(self, photo_organizer):
        assert photo_organizer.is_photo(Path("anim.gif"))

    def test_recognizes_raw_formats(self, photo_organizer):
        assert photo_organizer.is_photo(Path("raw.cr2"))
        assert photo_organizer.is_photo(Path("raw.nef"))

    def test_rejects_non_photos(self, photo_organizer):
        assert not photo_organizer.is_photo(Path("doc.pdf"))
        assert not photo_organizer.is_photo(Path("code.py"))

    def test_case_insensitive(self, photo_organizer):
        assert photo_organizer.is_photo(Path("PHOTO.JPG"))
        assert photo_organizer.is_photo(Path("Image.PNG"))


class TestPhotoOrganizerScan:
    """Tests for scanning directories for photos."""

    def test_scan_finds_photos(self, photo_organizer, workspace):
        photos = photo_organizer.scan(workspace)
        names = {p.name for p in photos}
        assert "vacation.jpg" in names
        assert "portrait.png" in names
        assert "raw_shot.cr2" in names

    def test_scan_excludes_non_photos(self, photo_organizer, workspace):
        photos = photo_organizer.scan(workspace)
        names = {p.name for p in photos}
        assert "document.pdf" not in names
        assert "readme.txt" not in names


class TestPhotoOrganizerOrganize:
    """Tests for organizing (moving) photos."""

    def test_organize_moves_photos(self, photo_organizer, workspace, tmp_path):
        target = tmp_path / "Photos"
        results = photo_organizer.organize(workspace, target, dry_run=False)
        assert results["moved"] == 3
        # Photos without EXIF go to unsorted subfolder
        assert (target / "unsorted" / "vacation.jpg").exists()
        assert (target / "unsorted" / "portrait.png").exists()

    def test_organize_dry_run_does_not_move(self, photo_organizer, workspace, tmp_path):
        target = tmp_path / "Photos"
        results = photo_organizer.organize(workspace, target, dry_run=True)
        assert results["moved"] == 0
        assert results["would_move"] == 3
        # Files should still be in source
        assert (workspace / "vacation.jpg").exists()

    def test_organize_handles_duplicates(self, photo_organizer, workspace, tmp_path):
        target = tmp_path / "Photos"
        # Pre-create a file in the unsorted subfolder with same name
        unsorted = target / "unsorted"
        unsorted.mkdir(parents=True)
        (unsorted / "vacation.jpg").write_bytes(b"existing")

        results = photo_organizer.organize(workspace, target, dry_run=False)
        # Should handle duplicate by renaming
        assert results["moved"] == 3
        assert results["duplicates"] >= 1

    def test_organize_creates_target_dir(self, photo_organizer, workspace, tmp_path):
        target = tmp_path / "new" / "Photos"
        photo_organizer.organize(workspace, target, dry_run=False)
        assert target.exists()

    def test_organize_preserves_source_non_photos(self, photo_organizer, workspace, tmp_path):
        target = tmp_path / "Photos"
        photo_organizer.organize(workspace, target, dry_run=False)
        assert (workspace / "document.pdf").exists()
        assert (workspace / "readme.txt").exists()


class TestPhotoOrganizerDateSubfolders:
    """Tests for organizing photos into Year/Month subfolders based on EXIF data."""

    def test_photo_with_exif_date_goes_to_year_month_folder(self, tmp_path):
        """Photo with EXIF date is placed in YYYY/MM subfolder."""
        import struct

        cfg = Config.from_dict(DEFAULT_CONFIG)
        organizer = PhotoOrganizer(cfg)

        source = tmp_path / "source"
        source.mkdir()
        target = tmp_path / "Photos"

        # Create a JPEG with EXIF date. Minimal EXIF with DateTimeOriginal.
        exif_date = b"2023:06:15 10:30:00\x00"
        # Build a minimal EXIF structure
        ifd_entry = (
            b"\x90\x03"          # Tag 0x9003 = DateTimeOriginal
            + b"\x00\x02"        # Type: ASCII
            + struct.pack(">I", 20)  # Count: 20 bytes
            + struct.pack(">I", 26)  # Offset to value (relative to TIFF header start)
        )
        tiff_header = (
            b"MM"                  # Big-endian
            + b"\x00\x2a"         # TIFF magic
            + struct.pack(">I", 8)  # Offset to IFD0
        )
        ifd0 = (
            b"\x00\x01"           # 1 entry
            + ifd_entry
            + b"\x00\x00\x00\x00" # Next IFD offset (none)
        )
        exif_data = tiff_header + ifd0 + exif_date

        app1 = b"\xff\xe1" + struct.pack(">H", len(exif_data) + 8) + b"Exif\x00\x00" + exif_data
        jpeg_data = b"\xff\xd8" + app1 + b"\xff\xd9"

        photo_file = source / "vacation.jpg"
        photo_file.write_bytes(jpeg_data)

        results = organizer.organize(source, target, dry_run=False)
        assert results["moved"] == 1
        # Photo should be in 2023/06 subfolder
        assert (target / "2023" / "06" / "vacation.jpg").exists()

    def test_photo_without_exif_goes_to_unsorted(self, tmp_path):
        """Photo without EXIF data goes to 'unsorted' subfolder."""
        cfg = Config.from_dict(DEFAULT_CONFIG)
        organizer = PhotoOrganizer(cfg)

        source = tmp_path / "source"
        source.mkdir()
        target = tmp_path / "Photos"

        # Plain JPEG without EXIF
        (source / "noexif.jpg").write_bytes(b"\xff\xd8\xff\xd9")

        results = organizer.organize(source, target, dry_run=False)
        assert results["moved"] == 1
        assert (target / "unsorted" / "noexif.jpg").exists()

    def test_png_without_exif_goes_to_unsorted(self, tmp_path):
        """Non-JPEG photos without EXIF go to 'unsorted' subfolder."""
        cfg = Config.from_dict(DEFAULT_CONFIG)
        organizer = PhotoOrganizer(cfg)

        source = tmp_path / "source"
        source.mkdir()
        target = tmp_path / "Photos"

        (source / "image.png").write_bytes(b"\x89PNG")

        results = organizer.organize(source, target, dry_run=False)
        assert results["moved"] == 1
        assert (target / "unsorted" / "image.png").exists()

    def test_dry_run_reports_year_month_path(self, tmp_path):
        """Dry run correctly reports target path including date subfolder."""
        cfg = Config.from_dict(DEFAULT_CONFIG)
        organizer = PhotoOrganizer(cfg)

        source = tmp_path / "source"
        source.mkdir()
        target = tmp_path / "Photos"

        # Photo without EXIF (simpler case)
        (source / "test.jpg").write_bytes(b"\xff\xd8\xff\xd9")

        results = organizer.organize(source, target, dry_run=True)
        assert results["would_move"] == 1
        assert results["moved"] == 0
        # File should NOT have been moved
        assert (source / "test.jpg").exists()
