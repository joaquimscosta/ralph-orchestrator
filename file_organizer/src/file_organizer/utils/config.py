# ABOUTME: Configuration management for the file organizer tool.
# ABOUTME: Loads/saves YAML config, provides defaults, and maps extensions to categories.

from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

import yaml

DEFAULT_CONFIG = {
    "categories": {
        "photos": {
            "extensions": [
                ".jpg", ".jpeg", ".png", ".gif", ".bmp", ".tiff", ".tif",
                ".webp", ".heic", ".heif", ".svg", ".raw", ".cr2", ".nef",
                ".arw", ".dng", ".orf", ".rw2",
            ],
            "target_dir": "Photos",
        },
        "documents": {
            "extensions": [
                ".pdf", ".doc", ".docx", ".xls", ".xlsx", ".ppt", ".pptx",
                ".odt", ".ods", ".odp", ".txt", ".rtf", ".csv", ".md",
                ".tex", ".epub",
            ],
            "target_dir": "Documents",
        },
        "downloads": {
            "extensions": [
                ".dmg", ".exe", ".msi", ".pkg", ".deb", ".rpm", ".appimage",
                ".zip", ".tar", ".gz", ".bz2", ".xz", ".7z", ".rar",
                ".iso", ".img",
            ],
            "target_dir": "Downloads",
        },
    }
}


@dataclass
class Config:
    """Holds file organizer configuration with extension-to-category mapping."""

    categories: dict = field(default_factory=dict)
    _extension_map: dict = field(default_factory=dict, repr=False)

    @classmethod
    def from_dict(cls, data: dict) -> "Config":
        categories = data.get("categories", {})
        instance = cls(categories=categories)
        instance._build_extension_map()
        return instance

    def _build_extension_map(self):
        self._extension_map = {}
        for category_name, category_data in self.categories.items():
            for ext in category_data.get("extensions", []):
                self._extension_map[ext.lower()] = category_name

    def get_category_for_extension(self, ext: str) -> Optional[str]:
        return self._extension_map.get(ext.lower())

    def get_target_dir(self, category: str) -> Optional[str]:
        cat_data = self.categories.get(category)
        if cat_data:
            return cat_data.get("target_dir")
        return None


def load_config(config_path: Path) -> Config:
    """Load config from YAML file, merging with defaults."""
    defaults = Config.from_dict(DEFAULT_CONFIG)

    if not config_path.exists():
        return defaults

    with open(config_path, "r") as f:
        user_data = yaml.safe_load(f) or {}

    # Merge user categories on top of defaults
    merged_categories = dict(DEFAULT_CONFIG["categories"])
    user_categories = user_data.get("categories", {})
    merged_categories.update(user_categories)

    return Config.from_dict({"categories": merged_categories})


def save_config(config: Config, config_path: Path) -> None:
    """Save config to a YAML file."""
    config_path.parent.mkdir(parents=True, exist_ok=True)
    data = {"categories": config.categories}
    with open(config_path, "w") as f:
        yaml.dump(data, f, default_flow_style=False)
