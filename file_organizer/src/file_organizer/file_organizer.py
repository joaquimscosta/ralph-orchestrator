# ABOUTME: Main file organizer that dispatches to category-specific organizers.
# ABOUTME: Coordinates photo, document, and download organization with backup tracking.

import logging
from pathlib import Path

from tqdm import tqdm

from file_organizer.organizers.document_organizer import DocumentOrganizer
from file_organizer.organizers.downloads_organizer import DownloadsOrganizer
from file_organizer.organizers.photo_organizer import PhotoOrganizer
from file_organizer.utils.backup import (
    BackupManifest,
    create_backup_entry,
    load_manifest,
    save_manifest,
    undo_moves,
)
from file_organizer.utils.config import Config

logger = logging.getLogger(__name__)


class FileOrganizer:
    """Top-level organizer that delegates to category-specific organizers."""

    def __init__(self, config: Config, base_target: Path):
        self.config = config
        self.base_target = base_target
        self._organizers = self._build_organizers()

    def _build_organizers(self) -> dict:
        """Build a mapping of category names to organizer instances."""
        organizers = {}
        # Map known category names to their organizer classes
        category_map = {
            "photos": PhotoOrganizer,
            "documents": DocumentOrganizer,
            "downloads": DownloadsOrganizer,
        }
        for cat_name, cls in category_map.items():
            if cat_name in self.config.categories:
                organizers[cat_name] = cls(self.config)

        return organizers

    def organize(
        self,
        source_dir: Path,
        dry_run: bool = False,
        categories: list[str] | None = None,
    ) -> dict:
        """Organize files from source_dir into category subdirectories.

        Args:
            source_dir: Directory containing files to organize.
            dry_run: If True, only report what would be done.
            categories: Optional list of categories to organize. None means all.

        Returns:
            Dict with organization statistics.
        """
        total_moved = 0
        total_would_move = 0
        manifest = BackupManifest()
        category_results = {}

        # Count total eligible files for progress bar
        total_files = self._count_eligible_files(source_dir, categories)
        action = "Scanning" if dry_run else "Organizing"
        progress = tqdm(total=total_files, desc=action, unit="file")

        # For categories with dedicated organizers, use them
        for cat_name, organizer in self._organizers.items():
            if categories and cat_name not in categories:
                continue

            target_dir_name = self.config.get_target_dir(cat_name) or cat_name
            target = self.base_target / target_dir_name

            results = organizer.organize(source_dir, target, dry_run=dry_run)
            category_results[cat_name] = results
            total_moved += results["moved"]
            total_would_move += results["would_move"]
            progress.update(results["moved"] + results["would_move"])

            # Record backup entries
            for entry in results.get("entries", []):
                manifest.add(
                    create_backup_entry(
                        source=entry["source"],
                        destination=entry["destination"],
                    )
                )

        # For categories without dedicated organizers, use generic extension matching
        for cat_name, cat_data in self.config.categories.items():
            if cat_name in self._organizers:
                continue
            if categories and cat_name not in categories:
                continue

            target_dir_name = cat_data.get("target_dir", cat_name)
            target = self.base_target / target_dir_name
            extensions = {e.lower() for e in cat_data.get("extensions", [])}

            results = self._organize_generic(
                source_dir, target, extensions, dry_run=dry_run
            )
            category_results[cat_name] = results
            total_moved += results["moved"]
            total_would_move += results["would_move"]
            progress.update(results["moved"] + results["would_move"])

            for entry in results.get("entries", []):
                manifest.add(
                    create_backup_entry(
                        source=entry["source"],
                        destination=entry["destination"],
                    )
                )

        progress.close()

        # Save manifest (only if we actually moved files)
        if not dry_run and total_moved > 0:
            self.base_target.mkdir(parents=True, exist_ok=True)
            manifest_path = self.base_target / ".file_organizer_manifest.json"
            save_manifest(manifest, manifest_path)

        return {
            "total_moved": total_moved,
            "total_would_move": total_would_move,
            "categories": category_results,
        }

    def _count_eligible_files(
        self, source_dir: Path, categories: list[str] | None = None
    ) -> int:
        """Count files in source_dir that match configured category extensions."""
        if not source_dir.is_dir():
            return 0

        # Gather all extensions for active categories
        all_extensions: set[str] = set()
        for cat_name, cat_data in self.config.categories.items():
            if categories and cat_name not in categories:
                continue
            for ext in cat_data.get("extensions", []):
                all_extensions.add(ext.lower())

        count = 0
        for f in source_dir.iterdir():
            if f.is_file() and f.suffix.lower() in all_extensions:
                count += 1
        return count

    def _organize_generic(
        self,
        source_dir: Path,
        target_dir: Path,
        extensions: set[str],
        dry_run: bool = False,
    ) -> dict:
        """Generic organizer for categories without dedicated organizer classes."""
        import shutil

        moved = 0
        would_move = 0
        duplicates = 0
        entries = []

        if not source_dir.is_dir():
            return {"moved": 0, "would_move": 0, "duplicates": 0, "entries": []}

        if not dry_run:
            target_dir.mkdir(parents=True, exist_ok=True)

        for f in source_dir.iterdir():
            if not f.is_file():
                continue
            if f.suffix.lower() not in extensions:
                continue

            dest = target_dir / f.name

            if dry_run:
                would_move += 1
                continue

            if dest.exists():
                duplicates += 1
                stem = f.stem
                suffix = f.suffix
                counter = 1
                while dest.exists():
                    dest = target_dir / f"{stem}_{counter}{suffix}"
                    counter += 1

            shutil.move(str(f), str(dest))
            entries.append({"source": f, "destination": dest})
            moved += 1

        return {
            "moved": moved,
            "would_move": would_move,
            "duplicates": duplicates,
            "entries": entries,
        }

    def undo(self, manifest_path: Path) -> dict:
        """Undo a previous organize operation using a backup manifest."""
        manifest = load_manifest(manifest_path)
        return undo_moves(manifest)
