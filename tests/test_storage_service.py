from __future__ import annotations

import pytest

from app.exceptions import InvalidDocumentError, UnsupportedDocumentError
from app.config import Settings
from app.services.storage_service import (
    remove_project_files,
    sanitize_filename,
    validate_docx_structure,
    validate_original_filename,
)

from tests.conftest import make_docx_bytes


def test_sanitize_filename_removes_unsafe_characters() -> None:
    assert sanitize_filename("reporte trabajo @ junio.docx") == "reporte_trabajo_junio.docx"


def test_validate_original_filename_rejects_path_traversal() -> None:
    with pytest.raises(InvalidDocumentError):
        validate_original_filename("../reporte.docx")


def test_validate_original_filename_rejects_docm() -> None:
    with pytest.raises(UnsupportedDocumentError):
        validate_original_filename("reporte.docm")


def test_validate_docx_structure_accepts_real_docx(workspace_tmp_path) -> None:
    path = workspace_tmp_path / "valid.docx"
    path.write_bytes(make_docx_bytes())
    validate_docx_structure(path)


def test_validate_docx_structure_rejects_plain_file(workspace_tmp_path) -> None:
    path = workspace_tmp_path / "invalid.docx"
    path.write_text("not a word file", encoding="utf-8")
    with pytest.raises(InvalidDocumentError):
        validate_docx_structure(path)


def test_remove_project_files_removes_upload_generated_and_export_dirs(workspace_tmp_path) -> None:
    settings = Settings(storage_root=workspace_tmp_path / "storage")
    project_id = "project-id"
    for child in ("uploads", "generated", "exports"):
        directory = settings.storage_root / child / project_id
        directory.mkdir(parents=True)
        (directory / "file.txt").write_text("data", encoding="utf-8")

    remove_project_files(settings, project_id)

    for child in ("uploads", "generated", "exports"):
        assert not (settings.storage_root / child / project_id).exists()
