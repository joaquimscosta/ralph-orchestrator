# ABOUTME: Backup and undo functionality for file organizer operations.
# ABOUTME: Tracks file moves in a JSON manifest and supports reverting them.

import json
import logging
import shutil
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

logger = logging.getLogger(__name__)


def create_backup_entry(source: Path, destination: Path) -> dict:
    """Create a backup manifest entry for a single file move."""
    return {
        "source": str(source),
        "destination": str(destination),
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


@dataclass
class BackupManifest:
    """Tracks all file moves for potential undo."""

    entries: list = field(default_factory=list)

    def add(self, entry: dict) -> None:
        self.entries.append(entry)


def save_manifest(manifest: BackupManifest, path: Path) -> None:
    """Persist the backup manifest to a JSON file."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w") as f:
        json.dump({"entries": manifest.entries}, f, indent=2)


def load_manifest(path: Path) -> BackupManifest:
    """Load a backup manifest from a JSON file."""
    if not path.exists():
        return BackupManifest()

    with open(path, "r") as f:
        data = json.load(f)

    manifest = BackupManifest()
    manifest.entries = data.get("entries", [])
    return manifest


def undo_moves(manifest: BackupManifest) -> dict:
    """Undo all file moves recorded in the manifest.

    Returns a dict with 'restored' and 'failed' counts.
    """
    restored = 0
    failed = 0

    for entry in reversed(manifest.entries):
        src = Path(entry["source"])
        dst = Path(entry["destination"])

        if not dst.exists():
            logger.warning("Cannot undo: destination %s no longer exists", dst)
            failed += 1
            continue

        try:
            src.parent.mkdir(parents=True, exist_ok=True)
            shutil.move(str(dst), str(src))
            restored += 1
            logger.info("Restored: %s -> %s", dst, src)
        except OSError as e:
            logger.error("Failed to restore %s: %s", dst, e)
            failed += 1

    return {"restored": restored, "failed": failed}
