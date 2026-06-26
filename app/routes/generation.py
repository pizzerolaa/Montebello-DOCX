from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

from fastapi import APIRouter, Depends, Form, HTTPException, Request, status
from fastapi.responses import FileResponse, HTMLResponse, RedirectResponse
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.config import Settings, get_settings
from app.database import get_db
from app.models.equipment import Equipment
from app.models.generated_artifact import GeneratedArtifact
from app.models.project import Project
from app.services.acta_generator import generate_acta
from app.services.annex_generator import generate_annex
from app.services.archive_service import create_project_zip
from app.services.excel_service import export_project_excel


router = APIRouter(prefix="/projects/{project_id}", tags=["generation"])


def _project_or_404(db: Session, project_id: str) -> Project:
    project = db.scalar(
        select(Project)
        .where(Project.id == project_id)
        .options(
            selectinload(Project.lots),
            selectinload(Project.signatures),
            selectinload(Project.source_documents),
            selectinload(Project.extraction_issues),
            selectinload(Project.generated_artifacts),
            selectinload(Project.equipment).selectinload(Equipment.work_items),
        )
    )
    if project is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Proyecto no encontrado.")
    return project


@router.get("/generate", response_class=HTMLResponse, name="project_generate")
def generate_page(project_id: str, request: Request, db: Session = Depends(get_db)) -> HTMLResponse:
    project = _project_or_404(db, project_id)
    return request.app.state.templates.TemplateResponse(request, "projects/generate.html", {"project": project})


@router.post("/generate", name="project_generate_post")
def generate_project(
    project_id: str,
    request: Request,
    action: str = Form("excel"),
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> RedirectResponse:
    project = _project_or_404(db, project_id)
    if action == "excel":
        result_path, filename, artifact_type = _generate_excel(project, settings)
    elif action == "acta":
        result_path, filename, artifact_type = _generate_acta(project, settings)
    elif action == "annex":
        result_path, filename, artifact_type = _generate_annex(project, settings)
    elif action == "zip":
        result_path, filename, artifact_type = _generate_zip(project, settings)
    else:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Accion de generacion no soportada.")
    db.add(
        GeneratedArtifact(
            project_id=project.id,
            artifact_type=artifact_type,
            filename=filename,
            stored_path=str(result_path),
        )
    )
    db.commit()
    return RedirectResponse(request.url_for("project_generate", project_id=project.id), status_code=status.HTTP_303_SEE_OTHER)


@router.get("/artifacts/{artifact_id}", name="project_artifact_download")
def artifact_download(project_id: str, artifact_id: str, db: Session = Depends(get_db)) -> FileResponse:
    project = _project_or_404(db, project_id)
    artifact = next((item for item in project.generated_artifacts if item.id == artifact_id), None)
    if artifact is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Archivo generado no encontrado.")
    path = Path(artifact.stored_path)
    if not path.exists():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="El archivo generado ya no existe.")
    media_type = _media_type(artifact.filename)
    return FileResponse(
        path,
        filename=artifact.filename,
        media_type=media_type,
    )


@router.delete("/artifacts/{artifact_id}", name="project_artifact_delete")
def artifact_delete(project_id: str, artifact_id: str, db: Session = Depends(get_db)) -> dict[str, str]:
    project = _project_or_404(db, project_id)
    artifact = next((item for item in project.generated_artifacts if item.id == artifact_id), None)
    if artifact is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Archivo generado no encontrado.")
    Path(artifact.stored_path).unlink(missing_ok=True)
    db.delete(artifact)
    db.commit()
    return {"status": "deleted", "artifact_id": artifact_id}


def _generate_excel(project: Project, settings: Settings) -> tuple[Path, str, str]:
    result = export_project_excel(project, settings)
    return result.stored_path, result.filename, "EXCEL_XLSX"


def _generate_acta(project: Project, settings: Settings) -> tuple[Path, str, str]:
    filename = f"{_safe_stem(project.name)}_ACTA_{_timestamp()}.docx"
    path = _generated_dir(project, settings) / filename
    return generate_acta(project, settings, path), filename, "ACTA_DOCX"


def _generate_annex(project: Project, settings: Settings) -> tuple[Path, str, str]:
    filename = f"{_safe_stem(project.name)}_ANEXO_{_timestamp()}.docx"
    path = _generated_dir(project, settings) / filename
    return generate_annex(project, settings, path), filename, "ANNEX_DOCX"


def _generate_zip(project: Project, settings: Settings) -> tuple[Path, str, str]:
    filename = f"{_safe_stem(project.name)}_outputs_{_timestamp()}.zip"
    path = _generated_dir(project, settings) / filename
    return create_project_zip(project, settings, path), filename, "PROJECT_ZIP"


def _generated_dir(project: Project, settings: Settings) -> Path:
    path = (settings.storage_root / "generated" / project.id).resolve()
    storage_root = settings.storage_root.resolve()
    if storage_root not in path.parents:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Ruta de generacion no valida.")
    path.mkdir(parents=True, exist_ok=True)
    return path


def _timestamp() -> str:
    return datetime.now(UTC).strftime("%Y%m%d_%H%M%S")


def _safe_stem(value: str) -> str:
    cleaned = "".join(char if char.isalnum() or char in {"-", "_"} else "_" for char in value.strip())
    return cleaned.strip("_") or "project"


def _media_type(filename: str) -> str:
    if filename.lower().endswith(".xlsx"):
        return "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    if filename.lower().endswith(".docx"):
        return "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
    if filename.lower().endswith(".zip"):
        return "application/zip"
    return "application/octet-stream"
