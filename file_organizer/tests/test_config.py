# ABOUTME: Tests for the config utility module.
# ABOUTME: Validates config loading, defaults, merging, and YAML persistence.

import os
import tempfile
from pathlib import Path

import pytest
import yaml

from file_organizer.utils.config import (
    DEFAULT_CONFIG,
    Config,
    load_config,
    save_config,
)


class TestDefaultConfig:
    """Tests for default configuration values."""

    def test_default_config_has_photo_extensions(self):
        assert "photos" in DEFAULT_CONFIG["categories"]
        assert ".jpg" in DEFAULT_CONFIG["categories"]["photos"]["extensions"]
        assert ".png" in DEFAULT_CONFIG["categories"]["photos"]["extensions"]

    def test_default_config_has_document_extensions(self):
        assert "documents" in DEFAULT_CONFIG["categories"]
        assert ".pdf" in DEFAULT_CONFIG["categories"]["documents"]["extensions"]
        assert ".docx" in DEFAULT_CONFIG["categories"]["documents"]["extensions"]

    def test_default_config_has_downloads_extensions(self):
        assert "downloads" in DEFAULT_CONFIG["categories"]

    def test_default_config_has_target_dirs(self):
        for category in DEFAULT_CONFIG["categories"].values():
            assert "target_dir" in category


class TestConfig:
    """Tests for Config dataclass behavior."""

    def test_config_from_dict(self):
        cfg = Config.from_dict(DEFAULT_CONFIG)
        assert cfg.categories is not None
        assert "photos" in cfg.categories

    def test_config_get_category_for_extension(self):
        cfg = Config.from_dict(DEFAULT_CONFIG)
        assert cfg.get_category_for_extension(".jpg") == "photos"
        assert cfg.get_category_for_extension(".pdf") == "documents"

    def test_config_unknown_extension_returns_none(self):
        cfg = Config.from_dict(DEFAULT_CONFIG)
        assert cfg.get_category_for_extension(".xyz_unknown") is None

    def test_config_get_target_dir(self):
        cfg = Config.from_dict(DEFAULT_CONFIG)
        target = cfg.get_target_dir("photos")
        assert target is not None
        assert isinstance(target, str)

    def test_config_custom_category(self):
        custom = {
            "categories": {
                "code": {
                    "extensions": [".py", ".rs", ".ts"],
                    "target_dir": "~/Code",
                }
            }
        }
        cfg = Config.from_dict(custom)
        assert cfg.get_category_for_extension(".py") == "code"
        assert cfg.get_category_for_extension(".rs") == "code"


class TestLoadConfig:
    """Tests for loading config from YAML files."""

    def test_load_config_returns_defaults_when_no_file(self):
        cfg = load_config(Path("/nonexistent/path/config.yml"))
        assert cfg.categories is not None
        assert "photos" in cfg.categories

    def test_load_config_from_yaml(self, tmp_path):
        config_file = tmp_path / "config.yml"
        custom_config = {
            "categories": {
                "music": {
                    "extensions": [".mp3", ".flac"],
                    "target_dir": "~/Music",
                }
            }
        }
        config_file.write_text(yaml.dump(custom_config))
        cfg = load_config(config_file)
        assert cfg.get_category_for_extension(".mp3") == "music"

    def test_load_config_merges_with_defaults(self, tmp_path):
        config_file = tmp_path / "config.yml"
        custom_config = {
            "categories": {
                "music": {
                    "extensions": [".mp3"],
                    "target_dir": "~/Music",
                }
            }
        }
        config_file.write_text(yaml.dump(custom_config))
        cfg = load_config(config_file)
        # Custom category present
        assert cfg.get_category_for_extension(".mp3") == "music"
        # Default categories also present
        assert cfg.get_category_for_extension(".jpg") == "photos"


class TestSaveConfig:
    """Tests for persisting config to YAML."""

    def test_save_config_creates_file(self, tmp_path):
        config_file = tmp_path / "config.yml"
        cfg = Config.from_dict(DEFAULT_CONFIG)
        save_config(cfg, config_file)
        assert config_file.exists()

    def test_save_config_roundtrip(self, tmp_path):
        config_file = tmp_path / "config.yml"
        cfg = Config.from_dict(DEFAULT_CONFIG)
        save_config(cfg, config_file)
        loaded = load_config(config_file)
        assert loaded.categories == cfg.categories
