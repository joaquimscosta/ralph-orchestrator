# ABOUTME: Tests for the main file_organizer module.
# ABOUTME: Validates the top-level organize function that dispatches to sub-organizers.

from pathlib import Path
from unittest.mock import patch

import pytest

from file_organizer.file_organizer import FileOrganizer
from file_organizer.utils.backup import load_manifest
from file_organizer.utils.config import Config, DEFAULT_CONFIG


@pytest.fixture
def organizer(tmp_path):
    cfg = Config.from_dict(DEFAULT_CONFIG)
    return FileOrganizer(config=cfg, base_target=tmp_path / "organized")


@pytest.fixture
def mixed_workspace(tmp_path):
    """Create a workspace with mixed file types."""
    source = tmp_path / "messy"
    source.mkdir()
    (source / "vacation.jpg").write_bytes(b"\xff\xd8\xff")
    (source / "sunset.png").write_bytes(b"\x89PNG")
    (source / "report.pdf").write_bytes(b"%PDF")
    (source / "notes.docx").write_bytes(b"PK")
    (source / "installer.dmg").write_bytes(b"data")
    (source / "archive.zip").write_bytes(b"PK")
    (source / "random.xyz").write_bytes(b"unknown")
    return source


class TestFileOrganizerOrganize:
    """Tests for the main organize dispatch."""

    def test_organizes_photos_and_documents(self, organizer, mixed_workspace, tmp_path):
        results = organizer.organize(mixed_workspace, dry_run=False)
        assert results["total_moved"] > 0
        # Photos moved to photos target
        organized = tmp_path / "organized"
        assert any(organized.rglob("vacation.jpg"))
        assert any(organized.rglob("report.pdf"))

    def test_dry_run_moves_nothing(self, organizer, mixed_workspace):
        results = organizer.organize(mixed_workspace, dry_run=True)
        assert results["total_moved"] == 0
        assert results["total_would_move"] > 0

    def test_creates_backup_manifest(self, organizer, mixed_workspace, tmp_path):
        organizer.organize(mixed_workspace, dry_run=False)
        manifest_path = tmp_path / "organized" / ".file_organizer_manifest.json"
        assert manifest_path.exists()
        manifest = load_manifest(manifest_path)
        assert len(manifest.entries) > 0

    def test_unknown_extensions_left_in_place(self, organizer, mixed_workspace):
        organizer.organize(mixed_workspace, dry_run=False)
        assert (mixed_workspace / "random.xyz").exists()


class TestFileOrganizerCustomCategory:
    """Tests for custom category support."""

    def test_custom_category_organization(self, tmp_path):
        custom_config = {
            "categories": {
                "code": {
                    "extensions": [".py", ".rs"],
                    "target_dir": "Code",
                }
            }
        }
        cfg = Config.from_dict(custom_config)
        organizer = FileOrganizer(config=cfg, base_target=tmp_path / "organized")

        source = tmp_path / "source"
        source.mkdir()
        (source / "main.py").write_text("print('hello')")
        (source / "lib.rs").write_text("fn main() {}")

        results = organizer.organize(source, dry_run=False)
        assert results["total_moved"] == 2
        assert (tmp_path / "organized" / "Code" / "main.py").exists()


class TestFileOrganizerDownloads:
    """Tests for downloads category organization via generic path."""

    def test_organizes_download_files(self, organizer, tmp_path):
        source = tmp_path / "source"
        source.mkdir()
        (source / "app.dmg").write_bytes(b"data")
        (source / "setup.exe").write_bytes(b"MZ")
        (source / "archive.zip").write_bytes(b"PK")
        (source / "disk.iso").write_bytes(b"CD001")

        results = organizer.organize(source, dry_run=False, categories=["downloads"])
        assert results["total_moved"] == 4
        organized = tmp_path / "organized"
        # Downloads are grouped by type subfolder
        assert (organized / "Downloads" / "installers" / "app.dmg").exists()
        assert (organized / "Downloads" / "installers" / "setup.exe").exists()
        assert (organized / "Downloads" / "archives" / "archive.zip").exists()
        assert (organized / "Downloads" / "disk_images" / "disk.iso").exists()

    def test_downloads_dry_run(self, organizer, tmp_path):
        source = tmp_path / "source"
        source.mkdir()
        (source / "app.dmg").write_bytes(b"data")
        (source / "archive.zip").write_bytes(b"PK")

        results = organizer.organize(source, dry_run=True, categories=["downloads"])
        assert results["total_moved"] == 0
        assert results["total_would_move"] == 2
        # Files should still be in source
        assert (source / "app.dmg").exists()
        assert (source / "archive.zip").exists()


class TestFileOrganizerProgressBar:
    """Tests for progress bar integration."""

    def test_organize_uses_tqdm_progress(self, organizer, tmp_path):
        source = tmp_path / "source"
        source.mkdir()
        (source / "photo.jpg").write_bytes(b"\xff\xd8\xff")
        (source / "doc.pdf").write_bytes(b"%PDF")

        with patch("file_organizer.file_organizer.tqdm") as mock_tqdm:
            # Make tqdm passthrough so organize still works
            mock_tqdm.return_value.__enter__ = lambda s: s
            mock_tqdm.return_value.__exit__ = lambda s, *a: None
            mock_tqdm.return_value.update = lambda *a: None
            results = organizer.organize(source, dry_run=False)
            assert results["total_moved"] > 0
            mock_tqdm.assert_called()

    def test_dry_run_uses_tqdm_progress(self, organizer, tmp_path):
        source = tmp_path / "source"
        source.mkdir()
        (source / "photo.jpg").write_bytes(b"\xff\xd8\xff")

        with patch("file_organizer.file_organizer.tqdm") as mock_tqdm:
            mock_tqdm.return_value.__enter__ = lambda s: s
            mock_tqdm.return_value.__exit__ = lambda s, *a: None
            mock_tqdm.return_value.update = lambda *a: None
            results = organizer.organize(source, dry_run=True)
            assert results["total_would_move"] > 0
            mock_tqdm.assert_called()


class TestFileOrganizerUndo:
    """Tests for undo functionality."""

    def test_undo_restores_files(self, organizer, mixed_workspace, tmp_path):
        organizer.organize(mixed_workspace, dry_run=False)
        # Files should be moved
        assert not (mixed_workspace / "vacation.jpg").exists()

        # Undo
        manifest_path = tmp_path / "organized" / ".file_organizer_manifest.json"
        results = organizer.undo(manifest_path)
        assert results["restored"] > 0
        assert (mixed_workspace / "vacation.jpg").exists()
