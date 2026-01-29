# ABOUTME: Tests for the document organizer module.
# ABOUTME: Validates document file detection, categorization, and move operations.

from pathlib import Path

import pytest

from file_organizer.organizers.document_organizer import DocumentOrganizer
from file_organizer.utils.config import Config, DEFAULT_CONFIG


@pytest.fixture
def doc_organizer():
    cfg = Config.from_dict(DEFAULT_CONFIG)
    return DocumentOrganizer(cfg)


@pytest.fixture
def workspace(tmp_path):
    """Create a workspace with document files."""
    source = tmp_path / "source"
    source.mkdir()
    (source / "report.pdf").write_bytes(b"%PDF")
    (source / "notes.docx").write_bytes(b"PK")
    (source / "data.xlsx").write_bytes(b"PK")
    (source / "slides.pptx").write_bytes(b"PK")
    (source / "plain.txt").write_text("text")
    (source / "photo.jpg").write_bytes(b"\xff\xd8\xff")
    return source


class TestDocumentOrganizerDetection:
    """Tests for detecting document files."""

    def test_recognizes_pdf(self, doc_organizer):
        assert doc_organizer.is_document(Path("report.pdf"))

    def test_recognizes_docx(self, doc_organizer):
        assert doc_organizer.is_document(Path("letter.docx"))

    def test_recognizes_xlsx(self, doc_organizer):
        assert doc_organizer.is_document(Path("data.xlsx"))

    def test_recognizes_txt(self, doc_organizer):
        assert doc_organizer.is_document(Path("notes.txt"))

    def test_rejects_non_documents(self, doc_organizer):
        assert not doc_organizer.is_document(Path("photo.jpg"))
        assert not doc_organizer.is_document(Path("code.py"))

    def test_case_insensitive(self, doc_organizer):
        assert doc_organizer.is_document(Path("REPORT.PDF"))


class TestDocumentOrganizerScan:
    """Tests for scanning directories for documents."""

    def test_scan_finds_documents(self, doc_organizer, workspace):
        docs = doc_organizer.scan(workspace)
        names = {d.name for d in docs}
        assert "report.pdf" in names
        assert "notes.docx" in names
        assert "data.xlsx" in names
        assert "plain.txt" in names

    def test_scan_excludes_non_documents(self, doc_organizer, workspace):
        docs = doc_organizer.scan(workspace)
        names = {d.name for d in docs}
        assert "photo.jpg" not in names


class TestDocumentOrganizerOrganize:
    """Tests for organizing (moving) documents."""

    def test_organize_moves_documents(self, doc_organizer, workspace, tmp_path):
        target = tmp_path / "Documents"
        results = doc_organizer.organize(workspace, target, dry_run=False)
        assert results["moved"] >= 4
        # Documents now go to extension-based subfolders
        assert (target / "pdf" / "report.pdf").exists()

    def test_organize_dry_run(self, doc_organizer, workspace, tmp_path):
        target = tmp_path / "Documents"
        results = doc_organizer.organize(workspace, target, dry_run=True)
        assert results["moved"] == 0
        assert results["would_move"] >= 4
        assert (workspace / "report.pdf").exists()

    def test_organize_handles_duplicates(self, doc_organizer, workspace, tmp_path):
        target = tmp_path / "Documents"
        target.mkdir(parents=True)
        # Pre-create the extension subfolder with existing file
        pdf_dir = target / "pdf"
        pdf_dir.mkdir()
        (pdf_dir / "report.pdf").write_bytes(b"existing")

        results = doc_organizer.organize(workspace, target, dry_run=False)
        assert results["duplicates"] >= 1


class TestDocumentOrganizerExtensionSubfolders:
    """Tests for organizing documents into extension-based subfolders."""

    def test_pdf_goes_to_pdf_subfolder(self, tmp_path):
        cfg = Config.from_dict(DEFAULT_CONFIG)
        organizer = DocumentOrganizer(cfg)

        source = tmp_path / "source"
        source.mkdir()
        target = tmp_path / "Documents"

        (source / "report.pdf").write_bytes(b"%PDF")

        results = organizer.organize(source, target, dry_run=False)
        assert results["moved"] == 1
        assert (target / "pdf" / "report.pdf").exists()

    def test_docx_goes_to_docx_subfolder(self, tmp_path):
        cfg = Config.from_dict(DEFAULT_CONFIG)
        organizer = DocumentOrganizer(cfg)

        source = tmp_path / "source"
        source.mkdir()
        target = tmp_path / "Documents"

        (source / "letter.docx").write_bytes(b"PK")

        results = organizer.organize(source, target, dry_run=False)
        assert results["moved"] == 1
        assert (target / "docx" / "letter.docx").exists()

    def test_txt_goes_to_txt_subfolder(self, tmp_path):
        cfg = Config.from_dict(DEFAULT_CONFIG)
        organizer = DocumentOrganizer(cfg)

        source = tmp_path / "source"
        source.mkdir()
        target = tmp_path / "Documents"

        (source / "notes.txt").write_text("some notes")

        results = organizer.organize(source, target, dry_run=False)
        assert results["moved"] == 1
        assert (target / "txt" / "notes.txt").exists()

    def test_multiple_extensions_sorted_correctly(self, tmp_path):
        cfg = Config.from_dict(DEFAULT_CONFIG)
        organizer = DocumentOrganizer(cfg)

        source = tmp_path / "source"
        source.mkdir()
        target = tmp_path / "Documents"

        (source / "report.pdf").write_bytes(b"%PDF")
        (source / "notes.txt").write_text("text")
        (source / "slides.pptx").write_bytes(b"PK")

        results = organizer.organize(source, target, dry_run=False)
        assert results["moved"] == 3
        assert (target / "pdf" / "report.pdf").exists()
        assert (target / "txt" / "notes.txt").exists()
        assert (target / "pptx" / "slides.pptx").exists()

    def test_dry_run_does_not_create_subfolders(self, tmp_path):
        cfg = Config.from_dict(DEFAULT_CONFIG)
        organizer = DocumentOrganizer(cfg)

        source = tmp_path / "source"
        source.mkdir()
        target = tmp_path / "Documents"

        (source / "report.pdf").write_bytes(b"%PDF")

        results = organizer.organize(source, target, dry_run=True)
        assert results["would_move"] == 1
        assert not (target / "pdf").exists()
        assert (source / "report.pdf").exists()
