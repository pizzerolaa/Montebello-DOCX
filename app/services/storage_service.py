from __future__ import annotations

import hashlib
import re
import shutil
import zipfile
from dataclasses import dataclass
from pathlib import Path

from fastapi import UploadFile

from app.config import Settings
from app.exceptions import InvalidDocumentError, StorageError, UnsupportedDocumentError


SAFE_FILENAME_RE = re.compile(r"[^A-Za-z0-9._-]+")
DOCX_MIME_ALIASES = {"application/octet-stream"}


@dataclass(frozen=True)
class StoredUpload:
    original_filename: str
    safe_filename: str
    stored_path: Path
    sha256: str
    file_size: int


def sanitize_filename(filename: str) -> str:
    """Return a filesystem-safe display filename while preserving the extension."""
    basename = Path(filename).name.strip()
    if not basename:
        return "documento.docx"
    safe = SAFE_FILENAME_RE.sub("_", basename).strip("._")
    return safe or "documento.docx"


def validate_original_filename(filename: str | None) -> str:
    if not filename:
        raise UnsupportedDocumentError("El archivo debe tener nombre.")
    if Path(filename).name != filename or "/" in filename or "\\" in filename:
        raise InvalidDocumentError("El nombre del archivo no es seguro.")
    suffix = Path(filename).suffix.lower()
    if suffix == ".docm":
        raise UnsupportedDocumentError("Los archivos .docm con macros no estan permitidos.")
    if suffix != ".docx":
        raise UnsupportedDocumentError("Solo se aceptan archivos .docx.")
    return filename


def ensure_project_storage(settings: Settings, project_id: str) -> Path:
    root = (settings.storage_root / "uploads" / project_id).resolve()
    storage_root = settings.storage_root.resolve()
    if storage_root not in root.parents and root != storage_root:
        raise StorageError("La ruta de almacenamiento no es valida.")
    root.mkdir(parents=True, exist_ok=True)
    return root


def validate_docx_structure(path: Path) -> None:
    """Validate that a stored file is a non-macro Word .docx package."""
    try:
        with zipfile.ZipFile(path) as archive:
            names = set(archive.namelist())
    except zipfile.BadZipFile as exc:
        raise InvalidDocumentError("El archivo .docx no tiene una estructura ZIP valida.") from exc

    required = {"[Content_Types].xml", "word/document.xml"}
    if not required.issubset(names):
        raise InvalidDocumentError("El archivo no contiene la estructura requerida de Word.")
    if any(name.lower().endswith("vbaproject.bin") for name in names):
        raise UnsupportedDocumentError("Los documentos con macros no estan permitidos.")


async def store_docx_upload(
    upload: UploadFile,
    *,
    project_id: str,
    document_id: str,
    settings: Settings,
) -> StoredUpload:
    """Stream, validate, hash, and store one uploaded .docx file."""
    original_filename = validate_original_filename(upload.filename)
    if upload.content_type:
        allowed = {settings.allowed_docx_mime, *DOCX_MIME_ALIASES}
        if upload.content_type not in allowed:
            raise UnsupportedDocumentError("El tipo MIME del archivo no corresponde a un .docx.")

    safe_filename = sanitize_filename(original_filename)
    project_dir = ensure_project_storage(settings, project_id)
    destination = project_dir / f"{document_id}.docx"
    digest = hashlib.sha256()
    total = 0

    try:
        with destination.open("wb") as out_file:
            while True:
                chunk = await upload.read(1024 * 1024)
                if not chunk:
                    break
                total += len(chunk)
                if total > settings.max_upload_bytes:
                    raise InvalidDocumentError(
                        f"El archivo supera el limite configurado de {settings.max_upload_mb} MB."
                    )
                digest.update(chunk)
                out_file.write(chunk)
        validate_docx_structure(destination)
    except Exception:
        destination.unlink(missing_ok=True)
        raise
    finally:
        await upload.close()

    return StoredUpload(
        original_filename=original_filename,
        safe_filename=safe_filename,
        stored_path=destination,
        sha256=digest.hexdigest(),
        file_size=total,
    )


def remove_project_files(settings: Settings, project_id: str) -> None:
    storage_root = settings.storage_root.resolve()
    for child in ("uploads", "generated", "exports"):
        project_dir = (settings.storage_root / child / project_id).resolve()
        if storage_root in project_dir.parents and project_dir.exists():
            shutil.rmtree(project_dir)


def remove_file(path: str | None) -> None:
    if path:
        Path(path).unlink(missing_ok=True)
