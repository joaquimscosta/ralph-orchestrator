# ABOUTME: Tests for the CLI module (argparse-based entry point).
# ABOUTME: Validates command parsing, argument handling, and CLI output.

import subprocess
import sys
from pathlib import Path
from unittest.mock import patch

import pytest

from file_organizer.cli import build_parser, main


class TestBuildParser:
    """Tests for argparse parser construction."""

    def test_parser_has_subcommands(self):
        parser = build_parser()
        # Should not raise
        args = parser.parse_args(["photos", "/tmp/test"])
        assert args.command == "photos"

    def test_photos_command(self):
        parser = build_parser()
        args = parser.parse_args(["photos", "/tmp/source"])
        assert args.command == "photos"
        assert args.source == "/tmp/source"

    def test_documents_command(self):
        parser = build_parser()
        args = parser.parse_args(["documents", "/tmp/source"])
        assert args.command == "documents"

    def test_downloads_command(self):
        parser = build_parser()
        args = parser.parse_args(["downloads", "/tmp/source"])
        assert args.command == "downloads"

    def test_custom_command(self):
        parser = build_parser()
        args = parser.parse_args(["custom", "/tmp/source", "--category", "code"])
        assert args.command == "custom"
        assert args.category == "code"

    def test_dry_run_flag(self):
        parser = build_parser()
        args = parser.parse_args(["photos", "/tmp/source", "--dry-run"])
        assert args.dry_run is True

    def test_undo_flag(self):
        parser = build_parser()
        args = parser.parse_args(["undo", "/tmp/manifest.json"])
        assert args.command == "undo"
        assert args.manifest == "/tmp/manifest.json"

    def test_config_flag(self):
        parser = build_parser()
        args = parser.parse_args(
            ["photos", "/tmp/source", "--config", "/tmp/config.yml"]
        )
        assert args.config == "/tmp/config.yml"

    def test_target_flag(self):
        parser = build_parser()
        args = parser.parse_args(
            ["photos", "/tmp/source", "--target", "/tmp/output"]
        )
        assert args.target == "/tmp/output"

    def test_verbose_flag(self):
        parser = build_parser()
        args = parser.parse_args(["photos", "/tmp/source", "--verbose"])
        assert args.verbose is True

    def test_log_file_flag(self):
        parser = build_parser()
        args = parser.parse_args(
            ["photos", "/tmp/source", "--log-file", "/tmp/organizer.log"]
        )
        assert args.log_file == "/tmp/organizer.log"


class TestMainCLI:
    """Integration tests for the main CLI entry point."""

    def test_photos_dry_run(self, tmp_path):
        source = tmp_path / "source"
        source.mkdir()
        (source / "test.jpg").write_bytes(b"\xff\xd8\xff")

        target = tmp_path / "output"

        with patch("sys.argv", [
            "file-organizer", "photos", str(source),
            "--target", str(target), "--dry-run"
        ]):
            exit_code = main()

        assert exit_code == 0
        # Dry run: file should still be in source
        assert (source / "test.jpg").exists()

    def test_log_file_flag(self, tmp_path):
        import logging

        source = tmp_path / "source"
        source.mkdir()
        (source / "test.jpg").write_bytes(b"\xff\xd8\xff")
        log_file = tmp_path / "organizer.log"

        # Reset logging to ensure basicConfig takes effect
        root_logger = logging.getLogger()
        for handler in root_logger.handlers[:]:
            root_logger.removeHandler(handler)

        with patch("sys.argv", [
            "file-organizer", "photos", str(source),
            "--target", str(tmp_path / "output"),
            "--dry-run", "--log-file", str(log_file)
        ]):
            exit_code = main()

        # Flush and close file handlers
        for handler in root_logger.handlers[:]:
            handler.flush()
            if isinstance(handler, logging.FileHandler):
                handler.close()
                root_logger.removeHandler(handler)

        assert exit_code == 0
        assert log_file.exists()
        log_content = log_file.read_text()
        assert len(log_content) > 0

    def test_organize_and_undo(self, tmp_path):
        source = tmp_path / "source"
        source.mkdir()
        (source / "photo.jpg").write_bytes(b"\xff\xd8\xff")
        target = tmp_path / "output"

        # Organize
        with patch("sys.argv", [
            "file-organizer", "photos", str(source),
            "--target", str(target)
        ]):
            main()

        assert not (source / "photo.jpg").exists()
        manifest = target / ".file_organizer_manifest.json"
        assert manifest.exists()

        # Undo
        with patch("sys.argv", [
            "file-organizer", "undo", str(manifest)
        ]):
            exit_code = main()

        assert exit_code == 0
        assert (source / "photo.jpg").exists()
