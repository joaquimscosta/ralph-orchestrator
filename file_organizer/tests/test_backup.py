# ABOUTME: Tests for the backup/undo utility module.
# ABOUTME: Validates backup creation, undo operations, and manifest tracking.

import json
from pathlib import Path

import pytest

from file_organizer.utils.backup import (
    BackupManifest,
    create_backup_entry,
    load_manifest,
    save_manifest,
    undo_moves,
)


class TestBackupManifest:
    """Tests for the BackupManifest data structure."""

    def test_manifest_starts_empty(self):
        manifest = BackupManifest()
        assert len(manifest.entries) == 0

    def test_add_entry(self):
        manifest = BackupManifest()
        entry = create_backup_entry(
            source=Path("/home/user/photo.jpg"),
            destination=Path("/home/user/Photos/photo.jpg"),
        )
        manifest.add(entry)
        assert len(manifest.entries) == 1
        assert manifest.entries[0]["source"] == str(Path("/home/user/photo.jpg"))
        assert manifest.entries[0]["destination"] == str(
            Path("/home/user/Photos/photo.jpg")
        )


class TestBackupEntry:
    """Tests for creating individual backup entries."""

    def test_entry_has_required_fields(self):
        entry = create_backup_entry(
            source=Path("/tmp/a.txt"),
            destination=Path("/tmp/b/a.txt"),
        )
        assert "source" in entry
        assert "destination" in entry
        assert "timestamp" in entry

    def test_entry_stores_paths_as_strings(self):
        entry = create_backup_entry(
            source=Path("/tmp/a.txt"),
            destination=Path("/tmp/b/a.txt"),
        )
        assert isinstance(entry["source"], str)
        assert isinstance(entry["destination"], str)


class TestManifestPersistence:
    """Tests for saving and loading manifests."""

    def test_save_and_load_roundtrip(self, tmp_path):
        manifest_file = tmp_path / ".file_organizer_manifest.json"
        manifest = BackupManifest()
        manifest.add(
            create_backup_entry(
                source=Path("/tmp/x.jpg"),
                destination=Path("/tmp/photos/x.jpg"),
            )
        )
        save_manifest(manifest, manifest_file)
        loaded = load_manifest(manifest_file)
        assert len(loaded.entries) == 1
        assert loaded.entries[0]["source"] == str(Path("/tmp/x.jpg"))

    def test_load_nonexistent_returns_empty(self):
        loaded = load_manifest(Path("/nonexistent/manifest.json"))
        assert len(loaded.entries) == 0


class TestUndoMoves:
    """Tests for undoing file moves."""

    def test_undo_moves_files_back(self, tmp_path):
        # Create source and destination
        source_dir = tmp_path / "source"
        dest_dir = tmp_path / "dest"
        source_dir.mkdir()
        dest_dir.mkdir()

        # Create a file and "move" it
        original = source_dir / "test.txt"
        original.write_text("hello")
        moved = dest_dir / "test.txt"
        original.rename(moved)

        # Create manifest reflecting the move
        manifest = BackupManifest()
        manifest.add(
            create_backup_entry(
                source=Path(str(original)),
                destination=Path(str(moved)),
            )
        )

        # Undo should move it back
        results = undo_moves(manifest)
        assert moved.exists() is False
        assert original.exists() is True
        assert original.read_text() == "hello"
        assert results["restored"] == 1
        assert results["failed"] == 0

    def test_undo_handles_missing_destination(self, tmp_path):
        manifest = BackupManifest()
        manifest.add(
            create_backup_entry(
                source=Path(str(tmp_path / "gone_source.txt")),
                destination=Path(str(tmp_path / "gone_dest.txt")),
            )
        )
        results = undo_moves(manifest)
        assert results["restored"] == 0
        assert results["failed"] == 1

    def test_undo_preserves_permissions(self, tmp_path):
        source_dir = tmp_path / "source"
        dest_dir = tmp_path / "dest"
        source_dir.mkdir()
        dest_dir.mkdir()

        original = source_dir / "script.sh"
        original.write_text("#!/bin/bash")
        original.chmod(0o755)
        moved = dest_dir / "script.sh"
        original.rename(moved)

        manifest = BackupManifest()
        manifest.add(
            create_backup_entry(
                source=Path(str(original)),
                destination=Path(str(moved)),
            )
        )

        undo_moves(manifest)
        assert original.exists()
        # Permissions should be preserved since we use shutil.move
        assert original.stat().st_mode & 0o777 == 0o755
